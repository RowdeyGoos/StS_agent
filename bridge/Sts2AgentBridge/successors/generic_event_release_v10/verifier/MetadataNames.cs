using System;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.Reflection.Metadata;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV10;

internal sealed class MetadataNames : ISignatureTypeProvider<string, object?>
{
    private static readonly IReadOnlyDictionary<PrimitiveTypeCode, string> PrimitiveNames =
        new Dictionary<PrimitiveTypeCode, string>
        {
            [PrimitiveTypeCode.Boolean] = "System.Boolean",
            [PrimitiveTypeCode.Byte] = "System.Byte",
            [PrimitiveTypeCode.Char] = "System.Char",
            [PrimitiveTypeCode.Double] = "System.Double",
            [PrimitiveTypeCode.Int16] = "System.Int16",
            [PrimitiveTypeCode.Int32] = "System.Int32",
            [PrimitiveTypeCode.Int64] = "System.Int64",
            [PrimitiveTypeCode.IntPtr] = "System.IntPtr",
            [PrimitiveTypeCode.Object] = "System.Object",
            [PrimitiveTypeCode.SByte] = "System.SByte",
            [PrimitiveTypeCode.Single] = "System.Single",
            [PrimitiveTypeCode.String] = "System.String",
            [PrimitiveTypeCode.TypedReference] = "System.TypedReference",
            [PrimitiveTypeCode.UInt16] = "System.UInt16",
            [PrimitiveTypeCode.UInt32] = "System.UInt32",
            [PrimitiveTypeCode.UInt64] = "System.UInt64",
            [PrimitiveTypeCode.UIntPtr] = "System.UIntPtr",
            [PrimitiveTypeCode.Void] = "System.Void",
        };

    public string GetArrayType(string elementType, ArrayShape shape) =>
        elementType + "[" + new string(',', shape.Rank - 1) + "]";

    public string GetByReferenceType(string elementType) => elementType + "&";

    public string GetFunctionPointerType(MethodSignature<string> signature) =>
        "methodptr(" + FormatParameters(signature.ParameterTypes) + ")->" + signature.ReturnType;

    public string GetGenericInstantiation(string genericType, ImmutableArray<string> typeArguments)
    {
        int arityMarker = genericType.LastIndexOf('`');
        if (arityMarker >= 0)
        {
            genericType = genericType[..arityMarker];
        }

        return genericType + "<" + string.Join(",", typeArguments) + ">";
    }

    public string GetGenericMethodParameter(object? genericContext, int index) => "!!" + index;

    public string GetGenericTypeParameter(object? genericContext, int index) => "!" + index;

    public string GetModifiedType(string modifier, string unmodifiedType, bool isRequired) => unmodifiedType;

    public string GetPinnedType(string elementType) => elementType;

    public string GetPointerType(string elementType) => elementType + "*";

    public string GetPrimitiveType(PrimitiveTypeCode typeCode)
    {
        if (!PrimitiveNames.TryGetValue(typeCode, out string? name))
        {
            throw new VerificationException("unresolved_primitive_type");
        }

        return name;
    }

    public string GetSZArrayType(string elementType) => elementType + "[]";

    public string GetTypeFromDefinition(
        MetadataReader reader,
        TypeDefinitionHandle handle,
        byte rawTypeKind) => TypeDefinitionName(reader, handle);

    public string GetTypeFromReference(
        MetadataReader reader,
        TypeReferenceHandle handle,
        byte rawTypeKind) => TypeReferenceName(reader, handle);

    public string GetTypeFromSpecification(
        MetadataReader reader,
        object? genericContext,
        TypeSpecificationHandle handle,
        byte rawTypeKind) => reader.GetTypeSpecification(handle).DecodeSignature(this, genericContext);

    public static string TypeDefinitionName(MetadataReader reader, TypeDefinitionHandle handle)
    {
        TypeDefinition definition = reader.GetTypeDefinition(handle);
        string name = reader.GetString(definition.Name);
        TypeDefinitionHandle declaring = definition.GetDeclaringType();
        if (!declaring.IsNil)
        {
            return TypeDefinitionName(reader, declaring) + "+" + name;
        }

        string ns = reader.GetString(definition.Namespace);
        return string.IsNullOrEmpty(ns) ? name : ns + "." + name;
    }

    public static string TypeReferenceName(MetadataReader reader, TypeReferenceHandle handle)
    {
        TypeReference reference = reader.GetTypeReference(handle);
        string name = reader.GetString(reference.Name);
        if (reference.ResolutionScope.Kind == HandleKind.TypeReference)
        {
            return TypeReferenceName(reader, (TypeReferenceHandle)reference.ResolutionScope) + "+" + name;
        }

        string ns = reader.GetString(reference.Namespace);
        return string.IsNullOrEmpty(ns) ? name : ns + "." + name;
    }

    public static string TypeReferenceAssembly(MetadataReader reader, TypeReferenceHandle handle)
    {
        TypeReference reference = reader.GetTypeReference(handle);
        EntityHandle scope = reference.ResolutionScope;
        if (scope.Kind == HandleKind.AssemblyReference)
        {
            return reader.GetString(reader.GetAssemblyReference((AssemblyReferenceHandle)scope).Name);
        }

        if (scope.Kind == HandleKind.TypeReference)
        {
            return TypeReferenceAssembly(reader, (TypeReferenceHandle)scope);
        }

        if (scope.Kind == HandleKind.ModuleDefinition)
        {
            return reader.GetString(reader.GetAssemblyDefinition().Name);
        }

        throw new VerificationException("unresolved_type_scope");
    }

    public static string MethodDefinitionIdentity(
        MetadataReader reader,
        MethodDefinitionHandle handle,
        MetadataNames provider)
    {
        MethodDefinition method = reader.GetMethodDefinition(handle);
        string owner = TypeDefinitionName(reader, method.GetDeclaringType());
        string name = reader.GetString(method.Name);
        MethodSignature<string> signature = method.DecodeSignature(provider, null);
        return owner + "." + name + "(" + FormatParameters(signature.ParameterTypes) + ")";
    }

    public static string MemberReferenceIdentity(
        MetadataReader reader,
        MemberReferenceHandle handle,
        MetadataNames provider)
    {
        MemberReference member = reader.GetMemberReference(handle);
        string owner = ParentTypeName(reader, member.Parent, provider);
        string name = reader.GetString(member.Name);
        if (member.GetKind() == MemberReferenceKind.Field)
        {
            _ = member.DecodeFieldSignature(provider, null);
            return owner + "." + name;
        }

        MethodSignature<string> signature = member.DecodeMethodSignature(provider, null);
        return owner + "." + name + "(" + FormatParameters(signature.ParameterTypes) + ")";
    }

    public static string ParentTypeName(
        MetadataReader reader,
        EntityHandle parent,
        MetadataNames provider)
    {
        return parent.Kind switch
        {
            HandleKind.TypeReference => TypeReferenceName(reader, (TypeReferenceHandle)parent),
            HandleKind.TypeDefinition => TypeDefinitionName(reader, (TypeDefinitionHandle)parent),
            HandleKind.TypeSpecification => reader.GetTypeSpecification((TypeSpecificationHandle)parent)
                .DecodeSignature(provider, null),
            HandleKind.MethodDefinition => TypeDefinitionName(
                reader,
                reader.GetMethodDefinition((MethodDefinitionHandle)parent).GetDeclaringType()),
            _ => throw new VerificationException("unresolved_member_parent"),
        };
    }

    public static string EntityTypeName(
        MetadataReader reader,
        EntityHandle handle,
        MetadataNames provider)
    {
        return handle.Kind switch
        {
            HandleKind.TypeDefinition => TypeDefinitionName(reader, (TypeDefinitionHandle)handle),
            HandleKind.TypeReference => TypeReferenceName(reader, (TypeReferenceHandle)handle),
            HandleKind.TypeSpecification => reader.GetTypeSpecification((TypeSpecificationHandle)handle)
                .DecodeSignature(provider, null),
            _ => throw new VerificationException("unresolved_entity_type"),
        };
    }

    public static string FormatParameters(ImmutableArray<string> parameters) =>
        string.Join(",", parameters);
}
