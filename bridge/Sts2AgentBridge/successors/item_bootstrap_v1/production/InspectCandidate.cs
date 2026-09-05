using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.PortableExecutable;
using System.Text.Json;

// Candidate metadata only. This does not replace the future default-deny
// owning-callsite/IL/source surface policy or authorize installation.
internal static class Program
{
    private static readonly HashSet<string> NativeNames = new(StringComparer.Ordinal)
    {
        "getuid", "geteuid", "getpwuid_r", "open", "openat", "fstat", "fstatat",
        "read", "close", "acl_get_fd_np", "acl_get_entry", "acl_get_tag_type", "acl_free",
    };

    public static int Main(string[] args)
    {
        try
        {
            bool pure = args.Length == 2 && args[0] == "--pure";
            if (!pure && args.Length != 1) throw new InvalidOperationException();
            using var input = File.OpenRead(pure ? args[1] : args[0]);
            using var pe = new PEReader(input);
            if (!pe.HasMetadata || pe.PEHeaders.CorHeader is null ||
                (pe.PEHeaders.CorHeader.Flags & CorFlags.ILOnly) == 0 ||
                (!pure && pe.PEHeaders.CorHeader.EntryPointTokenOrRelativeVirtualAddress != 0))
                throw new InvalidOperationException();
            MetadataReader reader = pe.GetMetadataReader();
            AssemblyDefinition assembly = reader.GetAssemblyDefinition();
            if ((!pure && reader.GetString(assembly.Name) != "Sts2AgentBridgeItemV1") ||
                assembly.Version != new Version(1, 0, 0, 0))
                throw new InvalidOperationException();
            var references = reader.AssemblyReferences
                .Select(handle => reader.GetString(reader.GetAssemblyReference(handle).Name))
                .OrderBy(value => value, StringComparer.Ordinal).ToArray();
            var external = references.Where(value => !value.StartsWith("System.", StringComparison.Ordinal) &&
                value is not "System" and not "mscorlib" and not "netstandard").ToArray();
            if (pure)
            {
                if (external.Length != 0) throw new InvalidOperationException();
                Console.WriteLine(JsonSerializer.Serialize(new
                {
                    schema_version = 1, status = "passed", scope = "framework_references_only",
                    assembly_name = reader.GetString(assembly.Name),
                }));
                return 0;
            }
            if (!external.SequenceEqual(new[] { "GodotSharp", "sts2" }))
                throw new InvalidOperationException();
            foreach (TypeReferenceHandle handle in reader.TypeReferences)
            {
                TypeReference reference = reader.GetTypeReference(handle);
                string name = reader.GetString(reference.Namespace) + "." + reader.GetString(reference.Name);
                if (name.Contains("InternalsVisibleTo", StringComparison.Ordinal) ||
                    name.StartsWith("System.Diagnostics.Process", StringComparison.Ordinal) ||
                    name.StartsWith("System.Reflection.Emit", StringComparison.Ordinal) ||
                    name.StartsWith("System.Net.Http.", StringComparison.Ordinal) ||
                    name.StartsWith("System.IO.Pipes.", StringComparison.Ordinal) ||
                    name.StartsWith("System.IO.MemoryMappedFiles.", StringComparison.Ordinal) ||
                    name.Contains("Harmony", StringComparison.Ordinal) ||
                    name.Contains(".Saves.", StringComparison.Ordinal))
                    throw new InvalidOperationException();
            }
            int initializerCount = 0;
            int frozenTransportTestMethods = 0;
            var frozenTestArities = new HashSet<int>();
            var versions = new HashSet<string>(StringComparer.Ordinal);
            var imports = new List<string>();
            foreach (MethodDefinitionHandle handle in reader.MethodDefinitions)
            {
                MethodDefinition method = reader.GetMethodDefinition(handle);
                TypeDefinition owner = reader.GetTypeDefinition(method.GetDeclaringType());
                string ownerName = reader.GetString(owner.Namespace) + "." + reader.GetString(owner.Name);
                string methodName = reader.GetString(method.Name);
                if (ownerName.Contains("Tests", StringComparison.Ordinal))
                    throw new InvalidOperationException();
                if (methodName.Contains("ForTests", StringComparison.Ordinal) ||
                    methodName.Contains("Synthetic", StringComparison.Ordinal))
                {
                    if (ownerName != "Sts2AgentBridge.Successors.ItemTransportV1.ItemTransportRuntime" ||
                        methodName != "StartForTests" ||
                        (method.Attributes & MethodAttributes.MemberAccessMask) != MethodAttributes.Assembly ||
                        (method.Attributes & MethodAttributes.Static) != 0)
                        throw new InvalidOperationException();
                    BlobReader signature = reader.GetBlobReader(method.Signature);
                    if (signature.ReadByte() != 0x20) throw new InvalidOperationException();
                    int arity = signature.ReadCompressedInteger();
                    if ((arity != 1 && arity != 2) || !frozenTestArities.Add(arity) ||
                        signature.ReadByte() != 0x02)
                        throw new InvalidOperationException();
                    for (int index = 0; index < arity; index++)
                    {
                        if (signature.ReadByte() != 0x12) throw new InvalidOperationException();
                        int coded = signature.ReadCompressedInteger();
                        if ((coded & 3) != 1) throw new InvalidOperationException();
                        TypeReference parameter = reader.GetTypeReference(MetadataTokens.TypeReferenceHandle(coded >> 2));
                        string fullName = reader.GetString(parameter.Namespace) + "." + reader.GetString(parameter.Name);
                        if (fullName != (index == 0 ? "System.Net.Sockets.TcpListener" : "System.Action"))
                            throw new InvalidOperationException();
                    }
                    if (signature.RemainingBytes != 0) throw new InvalidOperationException();
                    frozenTransportTestMethods++;
                }
                if ((method.Attributes & MethodAttributes.PinvokeImpl) != 0)
                {
                    MethodImport import = method.GetImport();
                    string module = reader.GetString(reader.GetModuleReference(import.Module).Name);
                    string name = reader.GetString(import.Name);
                    if (module != "/usr/lib/libSystem.B.dylib" || !NativeNames.Contains(name) ||
                        !ownerName.StartsWith("Sts2AgentBridge.Successors.ItemBootstrapV1.", StringComparison.Ordinal))
                        throw new InvalidOperationException();
                    imports.Add(name);
                }
            }
            foreach (CustomAttributeHandle handle in reader.CustomAttributes)
            {
                CustomAttribute attribute = reader.GetCustomAttribute(handle);
                if (attribute.Constructor.Kind != HandleKind.MemberReference) continue;
                MemberReference constructor = reader.GetMemberReference((MemberReferenceHandle)attribute.Constructor);
                if (constructor.Parent.Kind != HandleKind.TypeReference) continue;
                TypeReference type = reader.GetTypeReference((TypeReferenceHandle)constructor.Parent);
                if (reader.GetString(type.Namespace) == "MegaCrit.Sts2.Core.Modding" &&
                    reader.GetString(type.Name) == "ModInitializerAttribute")
                {
                    initializerCount++;
                    if (attribute.Parent.Kind != HandleKind.TypeDefinition)
                        throw new InvalidOperationException();
                    TypeDefinition initializer = reader.GetTypeDefinition((TypeDefinitionHandle)attribute.Parent);
                    if (reader.GetString(initializer.Namespace) != "Sts2AgentBridge.Successors.ItemBootstrapV1" ||
                        reader.GetString(initializer.Name) != "ModEntry" ||
                        (initializer.Attributes & TypeAttributes.VisibilityMask) != TypeAttributes.Public ||
                        (initializer.Attributes & (TypeAttributes.Abstract | TypeAttributes.Sealed)) !=
                            (TypeAttributes.Abstract | TypeAttributes.Sealed))
                        throw new InvalidOperationException();
                    int callable = 0;
                    foreach (MethodDefinitionHandle methodHandle in initializer.GetMethods())
                    {
                        MethodDefinition method = reader.GetMethodDefinition(methodHandle);
                        if (reader.GetString(method.Name) != "Initialize") continue;
                        if ((method.Attributes & MethodAttributes.MemberAccessMask) != MethodAttributes.Public ||
                            (method.Attributes & MethodAttributes.Static) == 0 ||
                            method.GetGenericParameters().Count != 0 || method.RelativeVirtualAddress == 0 ||
                            !reader.GetBlobBytes(method.Signature).AsSpan().SequenceEqual(new byte[] { 0, 0, 1 }))
                            throw new InvalidOperationException();
                        callable++;
                    }
                    if (callable != 1) throw new InvalidOperationException();
                    byte[] value = reader.GetBlobBytes(attribute.Value);
                    byte[] expected = { 1, 0, 10, 73, 110, 105, 116, 105, 97, 108, 105, 122, 101, 0, 0 };
                    if (!value.AsSpan().SequenceEqual(expected)) throw new InvalidOperationException();
                }
                if (reader.GetString(type.Namespace) == "System.Reflection")
                {
                    string name = reader.GetString(type.Name);
                    string? expectedVersion = name switch
                    {
                        "AssemblyFileVersionAttribute" => "1.0.0.0",
                        "AssemblyInformationalVersionAttribute" => "1.0.0",
                        _ => null,
                    };
                    if (expectedVersion is not null)
                    {
                        if (attribute.Parent.Kind != HandleKind.AssemblyDefinition || !versions.Add(name))
                            throw new InvalidOperationException();
                        BlobReader value = reader.GetBlobReader(attribute.Value);
                        if (value.ReadUInt16() != 1 || value.ReadSerializedString() != expectedVersion ||
                            value.ReadUInt16() != 0 || value.RemainingBytes != 0)
                            throw new InvalidOperationException();
                    }
                }
            }
            if (frozenTransportTestMethods != 2 || versions.Count != 2) throw new InvalidOperationException();
            if (initializerCount != 1 || imports.Count != NativeNames.Count ||
                !NativeNames.SetEquals(imports)) throw new InvalidOperationException();
            Console.WriteLine(JsonSerializer.Serialize(new
            {
                schema_version = 1, status = "passed", scope = "candidate_metadata_only",
                initializer_count = initializerCount, native_import_count = imports.Count,
                frozen_transport_test_method_count = frozenTransportTestMethods,
                nonframework_references = external, production_assembly_executed = false,
            }));
            return 0;
        }
        catch
        {
            Console.WriteLine("{\"schema_version\":1,\"status\":\"failed\",\"code\":\"candidate_metadata_mismatch\"}");
            return 4;
        }
    }
}
