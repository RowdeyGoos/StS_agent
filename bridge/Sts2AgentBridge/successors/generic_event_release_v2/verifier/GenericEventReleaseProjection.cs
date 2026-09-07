using System;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.Globalization;
using System.Linq;
using System.Reflection;
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.PortableExecutable;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV2;

internal sealed record GenericEventReleaseProjection(
    string AssemblyName,
    string AssemblyVersion,
    string ArtifactSha256,
    long ArtifactLength,
    string MetadataProjectionSha256,
    int CheckedMethodBodies,
    string[] Inventory,
    string[] Routes,
    string[] RequestLines,
    string[] NativeImports,
    string[] InitializerAttributes,
    string[] SensitiveReferences,
    string[] ForbiddenReferences,
    string[] CriticalReferences);

internal static partial class GenericEventReleaseProjectionBuilder
{
    private static readonly Regex RequestLinePattern = new(
        @"(?:GET|POST) /probe/generic-event-v3/[a-z0-9/-]+ HTTP/1\.1",
        RegexOptions.CultureInvariant);

    internal static GenericEventReleaseProjection Build(byte[] image)
    {
        try
        {
            using var stream = new System.IO.MemoryStream(image, writable: false);
            using var pe = new PEReader(stream, PEStreamOptions.LeaveOpen);
            if (!pe.HasMetadata || pe.PEHeaders.CorHeader is null ||
                (pe.PEHeaders.CorHeader.Flags & CorFlags.ILOnly) == 0 ||
                pe.PEHeaders.CorHeader.EntryPointTokenOrRelativeVirtualAddress != 0)
            {
                throw new VerificationException("candidate_pe_shape");
            }
            MetadataReader reader = pe.GetMetadataReader();
            var names = new MetadataNames();
            var inventory = new List<string>();
            var routes = new SortedSet<string>(StringComparer.Ordinal);
            var requestLines = new SortedSet<string>(StringComparer.Ordinal);
            var native = new List<string>();
            var initializers = new List<string>();
            var sensitive = new List<string>();
            var forbidden = new List<string>();
            var critical = new List<string>();
            var methods = new Dictionary<MethodDefinitionHandle, string>();
            var fields = new Dictionary<FieldDefinitionHandle, string>();
            foreach (Match match in RequestLinePattern.Matches(Encoding.Latin1.GetString(image)))
            {
                requestLines.Add(match.Value);
            }

            AssemblyDefinition assembly = reader.GetAssemblyDefinition();
            string assemblyName = reader.GetString(assembly.Name);
            string assemblyVersion = assembly.Version.ToString();
            inventory.Add(FormattableString.Invariant(
                $"assembly|{assemblyName}|{assemblyVersion}|{(int)assembly.Flags}|{(int)assembly.HashAlgorithm}|{Hex(reader.GetBlobBytes(assembly.PublicKey))}"));
            ModuleDefinition module = reader.GetModuleDefinition();
            inventory.Add(FormattableString.Invariant(
                $"module|{reader.GetString(module.Name)}|{Guid(reader, module.Mvid)}|{Guid(reader, module.GenerationId)}|{Guid(reader, module.BaseGenerationId)}"));
            inventory.Add($"metadata_raw|{Sha(pe.GetMetadata().GetContent().AsSpan())}");
            inventory.Add(FormattableString.Invariant(
                $"cor|{(int)pe.PEHeaders.CorHeader.Flags}|{pe.PEHeaders.CorHeader.MajorRuntimeVersion}|{pe.PEHeaders.CorHeader.MinorRuntimeVersion}"));
            foreach (SectionHeader section in pe.PEHeaders.SectionHeaders)
            {
                int offset = section.PointerToRawData;
                int length = section.SizeOfRawData;
                if (offset < 0 || length < 0 || offset > image.Length - length)
                {
                    throw new VerificationException("candidate_section_boundary");
                }
                inventory.Add(FormattableString.Invariant(
                    $"section|{section.Name}|{section.VirtualSize}|{length}|{(int)section.SectionCharacteristics}|{Sha(image.AsSpan(offset, length))}"));
            }

            foreach (AssemblyReferenceHandle handle in reader.AssemblyReferences)
            {
                AssemblyReference value = reader.GetAssemblyReference(handle);
                inventory.Add(FormattableString.Invariant(
                    $"assembly_ref|{reader.GetString(value.Name)}|{value.Version}|{(int)value.Flags}|{String(reader, value.Culture)}|{Hex(reader.GetBlobBytes(value.PublicKeyOrToken))}|{Hex(reader.GetBlobBytes(value.HashValue))}"));
            }
            for (int row = 1; row <= reader.GetTableRowCount(TableIndex.ModuleRef); row++)
            {
                ModuleReferenceHandle handle = MetadataTokens.ModuleReferenceHandle(row);
                inventory.Add($"module_ref|{reader.GetString(reader.GetModuleReference(handle).Name)}");
            }
            foreach (TypeReferenceHandle handle in reader.TypeReferences)
            {
                TypeReference value = reader.GetTypeReference(handle);
                inventory.Add($"type_ref|{MetadataNames.TypeReferenceName(reader, handle)}|{Scope(reader, value.ResolutionScope, names)}");
            }
            for (int row = 1; row <= reader.GetTableRowCount(TableIndex.TypeSpec); row++)
            {
                TypeSpecificationHandle handle = MetadataTokens.TypeSpecificationHandle(row);
                inventory.Add($"type_spec|{reader.GetTypeSpecification(handle).DecodeSignature(names, null)}");
            }
            foreach (TypeDefinitionHandle handle in reader.TypeDefinitions)
            {
                TypeDefinition value = reader.GetTypeDefinition(handle);
                string name = MetadataNames.TypeDefinitionName(reader, handle);
                inventory.Add(FormattableString.Invariant(
                    $"type_def|{name}|{(int)value.Attributes}|{Type(reader, value.BaseType, names)}|{value.GetLayout().PackingSize}|{value.GetLayout().Size}"));
                foreach (InterfaceImplementationHandle implementationHandle in value.GetInterfaceImplementations())
                {
                    InterfaceImplementation implementation = reader.GetInterfaceImplementation(implementationHandle);
                    inventory.Add($"interface|{name}|{Type(reader, implementation.Interface, names)}");
                }
                foreach (MethodImplementationHandle implementationHandle in value.GetMethodImplementations())
                {
                    MethodImplementation implementation = reader.GetMethodImplementation(implementationHandle);
                    inventory.Add($"method_impl|{name}|{MethodOperand(reader, implementation.MethodBody, names, methods)}|{MethodOperand(reader, implementation.MethodDeclaration, names, methods)}");
                }
                AddGenericParameters(reader, value.GetGenericParameters(), name, names, inventory);
                foreach (FieldDefinitionHandle fieldHandle in value.GetFields())
                {
                    FieldDefinition field = reader.GetFieldDefinition(fieldHandle);
                    string identity = name + "." + reader.GetString(field.Name);
                    fields[fieldHandle] = identity;
                    inventory.Add(FormattableString.Invariant(
                        $"field_def|{identity}|{field.DecodeSignature(names, null)}|{(int)field.Attributes}|{field.GetOffset()}|{field.GetRelativeVirtualAddress()}|{Hex(reader.GetBlobBytes(field.GetMarshallingDescriptor()))}"));
                }
                foreach (MethodDefinitionHandle methodHandle in value.GetMethods())
                {
                    MethodDefinition method = reader.GetMethodDefinition(methodHandle);
                    MethodSignature<string> signature = method.DecodeSignature(names, null);
                    string identity = name + "." + reader.GetString(method.Name) + "(" +
                        MetadataNames.FormatParameters(signature.ParameterTypes) + ")";
                    methods[methodHandle] = identity;
                }
                foreach (PropertyDefinitionHandle propertyHandle in value.GetProperties())
                {
                    PropertyDefinition property = reader.GetPropertyDefinition(propertyHandle);
                    MethodSignature<string> signature = property.DecodeSignature(names, null);
                    PropertyAccessors accessors = property.GetAccessors();
                    inventory.Add(FormattableString.Invariant(
                        $"property|{name}.{reader.GetString(property.Name)}|{signature.ReturnType}|{MetadataNames.FormatParameters(signature.ParameterTypes)}|{(int)property.Attributes}|{Token(accessors.Getter)}|{Token(accessors.Setter)}|{string.Join(',', accessors.Others.Select(handle => Token(handle)))}"));
                }
                foreach (EventDefinitionHandle eventHandle in value.GetEvents())
                {
                    EventDefinition eventDefinition = reader.GetEventDefinition(eventHandle);
                    EventAccessors accessors = eventDefinition.GetAccessors();
                    inventory.Add(FormattableString.Invariant(
                        $"event|{name}.{reader.GetString(eventDefinition.Name)}|{Type(reader, eventDefinition.Type, names)}|{(int)eventDefinition.Attributes}|{Token(accessors.Adder)}|{Token(accessors.Remover)}|{Token(accessors.Raiser)}|{string.Join(',', accessors.Others.Select(handle => Token(handle)))}"));
                }
            }

            foreach ((MethodDefinitionHandle handle, string identity) in methods)
            {
                MethodDefinition method = reader.GetMethodDefinition(handle);
                MethodSignature<string> signature = method.DecodeSignature(names, null);
                inventory.Add(FormattableString.Invariant(
                    $"method_def|{Token(handle)}|{identity}|{signature.ReturnType}|{signature.GenericParameterCount}|{signature.RequiredParameterCount}|{(signature.Header.IsInstance ? 1 : 0)}|{(int)method.Attributes}|{(int)method.ImplAttributes}"));
                AddGenericParameters(reader, method.GetGenericParameters(), identity, names, inventory);
                foreach (ParameterHandle parameterHandle in method.GetParameters())
                {
                    Parameter parameter = reader.GetParameter(parameterHandle);
                    inventory.Add(FormattableString.Invariant(
                        $"parameter|{Token(handle)}|{parameter.SequenceNumber}|{reader.GetString(parameter.Name)}|{(int)parameter.Attributes}"));
                }
            }
            foreach (MemberReferenceHandle handle in reader.MemberReferences)
            {
                MemberReference value = reader.GetMemberReference(handle);
                inventory.Add(FormattableString.Invariant(
                    $"member_ref|{(int)value.GetKind()}|{MetadataNames.MemberReferenceIdentity(reader, handle, names)}"));
            }
            for (int row = 1; row <= reader.GetTableRowCount(TableIndex.MethodSpec); row++)
            {
                MethodSpecification value = reader.GetMethodSpecification(MetadataTokens.MethodSpecificationHandle(row));
                ImmutableArray<string> arguments = value.DecodeSignature(names, null);
                inventory.Add($"method_spec|{MethodOperand(reader, value.Method, names, methods)}|{string.Join(',', arguments)}");
            }
            for (int row = 1; row <= reader.GetTableRowCount(TableIndex.StandAloneSig); row++)
            {
                StandaloneSignatureHandle handle = MetadataTokens.StandaloneSignatureHandle(row);
                StandaloneSignature value = reader.GetStandaloneSignature(handle);
                inventory.Add($"standalone_sig|{Hex(reader.GetBlobBytes(value.Signature))}");
            }
            foreach (CustomAttributeHandle handle in reader.CustomAttributes)
            {
                CustomAttribute value = reader.GetCustomAttribute(handle);
                string constructor = MethodOperand(reader, value.Constructor, names, methods);
                string blob = Hex(reader.GetBlobBytes(value.Value));
                inventory.Add($"attribute|{Token(value.Parent)}|{constructor}|{blob}");
                if (constructor is
                    "MegaCrit.Sts2.Core.Modding.ModInitializerAttribute..ctor(System.String)" or
                    "System.Runtime.CompilerServices.ModuleInitializerAttribute..ctor()")
                {
                    initializers.Add($"{AttributeParent(reader, value.Parent, names, methods)}|{constructor}|{blob}");
                }
            }
            foreach (ManifestResourceHandle handle in reader.ManifestResources)
            {
                ManifestResource value = reader.GetManifestResource(handle);
                inventory.Add(FormattableString.Invariant(
                    $"resource|{reader.GetString(value.Name)}|{(int)value.Attributes}|{value.Offset}|{Token(value.Implementation)}"));
            }
            foreach (AssemblyFileHandle handle in reader.AssemblyFiles)
            {
                AssemblyFile value = reader.GetAssemblyFile(handle);
                inventory.Add($"file|{reader.GetString(value.Name)}|{value.ContainsMetadata}|{Hex(reader.GetBlobBytes(value.HashValue))}");
            }
            foreach (ExportedTypeHandle handle in reader.ExportedTypes)
            {
                ExportedType value = reader.GetExportedType(handle);
                inventory.Add(FormattableString.Invariant(
                    $"exported_type|{reader.GetString(value.Namespace)}.{reader.GetString(value.Name)}|{(int)value.Attributes}|{value.GetTypeDefinitionId()}|{Token(value.Implementation)}"));
            }
            for (int table = 0; table <= (int)TableIndex.GenericParamConstraint; table++)
            {
                int rows;
                try { rows = reader.GetTableRowCount((TableIndex)table); }
                catch (ArgumentOutOfRangeException) { continue; }
                inventory.Add($"table|{table}|{rows}");
            }

            int checkedBodies = 0;
            foreach ((MethodDefinitionHandle handle, string owner) in methods)
            {
                MethodDefinition method = reader.GetMethodDefinition(handle);
                if ((method.Attributes & MethodAttributes.PinvokeImpl) != 0)
                {
                    MethodImport import = method.GetImport();
                    string row = FormattableString.Invariant(
                        $"pinvoke|{owner}|{reader.GetString(reader.GetModuleReference(import.Module).Name)}|{reader.GetString(import.Name)}|{(int)import.Attributes}");
                    native.Add(row);
                    inventory.Add(row);
                }
                if (method.RelativeVirtualAddress == 0)
                {
                    continue;
                }
                checkedBodies++;
                MethodBodyBlock body = pe.GetMethodBody(method.RelativeVirtualAddress);
                byte[] il = body.GetILBytes() ?? throw new VerificationException("unresolved_method_body");
                IReadOnlyList<IlInstruction> instructions = IlDecoder.Decode(il);
                var bodyLines = new List<string>
                {
                    FormattableString.Invariant($"header|{body.MaxStack}|{(body.LocalVariablesInitialized ? 1 : 0)}|{LocalSignature(reader, body.LocalSignature, names)}")
                };
                var offsets = instructions.Select((item, index) => (item.Offset, index))
                    .ToDictionary(item => item.Offset, item => item.index);
                for (int instructionIndex = 0; instructionIndex < instructions.Count; instructionIndex++)
                {
                    IlInstruction instruction = instructions[instructionIndex];
                    string operand = Operand(reader, instruction, names, methods, fields, routes);
                    int branch = instruction.BranchTarget.HasValue
                        ? RequireOffset(offsets, instruction.BranchTarget.Value) : -1;
                    string switches = string.Join(',', instruction.SwitchTargets.Select(target => RequireOffset(offsets, target)));
                    bodyLines.Add(FormattableString.Invariant(
                        $"il|{instruction.OpCode:x4}|{operand}|{instruction.IntegerConstant?.ToString(CultureInfo.InvariantCulture) ?? ""}|{instruction.VariableIndex?.ToString(CultureInfo.InvariantCulture) ?? ""}|{branch}|{switches}"));
                    if (instruction.MetadataToken.HasValue && instruction.OpCode != 0x0072)
                    {
                        EntityHandle target = IlDecoder.RequireEntityHandle(instruction.MetadataToken.Value);
                        string targetIdentity = DescribeEntity(reader, target, names, methods, fields);
                        if (IsTestNamed(targetIdentity))
                        {
                            sensitive.Add(FormattableString.Invariant(
                                $"sensitive|{owner}|{instruction.Offset}|{instruction.OpCode:x4}|{targetIdentity}"));
                        }
                        if (instruction.IsCall && IsForbiddenRuntimeReference(owner, targetIdentity))
                        {
                            forbidden.Add($"forbidden|{owner}|{instruction.Offset}|{targetIdentity}");
                        }
                        if (instruction.IsCall && IsCriticalReference(targetIdentity))
                        {
                            critical.Add(CriticalRow(owner, instruction, targetIdentity,
                                instructions, instructionIndex, reader, names, methods, fields));
                        }
                    }
                    if (instruction.OpCode == 0x0029)
                    {
                        forbidden.Add($"forbidden|{owner}|{instruction.Offset}|calli");
                    }
                }
                foreach (ExceptionRegion region in body.ExceptionRegions)
                {
                    bodyLines.Add(FormattableString.Invariant(
                        $"eh|{(int)region.Kind}|{region.TryOffset}|{region.TryLength}|{region.HandlerOffset}|{region.HandlerLength}|{region.FilterOffset}|{Type(reader, region.CatchType, names)}"));
                }
                inventory.Add($"body|{Token(handle)}|{Sha(Encoding.UTF8.GetBytes(string.Join('\n', bodyLines)))}");
            }

            string[] ordered = inventory.OrderBy(value => value, StringComparer.Ordinal).ToArray();
            return new GenericEventReleaseProjection(
                assemblyName,
                assemblyVersion,
                Sha(image),
                image.LongLength,
                Sha(Encoding.UTF8.GetBytes(string.Join('\n', ordered) + "\n")),
                checkedBodies,
                ordered,
                routes.ToArray(),
                requestLines.ToArray(),
                native.OrderBy(value => value, StringComparer.Ordinal).ToArray(),
                initializers.OrderBy(value => value, StringComparer.Ordinal).ToArray(),
                sensitive.OrderBy(value => value, StringComparer.Ordinal).ToArray(),
                forbidden.OrderBy(value => value, StringComparer.Ordinal).ToArray(),
                critical.OrderBy(value => value, StringComparer.Ordinal).ToArray());
        }
        catch (VerificationException) { throw; }
        catch (BadImageFormatException) { throw new VerificationException("candidate_metadata_invalid"); }
        catch (Exception) { throw new VerificationException("candidate_projection_invalid"); }
    }

    private static void AddGenericParameters(
        MetadataReader reader,
        GenericParameterHandleCollection handles,
        string owner,
        MetadataNames names,
        List<string> inventory)
    {
        foreach (GenericParameterHandle handle in handles)
        {
            GenericParameter value = reader.GetGenericParameter(handle);
            inventory.Add(FormattableString.Invariant(
                $"generic|{owner}|{value.Index}|{reader.GetString(value.Name)}|{(int)value.Attributes}"));
            foreach (GenericParameterConstraintHandle constraintHandle in value.GetConstraints())
            {
                GenericParameterConstraint constraint = reader.GetGenericParameterConstraint(constraintHandle);
                inventory.Add($"constraint|{owner}|{value.Index}|{Type(reader, constraint.Type, names)}");
            }
        }
    }

    private static string Operand(
        MetadataReader reader,
        IlInstruction instruction,
        MetadataNames names,
        IReadOnlyDictionary<MethodDefinitionHandle, string> methods,
        IReadOnlyDictionary<FieldDefinitionHandle, string> fields,
        SortedSet<string> routes)
    {
        if (!instruction.MetadataToken.HasValue) return string.Empty;
        int token = instruction.MetadataToken.Value;
        if (instruction.OpCode == 0x0072)
        {
            string value = reader.GetUserString(MetadataTokens.UserStringHandle(token));
            AddRoute(value, routes);
            return "string:" + Hex(Encoding.UTF8.GetBytes(value));
        }
        return DescribeEntity(reader, IlDecoder.RequireEntityHandle(token), names, methods, fields);
    }

    private static string DescribeEntity(
        MetadataReader reader,
        EntityHandle handle,
        MetadataNames names,
        IReadOnlyDictionary<MethodDefinitionHandle, string> methods,
        IReadOnlyDictionary<FieldDefinitionHandle, string> fields) => handle.Kind switch
        {
            HandleKind.TypeDefinition or HandleKind.TypeReference or HandleKind.TypeSpecification =>
                "type:" + MetadataNames.EntityTypeName(reader, handle, names),
            HandleKind.MethodDefinition => "method:" + methods[(MethodDefinitionHandle)handle],
            HandleKind.FieldDefinition => "field:" + fields[(FieldDefinitionHandle)handle],
            HandleKind.MemberReference => "member:" + MetadataNames.MemberReferenceIdentity(reader, (MemberReferenceHandle)handle, names),
            HandleKind.MethodSpecification => "method:" + MethodSpecification(reader, (MethodSpecificationHandle)handle, names, methods),
            HandleKind.StandaloneSignature => "signature:" + Hex(reader.GetBlobBytes(reader.GetStandaloneSignature((StandaloneSignatureHandle)handle).Signature)),
            _ => throw new VerificationException("unsupported_il_token"),
        };

    private static string MethodSpecification(
        MetadataReader reader,
        MethodSpecificationHandle handle,
        MetadataNames names,
        IReadOnlyDictionary<MethodDefinitionHandle, string> methods)
    {
        MethodSpecification value = reader.GetMethodSpecification(handle);
        return MethodOperand(reader, value.Method, names, methods) + "<" +
            string.Join(',', value.DecodeSignature(names, null)) + ">";
    }

    private static string MethodOperand(
        MetadataReader reader,
        EntityHandle handle,
        MetadataNames names,
        IReadOnlyDictionary<MethodDefinitionHandle, string> methods) => handle.Kind switch
        {
            HandleKind.MethodDefinition => methods.TryGetValue((MethodDefinitionHandle)handle, out string? value)
                ? value : MetadataNames.MethodDefinitionIdentity(reader, (MethodDefinitionHandle)handle, names),
            HandleKind.MemberReference => MetadataNames.MemberReferenceIdentity(reader, (MemberReferenceHandle)handle, names),
            HandleKind.MethodSpecification => MethodSpecification(reader, (MethodSpecificationHandle)handle, names, methods),
            _ => throw new VerificationException("unsupported_method_token"),
        };

    private static string AttributeParent(
        MetadataReader reader,
        EntityHandle handle,
        MetadataNames names,
        IReadOnlyDictionary<MethodDefinitionHandle, string> methods) => handle.Kind switch
        {
            HandleKind.TypeDefinition => "type:" + MetadataNames.TypeDefinitionName(reader, (TypeDefinitionHandle)handle),
            HandleKind.MethodDefinition => "method:" + methods[(MethodDefinitionHandle)handle],
            HandleKind.AssemblyDefinition => "assembly",
            HandleKind.ModuleDefinition => "module",
            _ => "token:" + Token(handle),
        };

    private static string LocalSignature(MetadataReader reader, StandaloneSignatureHandle handle, MetadataNames names)
    {
        if (handle.IsNil) return string.Empty;
        return string.Join(',', reader.GetStandaloneSignature(handle).DecodeLocalSignature(names, null));
    }

    private static string Scope(MetadataReader reader, EntityHandle handle, MetadataNames names) => handle.Kind switch
    {
        HandleKind.AssemblyReference => "assembly:" + reader.GetString(reader.GetAssemblyReference((AssemblyReferenceHandle)handle).Name),
        HandleKind.ModuleReference => "module:" + reader.GetString(reader.GetModuleReference((ModuleReferenceHandle)handle).Name),
        HandleKind.ModuleDefinition => "module",
        HandleKind.TypeReference => "type:" + MetadataNames.TypeReferenceName(reader, (TypeReferenceHandle)handle),
        _ => throw new VerificationException("unsupported_type_scope"),
    };

    private static string Type(MetadataReader reader, EntityHandle handle, MetadataNames names) =>
        handle.IsNil ? string.Empty : MetadataNames.EntityTypeName(reader, handle, names);

    private static string String(MetadataReader reader, StringHandle handle) =>
        handle.IsNil ? string.Empty : reader.GetString(handle);

    private static string Guid(MetadataReader reader, GuidHandle handle) =>
        handle.IsNil ? string.Empty : reader.GetGuid(handle).ToString("D");

    private static string Token(EntityHandle handle) => handle.IsNil ? "0" : MetadataTokens.GetToken(handle).ToString("x8", CultureInfo.InvariantCulture);

    private static int RequireOffset(Dictionary<int, int> offsets, int offset) =>
        offsets.TryGetValue(offset, out int index) ? index : throw new VerificationException("invalid_branch_target");

    private static void AddRoute(string value, SortedSet<string> routes)
    {
        if (value.Contains("/probe/", StringComparison.Ordinal) || value.Contains("/card-selection-v1/", StringComparison.Ordinal)) routes.Add(value);
    }

    private static bool IsCriticalReference(string identity) =>
        identity.Contains(".PinnedGenericEventHarmonyGuard.Verify(", StringComparison.Ordinal) ||
        identity.Contains(".ProductionGenericEventRuntimeFactory.CreateVerifiedService(", StringComparison.Ordinal) ||
        identity.Contains(".PinnedGenericEventV3NativeAdapter..ctor(", StringComparison.Ordinal) ||
        identity.Contains(".GenericEventV3Session..ctor(", StringComparison.Ordinal) ||
        identity.Contains(".GenericEventV3WireService..ctor(", StringComparison.Ordinal) ||
        identity.Contains(".GenericEventV3WireService.Handle(", StringComparison.Ordinal) ||
        identity.Contains(".OwnedByteFrameQueue.Submit(", StringComparison.Ordinal) ||
        identity.Contains(".<HandleSocketAsync>b__", StringComparison.Ordinal);

    private static string CriticalRow(
        string owner,
        IlInstruction instruction,
        string target,
        IReadOnlyList<IlInstruction> instructions,
        int index,
        MetadataReader reader,
        MetadataNames names,
        IReadOnlyDictionary<MethodDefinitionHandle, string> methods,
        IReadOnlyDictionary<FieldDefinitionHandle, string> fields)
    {
        // The frozen session takes adapter,nonce; the wire takes nonce,session.
        // Record the adapter producer rather than the final scalar nonce load.
        int inputIndex = target == "method:Sts2AgentBridge.Successors.GenericEventV3.GenericEventV3Session..ctor(Sts2AgentBridge.Successors.GenericEventV3.IGenericEventV3NativeAdapter,System.String)"
            ? index - 2 : index - 1;
        int input = inputIndex >= 0 ? LoadedLocal(instructions[inputIndex]) : -1;
        int output = index + 1 < instructions.Count ? StoredLocal(instructions[index + 1]) : -1;
        IlInstruction? next = index + 1 < instructions.Count ? instructions[index + 1] : null;
        IlInstruction? nextTwo = index + 2 < instructions.Count ? instructions[index + 2] : null;
        return FormattableString.Invariant(
            $"critical|{owner}|{instruction.Offset}|{instruction.OpCode:x4}|{input}|{output}|{target}|{NextOpcode(next)}|{NextTarget(next, reader, names, methods, fields)}|{NextOpcode(nextTwo)}|{NextTarget(nextTwo, reader, names, methods, fields)}");
    }

    private static string NextOpcode(IlInstruction? instruction) =>
        instruction.HasValue ? instruction.Value.OpCode.ToString("x4", CultureInfo.InvariantCulture) : string.Empty;

    private static string NextTarget(
        IlInstruction? instruction,
        MetadataReader reader,
        MetadataNames names,
        IReadOnlyDictionary<MethodDefinitionHandle, string> methods,
        IReadOnlyDictionary<FieldDefinitionHandle, string> fields) =>
        instruction is { MetadataToken: not null }
            ? instruction.Value.OpCode == 0x0072
                ? "string:" + Hex(Encoding.UTF8.GetBytes(reader.GetUserString(MetadataTokens.UserStringHandle(instruction.Value.MetadataToken.Value))))
                : DescribeEntity(reader, IlDecoder.RequireEntityHandle(instruction.Value.MetadataToken.Value), names, methods, fields)
            : string.Empty;

    private static int LoadedLocal(IlInstruction instruction) => instruction.OpCode switch
    {
        >= 0x0006 and <= 0x0009 => instruction.VariableIndex ?? -1,
        0x0011 or 0xfe0c => instruction.VariableIndex ?? -1,
        // Captured cleanup owners are fields; their full metadata tokens cannot
        // collide with a local index. Preserve exact producer/consumer identity.
        0x007b => instruction.MetadataToken ?? -1,
        _ => -1,
    };

    private static int StoredLocal(IlInstruction instruction) => instruction.OpCode switch
    {
        >= 0x000a and <= 0x000d => instruction.VariableIndex ?? -1,
        0x0013 or 0xfe0e => instruction.VariableIndex ?? -1,
        0x007d => instruction.MetadataToken ?? -1,
        _ => -1,
    };

    // These exceptions authorize an owner/member pair, never a reflection or
    // Harmony namespace. The exact policy additionally binds every call site and
    // complete method body to the independently reviewed production candidate.
    internal static bool IsForbiddenRuntimeReference(string owner, string identity)
    {
        const string hook = "Sts2AgentBridge.Successors.GenericEventV3.Native.GenericEventV3Hooks";
        bool hookOwner = owner.StartsWith(hook + ".", StringComparison.Ordinal) ||
            owner.StartsWith(hook + "+", StringComparison.Ordinal);
        bool guardOwner = owner.StartsWith(
            "Sts2AgentBridge.Successors.GenericEventReleaseV2.PinnedGenericEventHarmonyGuard.",
            StringComparison.Ordinal);
        bool allowedHook = hookOwner && identity is
            "member:System.Type.GetMethod(System.String,System.Type[])" or
            "member:System.Type.GetMethod(System.String,System.Reflection.BindingFlags)" or
            "member:System.Reflection.MethodInfo.op_Equality(System.Reflection.MethodInfo,System.Reflection.MethodInfo)" or
            "member:HarmonyLib.Harmony..ctor(System.String)" or
            "member:HarmonyLib.Harmony.GetPatchInfo(System.Reflection.MethodBase)" or
            "member:HarmonyLib.Harmony.Patch(System.Reflection.MethodBase,HarmonyLib.HarmonyMethod,HarmonyLib.HarmonyMethod,HarmonyLib.HarmonyMethod,HarmonyLib.HarmonyMethod)" or
            "member:HarmonyLib.Harmony.Unpatch(System.Reflection.MethodBase,System.Reflection.MethodInfo)" or
            "member:HarmonyLib.HarmonyMethod..ctor(System.Reflection.MethodInfo)" or
            "member:HarmonyLib.Patch.get_PatchMethod()" or
            "member:HarmonyLib.Patches.get_Owners()";
        bool allowedGuard = guardOwner && identity is
            "member:System.Reflection.Assembly.get_Location()" or
            "member:System.Reflection.Assembly.get_FullName()" or
            "member:System.Reflection.Assembly.GetName()" or
            "member:System.Reflection.Assembly.get_ManifestModule()" or
            "member:System.Reflection.Module.get_ModuleVersionId()" or
            "member:System.Reflection.AssemblyName.get_Name()" or
            "member:System.Runtime.Loader.AssemblyLoadContext.GetLoadContext(System.Reflection.Assembly)" or
            "member:System.Runtime.Loader.AssemblyLoadContext.get_IsCollectible()" or
            "member:System.AppDomain.get_CurrentDomain()" or
            "member:System.AppDomain.GetAssemblies()";
        bool allowedBuild = owner == "Sts2AgentBridge.Successors.ItemBootstrapV1.PinnedItemBuildGuard.Verify()" &&
            identity == "member:System.Reflection.Assembly.get_Location()";
        bool allowedExit = owner == "Sts2AgentBridge.Successors.GenericEventReleaseV2.GenericEventBootstrapHost.Initialize()" &&
            identity is "member:System.AppDomain.get_CurrentDomain()" or
                "member:System.AppDomain.add_ProcessExit(System.EventHandler)";
        bool sensitive = identity.StartsWith("member:System.Reflection.", StringComparison.Ordinal) ||
            identity.StartsWith("member:HarmonyLib.", StringComparison.Ordinal) ||
            identity.StartsWith("member:System.Type.GetMethod", StringComparison.Ordinal) ||
            identity.StartsWith("member:System.Type.GetField", StringComparison.Ordinal) ||
            identity.StartsWith("member:System.Type.GetProperty", StringComparison.Ordinal) ||
            identity.StartsWith("member:System.Type.GetConstructor", StringComparison.Ordinal) ||
            identity.StartsWith("member:System.Type.GetMember", StringComparison.Ordinal) ||
            identity.StartsWith("member:System.Type.GetEvent", StringComparison.Ordinal) ||
            identity.StartsWith("member:System.Type.GetNestedType", StringComparison.Ordinal) ||
            identity.StartsWith("member:System.Type.InvokeMember(", StringComparison.Ordinal) ||
            identity.Contains("System.Runtime.Loader", StringComparison.Ordinal) ||
            identity.StartsWith("member:System.AppDomain.", StringComparison.Ordinal);
        return sensitive && !(allowedHook || allowedGuard || allowedBuild || allowedExit) ||
            identity.Contains("System.Reflection.Emit", StringComparison.Ordinal) ||
            identity.Contains("System.Runtime.InteropServices.NativeLibrary", StringComparison.Ordinal) ||
            identity.Contains("System.Activator.", StringComparison.Ordinal) ||
            identity.Contains("System.Diagnostics.Process", StringComparison.Ordinal) ||
            identity.Contains("System.Net.Http", StringComparison.Ordinal) ||
            identity.Contains("System.Net.WebSockets", StringComparison.Ordinal) ||
            identity.Contains("System.Net.Quic", StringComparison.Ordinal) ||
            identity.Contains("System.IO.Pipes", StringComparison.Ordinal) ||
            identity.Contains("System.IO.MemoryMappedFiles", StringComparison.Ordinal) ||
            identity.Contains("System.IO.File.Write", StringComparison.Ordinal) ||
            identity.Contains("System.IO.File.Delete", StringComparison.Ordinal) ||
            identity.Contains("System.IO.Directory.Create", StringComparison.Ordinal);
    }

    private static bool IsTestNamed(string identity) =>
        identity.Contains("ForTests(", StringComparison.Ordinal) ||
        identity.Contains("Synthetic", StringComparison.Ordinal) ||
        identity.Contains("IsAllowedTestEndpoint(", StringComparison.Ordinal);

    internal static string Sha(ReadOnlySpan<byte> bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
    private static string Hex(byte[] bytes) => Convert.ToHexString(bytes).ToLowerInvariant();
}
