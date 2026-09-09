using System;
using System.Collections.Immutable;
using System.Reflection.Metadata;

// Signature decoding for the release-only PE comparison. No assembly loading.
internal sealed class MetadataNames : ISignatureTypeProvider<string, object?>
{
    public string GetArrayType(string type, ArrayShape shape) => type + "[" + new string(',', shape.Rank - 1) + "]";
    public string GetByReferenceType(string type) => type + "&";
    public string GetFunctionPointerType(MethodSignature<string> signature) =>
        "methodptr(" + string.Join(",", signature.ParameterTypes) + ")->" + signature.ReturnType;
    public string GetGenericInstantiation(string type, ImmutableArray<string> arguments) =>
        type + "<" + string.Join(",", arguments) + ">";
    public string GetGenericMethodParameter(object? context, int index) => "!!" + index;
    public string GetGenericTypeParameter(object? context, int index) => "!" + index;
    public string GetModifiedType(string modifier, string type, bool required) =>
        type + (required ? " modreq(" : " modopt(") + modifier + ")";
    public string GetPinnedType(string type) => type + " pinned";
    public string GetPointerType(string type) => type + "*";
    public string GetPrimitiveType(PrimitiveTypeCode code) => "primitive:" + code;
    public string GetSZArrayType(string type) => type + "[]";
    public string GetTypeFromDefinition(MetadataReader reader, TypeDefinitionHandle handle, byte kind) => TypeDefinitionName(reader, handle);
    public string GetTypeFromReference(MetadataReader reader, TypeReferenceHandle handle, byte kind) => TypeReferenceName(reader, handle);
    public string GetTypeFromSpecification(MetadataReader reader, object? context, TypeSpecificationHandle handle, byte kind) =>
        reader.GetTypeSpecification(handle).DecodeSignature(this, context);
    public static string TypeDefinitionName(MetadataReader reader, TypeDefinitionHandle handle)
    {
        var type = reader.GetTypeDefinition(handle);
        var name = reader.GetString(type.Name);
        var parent = type.GetDeclaringType();
        return parent.IsNil ? Qualified(reader.GetString(type.Namespace), name) : TypeDefinitionName(reader, parent) + "+" + name;
    }
    private static string TypeReferenceName(MetadataReader reader, TypeReferenceHandle handle)
    {
        var type = reader.GetTypeReference(handle);
        var name = reader.GetString(type.Name);
        return type.ResolutionScope.Kind == HandleKind.TypeReference
            ? TypeReferenceName(reader, (TypeReferenceHandle)type.ResolutionScope) + "+" + name
            : Qualified(reader.GetString(type.Namespace), name);
    }
    private static string Qualified(string ns, string name) => ns.Length == 0 ? name : ns + "." + name;
}
