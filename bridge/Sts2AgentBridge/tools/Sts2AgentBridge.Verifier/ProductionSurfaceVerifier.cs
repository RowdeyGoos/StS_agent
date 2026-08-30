using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.PortableExecutable;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace Sts2AgentBridge.Verifier;

internal sealed class ProductionSurfaceVerifier
{
    private const string ModInitializerType = "MegaCrit.Sts2.Core.Modding.ModInitializerAttribute";
    private const string AsyncStateMachineType = "System.Runtime.CompilerServices.AsyncStateMachineAttribute";
    private const string CompilerGeneratedType = "System.Runtime.CompilerServices.CompilerGeneratedAttribute";
    private const string FixedTimeEquals =
        "System.Security.Cryptography.CryptographicOperations.FixedTimeEquals(System.ReadOnlySpan<System.Byte>,System.ReadOnlySpan<System.Byte>)";
    private const string FixedTimeOwner =
        "Sts2AgentBridge.Core.Identity.FixedTimeAuthenticator.Matches(System.ReadOnlySpan<System.Byte>)";

    private static readonly Regex RoutePattern = new(
        @"/probe/v0/[A-Za-z0-9_./-]*",
        RegexOptions.CultureInvariant | RegexOptions.Compiled);

    private static readonly string[] HardForbiddenSourceFragments =
    {
        "0Harmony",
        "HarmonyLib",
        "MegaCrit.Sts2.Core.Saves",
        "GetChildren(",
        "GetNode(",
        "NodePath",
        "CallDeferred(",
        "System.Net.Http",
        "HttpClient",
        "WebRequest",
        "TcpClient",
        "NetworkStream",
        "Socket.Connect",
        "Socket.SendTo",
        "Socket.ReceiveFrom",
        "System.Net.Dns",
        "System.Net.WebSockets",
        "System.Net.Quic",
        "System.IO.Pipes",
        "System.IO.MemoryMappedFiles",
        "System.IO.Compression",
        "File.Write",
        "File.Append",
        "File.Create",
        "File.Copy",
        "File.Move",
        "File.Replace",
        "File.Delete",
        "Directory.Create",
        "Directory.Delete",
        "Directory.Enumerate",
        "Directory.GetFiles",
        "Directory.GetDirectories",
        "FileSystemWatcher",
        "System.Diagnostics.Process",
        "DllImport(",
        "LibraryImport(",
        "NativeLibrary.",
        "System.Reflection.Emit",
        "Assembly.Load",
        "Activator.CreateInstance",
        " unsafe ",
        " dynamic ",
    };

    private readonly string _assemblyPath;
    private readonly string _sourceRoot;
    private readonly SurfacePolicy _policy;
    private readonly MetadataNames _names = new();
    private readonly HashSet<string> _allowedGameTypes;
    private readonly HashSet<string> _allowedGameMembers;
    private readonly HashSet<string> _allowedNetworkTypes;
    private readonly HashSet<string> _allowedNetworkMembers;
    private readonly HashSet<string> _allowedFilesystemTypes;
    private readonly HashSet<string> _allowedFilesystemMembers;
    private readonly HashSet<string> _networkOwners;
    private readonly HashSet<string> _routeLiterals;
    private readonly HashSet<string> _observedGameMembers = new(StringComparer.Ordinal);
    private readonly HashSet<string> _observedNetworkMembers = new(StringComparer.Ordinal);
    private readonly HashSet<string> _observedFilesystemMembers = new(StringComparer.Ordinal);
    private readonly HashSet<string> _observedReflectionMembers = new(StringComparer.Ordinal);
    private readonly HashSet<string> _observedConfigurationPathComponents = new(StringComparer.Ordinal);
    private readonly HashSet<string> _validatedNetworkStateTypes = new(StringComparer.Ordinal);

    private MetadataReader _reader = null!;
    private PEReader _peReader = null!;
    private readonly Dictionary<MethodDefinitionHandle, string> _methodIdentities = new();
    private readonly Dictionary<MethodDefinitionHandle, string> _logicalOwners = new();
    private readonly Dictionary<string, MethodDefinitionHandle> _methodsByIdentity = new(StringComparer.Ordinal);
    private readonly Dictionary<string, TypeDefinitionHandle> _typesByName = new(StringComparer.Ordinal);
    private readonly HashSet<string> _observedRoutes = new(StringComparer.Ordinal);
    private int _initializerAttributeCount;
    private int _checkedMethodBodies;
    private bool _observedEnvironmentMember;
    private bool _observedFixedTimeEquals;
    private string _configurationStructureSha256 = string.Empty;
    private string _buildGuardStructureSha256 = string.Empty;
    private string _transportStructureSha256 = string.Empty;
    private string _sourceProjectionSha256 = string.Empty;
    private string _releaseAssemblyStructureSha256 = string.Empty;

    public ProductionSurfaceVerifier(string assemblyPath, string sourceRoot, SurfacePolicy policy)
    {
        _assemblyPath = assemblyPath;
        _sourceRoot = sourceRoot;
        _policy = policy;
        _allowedGameTypes = new HashSet<string>(policy.GameGodot.AllowedTypes, StringComparer.Ordinal);
        _allowedGameMembers = new HashSet<string>(
            policy.GameGodot.AllowedMembers.Select(NormalizePolicyMember),
            StringComparer.Ordinal);
        _allowedNetworkTypes = new HashSet<string>(policy.Network.AllowedTypes, StringComparer.Ordinal);
        _allowedNetworkMembers = new HashSet<string>(
            policy.Network.AllowedMembers.Select(NormalizePolicyMember),
            StringComparer.Ordinal);
        _allowedFilesystemTypes = new HashSet<string>(policy.Filesystem.AllowedTypes, StringComparer.Ordinal);
        _allowedFilesystemMembers = new HashSet<string>(
            policy.Filesystem.AllowedMembers.Select(NormalizePolicyMember),
            StringComparer.Ordinal);
        _networkOwners = new HashSet<string>(policy.Network.Owners, StringComparer.Ordinal);
        _routeLiterals = new HashSet<string>(policy.AllowedRouteLiterals, StringComparer.Ordinal);
    }

    public VerificationReport Verify()
    {
        byte[] assemblyBytes = ReadAssembly();
        string assemblySha256 = Convert.ToHexString(SHA256.HashData(assemblyBytes)).ToLowerInvariant();
        using var stream = new MemoryStream(assemblyBytes, writable: false);
        using var peReader = new PEReader(stream, PEStreamOptions.LeaveOpen);
        _peReader = peReader;
        if (!peReader.HasMetadata || peReader.PEHeaders.CorHeader is null)
        {
            throw new VerificationException("assembly_not_managed");
        }

        _reader = peReader.GetMetadataReader(MetadataReaderOptions.None);
        if (!_reader.IsAssembly)
        {
            throw new VerificationException("assembly_definition_missing");
        }

        AssemblyDefinition assemblyDefinition = _reader.GetAssemblyDefinition();
        string assemblyName = _reader.GetString(assemblyDefinition.Name);
        if (!string.Equals(assemblyName, _policy.ProductionAssembly, StringComparison.Ordinal))
        {
            throw new VerificationException("assembly_name");
        }

        if (assemblyDefinition.Version != new Version(0, 8, 0, 0))
        {
            throw new VerificationException("assembly_version");
        }

        IndexDefinitions();
        VerifyAssemblyReferences();
        VerifyTypeReferences();
        VerifyReferenceTables();
        IndexAsyncStateMachines();
        VerifyDefinitionsAndSignatures();
        VerifyMethodBodies();
        VerifyCustomAttributesAndInitializer();
        VerifyRequiredOwnersAndCalls();
        VerifyRoutes();
        VerifySourceSurface();
        VerifyReleaseStructure();

        return new VerificationReport(
            assemblyName,
            assemblySha256,
            _observedRoutes.Count,
            _checkedMethodBodies,
            _configurationStructureSha256,
            _buildGuardStructureSha256,
            _transportStructureSha256,
            _sourceProjectionSha256,
            _releaseAssemblyStructureSha256);
    }

    private byte[] ReadAssembly()
    {
        var info = new FileInfo(_assemblyPath);
        if (info.LinkTarget is not null || !info.Exists ||
            (info.Attributes & (FileAttributes.Directory | FileAttributes.ReparsePoint | FileAttributes.Device)) != 0 ||
            info.Length <= 0 || info.Length > 64 * 1024 * 1024)
        {
            throw new VerificationException("assembly_boundary");
        }

        byte[] data = File.ReadAllBytes(_assemblyPath);
        info.Refresh();
        if (info.LinkTarget is not null || !info.Exists || info.Length != data.Length)
        {
            throw new VerificationException("assembly_changed");
        }

        return data;
    }

    private void IndexDefinitions()
    {
        foreach (TypeDefinitionHandle handle in _reader.TypeDefinitions)
        {
            string name = MetadataNames.TypeDefinitionName(_reader, handle);
            if (!_typesByName.TryAdd(name, handle))
            {
                throw new VerificationException("duplicate_type_identity");
            }

            RejectForbiddenName(name);
            TypeDefinition definition = _reader.GetTypeDefinition(handle);
            foreach (MethodDefinitionHandle methodHandle in definition.GetMethods())
            {
                string identity = MetadataNames.MethodDefinitionIdentity(_reader, methodHandle, _names);
                _methodIdentities.Add(methodHandle, identity);
                _logicalOwners.Add(methodHandle, identity);
                if (!_methodsByIdentity.TryAdd(identity, methodHandle))
                {
                    throw new VerificationException("duplicate_method_identity");
                }

                RejectForbiddenName(identity);
            }
        }
    }

    private void VerifyAssemblyReferences()
    {
        var observedExternal = new HashSet<string>(StringComparer.Ordinal);
        var forbidden = new HashSet<string>(_policy.ForbiddenAssemblyReferences, StringComparer.Ordinal);
        foreach (AssemblyReferenceHandle handle in _reader.AssemblyReferences)
        {
            AssemblyReference reference = _reader.GetAssemblyReference(handle);
            string name = _reader.GetString(reference.Name);
            if (forbidden.Contains(name))
            {
                throw new VerificationException("forbidden_assembly_reference");
            }

            if (IsFrameworkAssembly(name))
            {
                continue;
            }

            if (!_policy.AllowedDirectNonframeworkReferences.Contains(name, StringComparer.Ordinal) ||
                !observedExternal.Add(name))
            {
                throw new VerificationException("unexpected_assembly_reference");
            }
        }

        if (!observedExternal.SetEquals(_policy.AllowedDirectNonframeworkReferences))
        {
            throw new VerificationException("missing_pinned_assembly_reference");
        }
    }

    private void VerifyTypeReferences()
    {
        foreach (TypeReferenceHandle handle in _reader.TypeReferences)
        {
            string name = MetadataNames.TypeReferenceName(_reader, handle);
            string assembly = MetadataNames.TypeReferenceAssembly(_reader, handle);
            RejectForbiddenName(name);

            if (_policy.DefaultDeny.ExternalAssemblies.Contains(assembly, StringComparer.Ordinal))
            {
                if (!_allowedGameTypes.Contains(name))
                {
                    throw new VerificationException("game_type_forbidden");
                }

                continue;
            }

            if (IsNamespaceFamily(name, _policy.Network.NamespaceFamily))
            {
                if (!_allowedNetworkTypes.Contains(name))
                {
                    throw new VerificationException("network_type_forbidden");
                }

                continue;
            }

            if (IsNamespaceFamily(name, _policy.Filesystem.NamespaceFamily))
            {
                if (!_allowedFilesystemTypes.Contains(name))
                {
                    throw new VerificationException("filesystem_type_forbidden");
                }

                continue;
            }

            foreach (string prefix in _policy.ForbiddenNamespacePrefixes)
            {
                if (IsNamespaceFamily(name, prefix))
                {
                    throw new VerificationException("forbidden_namespace_reference");
                }
            }
        }
    }

    private void VerifyDefinitionsAndSignatures()
    {
        foreach (TypeDefinitionHandle typeHandle in _reader.TypeDefinitions)
        {
            TypeDefinition type = _reader.GetTypeDefinition(typeHandle);
            string typeName = MetadataNames.TypeDefinitionName(_reader, typeHandle);

            if ((type.Attributes & TypeAttributes.Import) != 0)
            {
                throw new VerificationException("native_type_import");
            }

            if (!type.BaseType.IsNil)
            {
                string baseType = MetadataNames.EntityTypeName(_reader, type.BaseType, _names);
                VerifySignatureType(baseType, typeName, "base_type");
            }

            foreach (InterfaceImplementationHandle interfaceHandle in type.GetInterfaceImplementations())
            {
                string interfaceType = MetadataNames.EntityTypeName(
                    _reader,
                    _reader.GetInterfaceImplementation(interfaceHandle).Interface,
                    _names);
                VerifySignatureType(interfaceType, typeName, "interface_type");
            }

            foreach (FieldDefinitionHandle fieldHandle in type.GetFields())
            {
                FieldDefinition field = _reader.GetFieldDefinition(fieldHandle);
                string fieldName = _reader.GetString(field.Name);
                string fieldType = field.DecodeSignature(_names, null);
                VerifySignatureType(fieldType, typeName + "." + fieldName, "field_type");
                VerifyPinnedAdapterField(typeName, fieldName, fieldType, field.Attributes);
            }

            foreach (MethodDefinitionHandle methodHandle in type.GetMethods())
            {
                MethodDefinition method = _reader.GetMethodDefinition(methodHandle);
                if ((method.Attributes & MethodAttributes.PinvokeImpl) != 0 ||
                    (method.ImplAttributes & (MethodImplAttributes.Native | MethodImplAttributes.Unmanaged)) != 0)
                {
                    throw new VerificationException("native_method");
                }

                MethodSignature<string> signature = method.DecodeSignature(_names, null);
                string owner = _methodIdentities[methodHandle];
                VerifySignatureType(signature.ReturnType, owner, "method_return");
                foreach (string parameter in signature.ParameterTypes)
                {
                    VerifySignatureType(parameter, owner, "method_parameter");
                }
            }
        }
    }

    private void VerifyReferenceTables()
    {
        string environmentMember = NormalizePolicyMember(_policy.Environment.AllowedMember);

        foreach (MemberReferenceHandle handle in _reader.MemberReferences)
        {
            MemberReference reference = _reader.GetMemberReference(handle);
            string declaringType = MetadataNames.ParentTypeName(_reader, reference.Parent, _names);
            string identity = MetadataNames.MemberReferenceIdentity(_reader, handle, _names);
            RejectForbiddenName(identity);

            if (ContainsGameType(declaringType))
            {
                bool genericCallableDefinition =
                    declaringType == "Godot.Callable" &&
                    _reader.StringComparer.Equals(reference.Name, "From") &&
                    reference.GetKind() == MemberReferenceKind.Method &&
                    reference.DecodeMethodSignature(_names, null).GenericParameterCount == 1;
                if (!_allowedGameMembers.Contains(identity) && !genericCallableDefinition)
                {
                    throw new VerificationException("game_member_reference_forbidden");
                }

                continue;
            }

            if (IsNamespaceFamily(declaringType, _policy.Network.NamespaceFamily))
            {
                if (!_allowedNetworkMembers.Contains(identity))
                {
                    string code = declaringType == "System.Net.IPAddress"
                        ? "listener_address_constant"
                        : "network_member_reference_forbidden";
                    throw new VerificationException(code);
                }

                continue;
            }

            if (IsNamespaceFamily(declaringType, _policy.Filesystem.NamespaceFamily))
            {
                if (!IsPotentialFilesystemMember(identity))
                {
                    throw new VerificationException("filesystem_member_reference_forbidden");
                }

                continue;
            }

            if (declaringType == "System.Environment" && identity != environmentMember)
            {
                throw new VerificationException("environment_member_reference_forbidden");
            }

            if (declaringType == "System.Security.Cryptography.CryptographicOperations" &&
                _reader.StringComparer.Equals(reference.Name, "FixedTimeEquals") &&
                identity != FixedTimeEquals)
            {
                throw new VerificationException("fixed_time_member_reference_forbidden");
            }
        }

        int methodSpecificationCount = _reader.GetTableRowCount(TableIndex.MethodSpec);
        for (int row = 1; row <= methodSpecificationCount; row++)
        {
            MethodSpecificationHandle handle = MetadataTokens.MethodSpecificationHandle(row);
            ResolvedMethod method = ResolveCalledMethod(handle);
            if (ContainsGameType(method.DeclaringType))
            {
                if (method.Identity != "Godot.Callable.From(System.Action)" ||
                    !_allowedGameMembers.Contains(method.Identity))
                {
                    throw new VerificationException("game_method_spec_forbidden");
                }

                continue;
            }

            if (IsNamespaceFamily(method.DeclaringType, _policy.Network.NamespaceFamily) ||
                IsNamespaceFamily(method.DeclaringType, _policy.Filesystem.NamespaceFamily))
            {
                throw new VerificationException("default_deny_method_spec");
            }
        }
    }

    private void VerifyPinnedAdapterField(
        string typeName,
        string fieldName,
        string fieldType,
        FieldAttributes attributes)
    {
        if (!ContainsGameType(fieldType))
        {
            return;
        }

        bool exact = typeName == "Sts2AgentBridge.Adapters.Threading.GodotFrameDispatcher" &&
            ((fieldName == "_tree" && fieldType == "Godot.SceneTree") ||
             (fieldName == "_callable" && fieldType == "Godot.Callable")) &&
            (attributes & FieldAttributes.FieldAccessMask) == FieldAttributes.Private &&
            (attributes & FieldAttributes.Static) == 0;
        string fieldIdentity = typeName + "." + fieldName + ":" + fieldType;
        exact = exact ||
            Array.IndexOf(_policy.GameGodot.AllowedPrivateInstanceFields, fieldIdentity) >= 0 &&
            (attributes & FieldAttributes.FieldAccessMask) == FieldAttributes.Private &&
            (attributes & FieldAttributes.Static) == 0;
        if (!exact)
        {
            throw new VerificationException("game_field_forbidden");
        }
    }

    private void IndexAsyncStateMachines()
    {
        var stateOwners = new Dictionary<TypeDefinitionHandle, MethodDefinitionHandle>();
        foreach ((MethodDefinitionHandle methodHandle, string methodIdentity) in _methodIdentities)
        {
            MethodDefinition method = _reader.GetMethodDefinition(methodHandle);
            foreach (CustomAttributeHandle attributeHandle in method.GetCustomAttributes())
            {
                CustomAttribute attribute = _reader.GetCustomAttribute(attributeHandle);
                if (CustomAttributeType(attribute) != AsyncStateMachineType)
                {
                    continue;
                }

                string stateMachineName = ReadSingleTypeAttributeArgument(attribute);
                if (!_typesByName.TryGetValue(stateMachineName, out TypeDefinitionHandle stateType))
                {
                    throw new VerificationException("async_state_machine_unresolved");
                }

                if (!stateOwners.TryAdd(stateType, methodHandle))
                {
                    throw new VerificationException("async_state_machine_reused");
                }

                TypeDefinition state = _reader.GetTypeDefinition(stateType);
                string outerTypeName = MetadataNames.TypeDefinitionName(_reader, method.GetDeclaringType());
                string methodName = _reader.GetString(method.Name);
                string expectedStatePrefix = outerTypeName + "+<" + methodName + ">d__";
                if (state.GetDeclaringType() != method.GetDeclaringType() ||
                    !HasCustomAttribute(state.GetCustomAttributes(), CompilerGeneratedType) ||
                    !stateMachineName.StartsWith(expectedStatePrefix, StringComparison.Ordinal))
                {
                    throw new VerificationException("async_state_machine_shape");
                }

                MethodDefinitionHandle? moveNext = null;
                foreach (MethodDefinitionHandle candidate in state.GetMethods())
                {
                    MethodDefinition candidateMethod = _reader.GetMethodDefinition(candidate);
                    if (_reader.StringComparer.Equals(candidateMethod.Name, "MoveNext"))
                    {
                        if (moveNext is not null)
                        {
                            throw new VerificationException("async_state_machine_move_next_count");
                        }

                        MethodSignature<string> signature = candidateMethod.DecodeSignature(_names, null);
                        if (signature.ReturnType != "System.Void" || signature.ParameterTypes.Length != 0)
                        {
                            throw new VerificationException("async_state_machine_move_next_signature");
                        }

                        moveNext = candidate;
                    }
                }

                if (moveNext is null ||
                    !_logicalOwners.TryGetValue(moveNext.Value, out string? existingOwner) ||
                    existingOwner != _methodIdentities[moveNext.Value])
                {
                    throw new VerificationException("async_state_machine_move_next_missing");
                }

                _logicalOwners[moveNext.Value] = methodIdentity;
                if (_networkOwners.Contains(methodIdentity))
                {
                    _validatedNetworkStateTypes.Add(stateMachineName);
                }
            }
        }
    }

    private void VerifyCustomAttributesAndInitializer()
    {
        foreach (CustomAttributeHandle handle in _reader.CustomAttributes)
        {
            CustomAttribute attribute = _reader.GetCustomAttribute(handle);
            string typeName = CustomAttributeType(attribute);
            if (!ContainsGameType(typeName))
            {
                continue;
            }

            string constructor = CustomAttributeConstructor(attribute);
            if (typeName != ModInitializerType ||
                constructor != ModInitializerType + "..ctor(System.String)" ||
                attribute.Parent.Kind != HandleKind.TypeDefinition ||
                MetadataNames.TypeDefinitionName(_reader, (TypeDefinitionHandle)attribute.Parent) !=
                    _policy.GameGodot.InitializerOwner ||
                ReadSingleStringAttributeArgument(attribute) != _policy.GameGodot.InitializerMethod)
            {
                throw new VerificationException("initializer_attribute_invalid");
            }

            _initializerAttributeCount++;
            _observedGameMembers.Add(constructor);
        }

        if (_initializerAttributeCount != 1 ||
            !_typesByName.TryGetValue(_policy.GameGodot.InitializerOwner, out TypeDefinitionHandle initializerType))
        {
            throw new VerificationException("initializer_attribute_count");
        }

        TypeDefinition type = _reader.GetTypeDefinition(initializerType);
        TypeAttributes required = TypeAttributes.Public | TypeAttributes.Abstract | TypeAttributes.Sealed;
        if ((type.Attributes & required) != required)
        {
            throw new VerificationException("initializer_type_shape");
        }

        int matchingMethods = 0;
        foreach (MethodDefinitionHandle handle in type.GetMethods())
        {
            MethodDefinition method = _reader.GetMethodDefinition(handle);
            if (!_reader.StringComparer.Equals(method.Name, _policy.GameGodot.InitializerMethod))
            {
                continue;
            }

            matchingMethods++;
            MethodSignature<string> signature = method.DecodeSignature(_names, null);
            MethodAttributes shape = MethodAttributes.Public | MethodAttributes.Static;
            if ((method.Attributes & shape) != shape ||
                signature.ReturnType != "System.Void" ||
                signature.ParameterTypes.Length != 0)
            {
                throw new VerificationException("initializer_method_shape");
            }
        }

        if (matchingMethods != 1)
        {
            throw new VerificationException("initializer_method_count");
        }
    }

    private void VerifyMethodBodies()
    {
        foreach ((MethodDefinitionHandle handle, string physicalOwner) in _methodIdentities)
        {
            MethodDefinition method = _reader.GetMethodDefinition(handle);
            if (method.RelativeVirtualAddress == 0)
            {
                continue;
            }

            MethodBodyBlock body;
            try
            {
                body = _peReader.GetMethodBody(method.RelativeVirtualAddress);
            }
            catch (BadImageFormatException)
            {
                throw new VerificationException("unresolved_method_body");
            }

            _checkedMethodBodies++;
            string logicalOwner = _logicalOwners[handle];
            if (IsReaderOwner(logicalOwner) &&
                body.ExceptionRegions.Any(region => region.Kind != ExceptionRegionKind.Finally))
            {
                throw new VerificationException("reader_exception_handler_forbidden");
            }

            VerifyLocalSignature(body, logicalOwner);
            byte[]? ilBytes = body.GetILBytes();
            if (ilBytes is null)
            {
                throw new VerificationException("unresolved_method_body");
            }

            IReadOnlyList<IlInstruction> instructions = IlDecoder.Decode(ilBytes);
            VerifyInstructions(physicalOwner, logicalOwner, instructions);
        }
    }

    private void VerifyLocalSignature(MethodBodyBlock body, string owner)
    {
        if (body.LocalSignature.IsNil)
        {
            return;
        }

        ImmutableArray<string> locals;
        try
        {
            StandaloneSignature signature = _reader.GetStandaloneSignature(body.LocalSignature);
            locals = signature.DecodeLocalSignature(_names, null);
        }
        catch (BadImageFormatException)
        {
            throw new VerificationException("unresolved_local_signature");
        }

        foreach (string local in locals)
        {
            VerifySignatureType(local, owner, "local_type");
        }
    }

    private void VerifyInstructions(
        string physicalOwner,
        string logicalOwner,
        IReadOnlyList<IlInstruction> instructions)
    {
        int lastLinkTargetOffset = -1;
        for (int index = 0; index < instructions.Count; index++)
        {
            IlInstruction instruction = instructions[index];
            if (instruction.MetadataToken is null)
            {
                continue;
            }

            if (instruction.OpCode == 0x0072)
            {
                VerifyUserString(instruction.MetadataToken.Value, logicalOwner);
                continue;
            }

            if (instruction.OpCode == 0x0029)
            {
                throw new VerificationException("indirect_call_forbidden");
            }

            EntityHandle target = IlDecoder.RequireEntityHandle(instruction.MetadataToken.Value);
            if (instruction.IsCall)
            {
                ResolvedMethod call = ResolveCalledMethod(target);
                VerifyCall(physicalOwner, logicalOwner, call, instructions, index, ref lastLinkTargetOffset);
                continue;
            }

            if (instruction.IsFieldOperation)
            {
                ResolvedMember field = ResolveField(target);
                VerifyFieldAccess(logicalOwner, field);
                continue;
            }

            if (instruction.IsTypeOperation || instruction.IsLoadToken)
            {
                VerifyTypeOperation(logicalOwner, instruction, target);
            }
        }
    }

    private void VerifyCall(
        string physicalOwner,
        string logicalOwner,
        ResolvedMethod call,
        IReadOnlyList<IlInstruction> instructions,
        int instructionIndex,
        ref int lastLinkTargetOffset)
    {
        RejectForbiddenName(call.Identity);

        if (ContainsGameType(call.DeclaringType))
        {
            VerifyGameCall(logicalOwner, call, instructions, instructionIndex);
            return;
        }

        if (IsNamespaceFamily(call.DeclaringType, _policy.Network.NamespaceFamily))
        {
            if (!_allowedNetworkMembers.Contains(call.Identity) || !_networkOwners.Contains(logicalOwner))
            {
                throw new VerificationException("network_member_or_owner_forbidden");
            }

            if (physicalOwner == logicalOwner)
            {
                throw new VerificationException("network_call_not_async_state_machine");
            }

            VerifyNetworkConstants(call.Identity, instructions, instructionIndex);
            _observedNetworkMembers.Add(call.Identity);
            return;
        }

        if (IsNamespaceFamily(call.DeclaringType, _policy.Filesystem.NamespaceFamily))
        {
            string filesystemMember = NormalizeFilesystemMember(call.Identity, logicalOwner);
            if (!_allowedFilesystemMembers.Contains(filesystemMember) ||
                !IsFilesystemOwner(logicalOwner, filesystemMember))
            {
                throw new VerificationException("filesystem_member_or_owner_forbidden");
            }

            if (filesystemMember.EndsWith(".get_LinkTarget()", StringComparison.Ordinal))
            {
                lastLinkTargetOffset = instructions[instructionIndex].Offset;
            }
            else if (RequiresPriorLinkCheck(filesystemMember) &&
                lastLinkTargetOffset < 0)
            {
                throw new VerificationException("filesystem_link_check_order");
            }

            if (filesystemMember ==
                "System.IO.FileStream..ctor(System.String,System.IO.FileMode,System.IO.FileAccess,System.IO.FileShare)")
            {
                RequireTrailingConstants(
                    instructions,
                    instructionIndex,
                    "filesystem_open_constants",
                    3,
                    1,
                    1);
            }

            _observedFilesystemMembers.Add(filesystemMember);
            return;
        }

        if (call.DeclaringType == "System.Environment")
        {
            string allowed = NormalizePolicyMember(_policy.Environment.AllowedMember);
            if (call.Identity != allowed ||
                !logicalOwner.StartsWith(_policy.Environment.Owner + ".", StringComparison.Ordinal))
            {
                throw new VerificationException("environment_member_or_owner_forbidden");
            }

            RequireTrailingConstants(
                instructions,
                instructionIndex,
                "environment_constants",
                40,
                16_384);
            _observedEnvironmentMember = true;
            return;
        }

        if (call.DeclaringType == "System.Type" ||
            IsNamespaceFamily(call.DeclaringType, "System.Reflection"))
        {
            var allowed = new HashSet<string>(
                _policy.Reflection.AllowedMembers.Select(NormalizePolicyMember),
                StringComparer.Ordinal);
            if (!allowed.Contains(call.Identity) || logicalOwner != _policy.Reflection.Owner)
            {
                throw new VerificationException("reflection_member_or_owner_forbidden");
            }

            _observedReflectionMembers.Add(call.Identity);
            return;
        }

        if (call.DeclaringType == "System.Security.Cryptography.CryptographicOperations" &&
            call.Name == "FixedTimeEquals")
        {
            if (call.Identity != FixedTimeEquals || logicalOwner != FixedTimeOwner)
            {
                throw new VerificationException("fixed_time_member_or_owner_forbidden");
            }

            _observedFixedTimeEquals = true;
        }
    }

    private void VerifyGameCall(
        string owner,
        ResolvedMethod call,
        IReadOnlyList<IlInstruction> instructions,
        int instructionIndex)
    {
        if (!_allowedGameMembers.Contains(call.Identity))
        {
            throw new VerificationException("game_member_forbidden");
        }

        string expectedOwner;
        if (call.Identity == "Godot.GD.Print(System.String)")
        {
            expectedOwner = _policy.GameGodot.LoggerInfoOwner;
        }
        else if (call.Identity == "Godot.GD.PrintErr(System.String)")
        {
            expectedOwner = _policy.GameGodot.LoggerErrorOwner;
        }
        else if (call.Identity is
            "Godot.Engine.GetMainLoop()" or
            "Godot.Callable.From(System.Action)" or
            "Godot.GodotObject.Connect(Godot.StringName,Godot.Callable,System.UInt32)")
        {
            expectedOwner = _policy.GameGodot.DispatcherConstructorOwner;
        }
        else if (call.Identity == "Godot.GodotObject.Disconnect(Godot.StringName,Godot.Callable)")
        {
            expectedOwner = _policy.GameGodot.DispatcherDisposeOwner;
        }
        else if (call.Identity == ModInitializerType + "..ctor(System.String)")
        {
            throw new VerificationException("initializer_constructor_called");
        }
        else
        {
            if (!IsGameAccessOwner(owner))
            {
                throw new VerificationException("game_member_wrong_owner");
            }
            expectedOwner = owner;
        }

        if (owner != expectedOwner)
        {
            throw new VerificationException("game_member_wrong_owner");
        }

        if (call.Identity ==
            "Godot.GodotObject.Connect(Godot.StringName,Godot.Callable,System.UInt32)")
        {
            RequireTrailingConstants(
                instructions,
                instructionIndex,
                "godot_connect_flags_constant",
                0);
        }

        _observedGameMembers.Add(call.Identity);
    }

    private void VerifyFieldAccess(string owner, ResolvedMember field)
    {
        RejectForbiddenName(field.Identity);
        if (ContainsGameType(field.DeclaringType))
        {
            bool dispatcherField = field.Identity == "Godot.SceneTree+SignalName.ProcessFrame" &&
                (owner == _policy.GameGodot.DispatcherConstructorOwner ||
                 owner == _policy.GameGodot.DispatcherDisposeOwner);
            bool boundedGameField = field.Identity != "Godot.SceneTree+SignalName.ProcessFrame" &&
                IsGameAccessOwner(owner);
            if (!_allowedGameMembers.Contains(field.Identity) ||
                (!dispatcherField && !boundedGameField))
            {
                throw new VerificationException("game_field_or_owner_forbidden");
            }

            _observedGameMembers.Add(field.Identity);
            return;
        }

        if (IsNamespaceFamily(field.DeclaringType, _policy.Network.NamespaceFamily))
        {
            if (!_allowedNetworkMembers.Contains(field.Identity) || !_networkOwners.Contains(owner))
            {
                throw new VerificationException("network_field_or_owner_forbidden");
            }

            _observedNetworkMembers.Add(field.Identity);
            return;
        }

        if (IsNamespaceFamily(field.DeclaringType, _policy.Filesystem.NamespaceFamily))
        {
            if (!_allowedFilesystemMembers.Contains(field.Identity) || !IsFilesystemOwner(owner, field.Identity))
            {
                throw new VerificationException("filesystem_field_or_owner_forbidden");
            }


            _observedFilesystemMembers.Add(field.Identity);
        }
    }

    private void VerifyTypeOperation(string owner, IlInstruction instruction, EntityHandle target)
    {
        string typeName;
        if (target.Kind is HandleKind.TypeDefinition or HandleKind.TypeReference or HandleKind.TypeSpecification)
        {
            typeName = MetadataNames.EntityTypeName(_reader, target, _names);
        }
        else if (instruction.IsLoadToken && target.Kind == HandleKind.MethodDefinition)
        {
            throw new VerificationException("reflection_method_token_forbidden");
        }
        else if (instruction.IsLoadToken && target.Kind == HandleKind.MemberReference)
        {
            throw new VerificationException("reflection_member_token_forbidden");
        }
        else
        {
            throw new VerificationException("unresolved_type_operation");
        }

        if (!ContainsGameType(typeName))
        {
            if (IsNamespaceFamily(typeName, _policy.Network.NamespaceFamily) &&
                !_allowedNetworkTypes.Contains(StripTypeDecorations(typeName)))
            {
                throw new VerificationException("network_type_operation_forbidden");
            }

            if (IsNamespaceFamily(typeName, _policy.Filesystem.NamespaceFamily) &&
                !_allowedFilesystemTypes.Contains(StripTypeDecorations(typeName)))
            {
                throw new VerificationException("filesystem_type_operation_forbidden");
            }

            return;
        }

        if (instruction.IsIsInst && typeName == _policy.GameGodot.ReaderIsinstType &&
            owner == _policy.GameGodot.ReaderOwner)
        {
            return;
        }

        if (instruction.IsIsInst && typeName == _policy.GameGodot.DecisionReaderIsinstType &&
            owner == _policy.GameGodot.DecisionReaderOwner)
        {
            return;
        }

        if (instruction.IsIsInst &&
            owner == _policy.GameGodot.RewardDecisionReaderOwner &&
            _policy.GameGodot.RewardDecisionReaderIsinstTypes.Contains(typeName, StringComparer.Ordinal))
        {
            return;
        }

        if (instruction.IsIsInst &&
            owner == _policy.GameGodot.RewardActionOwner &&
            typeName == _policy.GameGodot.RewardActionIsinstType)
        {
            return;
        }

        if (instruction.IsIsInst &&
            owner == _policy.GameGodot.MapDecisionReaderOwner &&
            typeName == _policy.GameGodot.MapDecisionReaderIsinstType)
        {
            return;
        }

        if (instruction.IsIsInst &&
            owner == _policy.GameGodot.MapActionOwner &&
            typeName == _policy.GameGodot.MapActionIsinstType)
        {
            return;
        }

        if (instruction.IsIsInst && IsAdditionalGameOwnerType(owner))
        {
            return;
        }

        if (instruction.OpCode is 0x008d or 0x00a4 && typeName == "Godot.Variant" &&
            owner.StartsWith(
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRewardActionApplier.",
                StringComparison.Ordinal))
        {
            return;
        }

        if (instruction.OpCode == 0xfe16 && IsAdditionalGameOwnerType(owner))
        {
            return;
        }

        if (instruction.IsLoadToken && typeName == _policy.Reflection.TypeToken &&
            owner == _policy.Reflection.Owner)
        {
            return;
        }

        if ((instruction.OpCode == 0x0074 || instruction.IsIsInst) &&
            typeName == "Godot.SceneTree" &&
            owner == _policy.GameGodot.DispatcherConstructorOwner)
        {
            return;
        }

        if (instruction.OpCode == 0xfe16 && owner == _policy.GameGodot.DecisionReaderOwner &&
            typeName is
                "MegaCrit.Sts2.Core.MonsterMoves.Intents.IntentType" or
                "MegaCrit.Sts2.Core.Entities.Cards.CardType" or
                "MegaCrit.Sts2.Core.Entities.Cards.TargetType")
        {
            return;
        }
        if (instruction.OpCode == 0xfe16 &&
            owner == _policy.GameGodot.RewardDecisionReaderOwner &&
            typeName == "System.Collections.Generic.List<MegaCrit.Sts2.Core.Rewards.Reward>")
        {
            return;
        }
        throw new VerificationException("game_type_operation_forbidden");
    }

    private void VerifyNetworkConstants(
        string member,
        IReadOnlyList<IlInstruction> instructions,
        int callIndex)
    {
        if (member == "System.Net.Sockets.TcpListener..ctor(System.Net.IPAddress,System.Int32)")
        {
            RequireTrailingConstants(instructions, callIndex, "listener_port_constant", 43117);
        }
        else if (member == "System.Net.Sockets.TcpListener.Start(System.Int32)")
        {
            RequireTrailingConstants(instructions, callIndex, "listener_backlog_constant", 8);
        }
        else if (member.Contains(".ReceiveAsync(", StringComparison.Ordinal) ||
            member.Contains(".SendAsync(", StringComparison.Ordinal))
        {
            RequireRecentConstant(instructions, callIndex, 0, 6);
        }
        else if (member == "System.Net.Sockets.Socket.Shutdown(System.Net.Sockets.SocketShutdown)")
        {
            RequireTrailingConstants(instructions, callIndex, "socket_shutdown_constant", 2);
        }
    }

    private void VerifySignatureType(string type, string owner, string category)
    {
        foreach (string gameType in _allowedGameTypes)
        {
            if (!ContainsExactType(type, gameType))
            {
                continue;
            }

            bool allowedOwner = IsGameAccessOwner(owner) ||
                owner.StartsWith(
                    "Sts2AgentBridge.Adapters.Threading.GodotFrameDispatcher.",
                    StringComparison.Ordinal);
            if (!allowedOwner)
            {
                throw new VerificationException("game_signature_type_wrong_owner");
            }
        }

        if (ContainsNamespaceFamily(type, _policy.Network.NamespaceFamily))
        {
            bool allowedOwner = _networkOwners.Contains(owner) ||
                _validatedNetworkStateTypes.Any(stateType =>
                    owner.StartsWith(stateType + ".", StringComparison.Ordinal));
            if (!allowedOwner)
            {
                throw new VerificationException("network_signature_type_wrong_owner");
            }
        }

        if (ContainsNamespaceFamily(type, _policy.Filesystem.NamespaceFamily))
        {
            bool allowedOwner = owner.StartsWith(_policy.Filesystem.ConfigurationOwner + ".", StringComparison.Ordinal) ||
                owner.StartsWith(_policy.Filesystem.BuildGuardOwner + ".", StringComparison.Ordinal);
            if (!allowedOwner)
            {
                throw new VerificationException("filesystem_signature_type_wrong_owner");
            }
        }

        _ = category;
    }

    private void VerifyRequiredOwnersAndCalls()
    {
        string[] requiredMethods =
        {
            _policy.GameGodot.ReaderOwner,
            _policy.GameGodot.DecisionReaderOwner,
            _policy.GameGodot.CombatActionOwner,
            _policy.GameGodot.RewardDecisionReaderOwner,
            _policy.GameGodot.RewardActionOwner,
            _policy.GameGodot.MapDecisionReaderOwner,
            _policy.GameGodot.MapActionOwner,
            _policy.GameGodot.DispatcherConstructorOwner,
            _policy.GameGodot.DispatcherDisposeOwner,
            _policy.GameGodot.LoggerInfoOwner,
            _policy.GameGodot.LoggerErrorOwner,
            _policy.Reflection.Owner,
            FixedTimeOwner,
        };
        foreach (string method in requiredMethods)
        {
            if (!_methodsByIdentity.ContainsKey(method))
            {
                throw new VerificationException("required_owner_missing");
            }
        }

        foreach (string owner in _networkOwners)
        {
            if (!_methodsByIdentity.TryGetValue(owner, out MethodDefinitionHandle outer) ||
                !_logicalOwners.Any(pair => pair.Value == owner && pair.Key != outer))
            {
                throw new VerificationException("network_async_owner_missing");
            }
        }

        VerifyReflectionSequence();
        VerifyPinnedBuildGuardStructure();
        if (!_observedGameMembers.SetEquals(_allowedGameMembers))
        {
            throw new VerificationException("required_game_member_missing");
        }

        if (!_observedNetworkMembers.SetEquals(_allowedNetworkMembers))
        {
            throw new VerificationException("required_network_member_missing");
        }

        if (!_observedFilesystemMembers.SetEquals(_allowedFilesystemMembers))
        {
            throw new VerificationException("required_filesystem_member_missing");
        }

        var requiredReflection = new HashSet<string>(
            _policy.Reflection.AllowedMembers.Select(NormalizePolicyMember),
            StringComparer.Ordinal);
        if (!_observedReflectionMembers.SetEquals(requiredReflection) ||
            !_observedEnvironmentMember ||
            !_observedFixedTimeEquals)
        {
            throw new VerificationException("required_security_member_missing");
        }

        var requiredPathComponents = new HashSet<string>(
            new[]
            {
                "Library",
                "Application Support",
                "Sts2AgentBridge",
                "r0a",
                "config.json",
                "credential.hex",
            },
            StringComparer.Ordinal);
        if (!_observedConfigurationPathComponents.SetEquals(requiredPathComponents))
        {
            throw new VerificationException("configuration_path_provenance");
        }

        VerifyConfigurationStructure();
        VerifyTransportStructure();
    }

    private bool IsReaderOwner(string owner)
    {
        return owner == _policy.GameGodot.ReaderOwner ||
            owner == _policy.GameGodot.DecisionReaderOwner ||
            owner == _policy.GameGodot.RewardDecisionReaderOwner ||
            owner == _policy.GameGodot.MapDecisionReaderOwner;
    }

    private bool IsGameAccessOwner(string owner)
    {
        return IsAdditionalGameOwnerType(owner) ||
            IsReaderOwner(owner) ||
            owner == _policy.GameGodot.CombatActionOwner ||
            owner == _policy.GameGodot.RewardActionOwner ||
            owner == _policy.GameGodot.MapActionOwner;
    }

    private bool IsAdditionalGameOwnerType(string owner) =>
        _policy.GameGodot.AllowedOwnerTypes.Any(typeName =>
            owner.StartsWith(typeName + ".", StringComparison.Ordinal));

    private void VerifyReflectionSequence()
    {
        MethodDefinitionHandle methodHandle = _methodsByIdentity[_policy.Reflection.Owner];
        MethodDefinition method = _reader.GetMethodDefinition(methodHandle);
        MethodBodyBlock body = _peReader.GetMethodBody(method.RelativeVirtualAddress);
        byte[]? ilBytes = body.GetILBytes();
        if (ilBytes is null)
        {
            throw new VerificationException("unresolved_method_body");
        }

        IReadOnlyList<IlInstruction> instructions = IlDecoder.Decode(ilBytes);
        var observed = new List<string>();
        foreach (IlInstruction instruction in instructions)
        {
            if (instruction.MetadataToken is null ||
                (!instruction.IsLoadToken && !instruction.IsCall))
            {
                continue;
            }

            EntityHandle target = IlDecoder.RequireEntityHandle(instruction.MetadataToken.Value);
            if (instruction.IsLoadToken &&
                target.Kind is HandleKind.TypeDefinition or HandleKind.TypeReference or HandleKind.TypeSpecification)
            {
                string type = MetadataNames.EntityTypeName(_reader, target, _names);
                if (type == _policy.Reflection.TypeToken)
                {
                    observed.Add("ldtoken " + type);
                }
            }
            else if (instruction.IsCall)
            {
                ResolvedMethod call = ResolveCalledMethod(target);
                if (call.DeclaringType == "System.Type" ||
                    IsNamespaceFamily(call.DeclaringType, "System.Reflection"))
                {
                    observed.Add(call.Identity);
                }
            }
        }

        string[] expected =
        {
            "ldtoken " + _policy.Reflection.TypeToken,
            "System.Type.GetTypeFromHandle(System.RuntimeTypeHandle)",
            "System.Type.get_Assembly()",
            "System.Reflection.Assembly.get_Location()",
        };
        if (!observed.SequenceEqual(expected, StringComparer.Ordinal))
        {
            throw new VerificationException("build_guard_path_provenance");
        }
    }

    private void VerifyConfigurationStructure()
    {
        string sourcePath = Path.Combine(
            _sourceRoot,
            _policy.ConfigurationStructure.SourceRelativePath.Replace(
                '/',
                Path.DirectorySeparatorChar));
        var sourceInfo = new FileInfo(sourcePath);
        if (sourceInfo.LinkTarget is not null || !sourceInfo.Exists ||
            sourceInfo.Length <= 0 || sourceInfo.Length > 1024 * 1024)
        {
            throw new VerificationException("configuration_source_boundary");
        }

        byte[] sourceBytes = File.ReadAllBytes(sourcePath);
        sourceInfo.Refresh();
        if (sourceInfo.LinkTarget is not null || sourceInfo.Length != sourceBytes.Length)
        {
            throw new VerificationException("configuration_source_changed");
        }

        string sourceHash = Convert.ToHexString(SHA256.HashData(sourceBytes)).ToLowerInvariant();
        if (sourceHash != _policy.ConfigurationStructure.SourceSha256)
        {
            throw new VerificationException("configuration_source_hash");
        }

        _configurationStructureSha256 = ComputeNormalizedTypeStructure(
            _policy.Filesystem.ConfigurationOwner);
        if (_configurationStructureSha256 != _policy.ConfigurationStructure.TypeStructureSha256)
        {
            throw new VerificationException("configuration_path_provenance");
        }
    }

    private void VerifyTransportStructure()
    {
        _transportStructureSha256 = ComputeNormalizedTypeFamilyStructure(
            _policy.TransportStructure.OwnerType);
        if (_transportStructureSha256 != _policy.TransportStructure.TypeFamilyStructureSha256)
        {
            throw new VerificationException("transport_admission_structure");
        }
    }

    private void VerifyPinnedBuildGuardStructure()
    {
        string sourcePath = Path.Combine(
            _sourceRoot,
            _policy.BuildGuardStructure.SourceRelativePath.Replace('/', Path.DirectorySeparatorChar));
        var sourceInfo = new FileInfo(sourcePath);
        if (sourceInfo.LinkTarget is not null || !sourceInfo.Exists ||
            sourceInfo.Length <= 0 || sourceInfo.Length > 1024 * 1024)
        {
            throw new VerificationException("build_guard_source_boundary");
        }

        byte[] sourceBytes = File.ReadAllBytes(sourcePath);
        sourceInfo.Refresh();
        if (sourceInfo.LinkTarget is not null || sourceInfo.Length != sourceBytes.Length)
        {
            throw new VerificationException("build_guard_source_changed");
        }

        string sourceHash = Convert.ToHexString(SHA256.HashData(sourceBytes)).ToLowerInvariant();
        if (sourceHash != _policy.BuildGuardStructure.SourceSha256)
        {
            throw new VerificationException("build_guard_source_hash");
        }

        MethodDefinitionHandle methodHandle = _methodsByIdentity[_policy.Reflection.Owner];
        MethodDefinition method = _reader.GetMethodDefinition(methodHandle);
        MethodBodyBlock body = _peReader.GetMethodBody(method.RelativeVirtualAddress);
        byte[]? ilBytes = body.GetILBytes();
        if (ilBytes is null)
        {
            throw new VerificationException("build_guard_method_body");
        }

        IReadOnlyList<IlInstruction> instructions = IlDecoder.Decode(ilBytes);
        var calls = new List<(int Index, ResolvedMethod Method)>();
        for (int index = 0; index < instructions.Count; index++)
        {
            IlInstruction instruction = instructions[index];
            if (!instruction.IsCall || instruction.MetadataToken is null)
            {
                continue;
            }

            EntityHandle target = IlDecoder.RequireEntityHandle(instruction.MetadataToken.Value);
            calls.Add((index, ResolveCalledMethod(target)));
        }

        int fileInfoConstructor = RequireSingleCall(
            calls,
            "System.IO.FileInfo..ctor(System.String)",
            "build_guard_file_info_count");
        int firstLink = RequireCallAt(calls, "System.IO.FileSystemInfo.get_LinkTarget()", 0, 2);
        int firstExists = RequireCallAt(calls, "System.IO.FileSystemInfo.get_Exists()", 0, 2);
        int attributes = RequireSingleCall(
            calls,
            "System.IO.FileSystemInfo.get_Attributes()",
            "build_guard_attributes_count");
        int prePathLength = RequireCallAt(calls, "System.IO.FileInfo.get_Length()", 0, 2);
        int streamConstructor = RequireSingleCall(
            calls,
            "System.IO.FileStream..ctor(System.String,System.IO.FileMode,System.IO.FileAccess,System.IO.FileShare)",
            "build_guard_stream_count");
        int preHandleLength = RequireCallAt(calls, "System.IO.Stream.get_Length()", 0, 2);
        int read = RequireSingleCall(
            calls,
            "System.IO.Stream.Read(System.Span<System.Byte>)",
            "build_guard_read_count");
        int postHandleLength = RequireCallAt(calls, "System.IO.Stream.get_Length()", 1, 2);
        int refresh = RequireSingleCall(
            calls,
            "System.IO.FileSystemInfo.Refresh()",
            "build_guard_refresh_count");
        int postLink = RequireCallAt(calls, "System.IO.FileSystemInfo.get_LinkTarget()", 1, 2);
        int postExists = RequireCallAt(calls, "System.IO.FileSystemInfo.get_Exists()", 1, 2);
        int postPathLength = RequireCallAt(calls, "System.IO.FileInfo.get_Length()", 1, 2);
        int digestComparison = RequireSingleNamedCall(
            calls,
            "System.MemoryExtensions",
            "SequenceEqual",
            "build_guard_digest_compare_count");

        int[] requiredOrder =
        {
            fileInfoConstructor,
            firstLink,
            firstExists,
            attributes,
            prePathLength,
            streamConstructor,
            preHandleLength,
            read,
            postHandleLength,
            refresh,
            postLink,
            postExists,
            postPathLength,
            digestComparison,
        };
        for (int index = 1; index < requiredOrder.Length; index++)
        {
            if (requiredOrder[index - 1] >= requiredOrder[index])
            {
                throw new VerificationException("build_guard_operation_order");
            }
        }

        int expectedLengthConstants = instructions.Count(instruction =>
            instruction.IntegerConstant == _policy.BuildGuardStructure.ExpectedAssemblyLength);
        int readBufferConstants = instructions.Count(instruction =>
            instruction.IntegerConstant == _policy.BuildGuardStructure.ReadBufferBytes);
        if (expectedLengthConstants < 5 || readBufferConstants != 1)
        {
            throw new VerificationException("build_guard_bound_constants");
        }

        string resultConstructor =
            "Sts2AgentBridge.Core.Hosting.BuildIdentityResult..ctor(Sts2AgentBridge.Core.Hosting.BuildIdentityStatus)";
        RequireStatusReturnInRange(
            instructions,
            calls,
            resultConstructor,
            prePathLength,
            streamConstructor,
            expectedStatus: 2,
            "build_guard_wrong_size_classification");
        RequireStatusReturnInRange(
            instructions,
            calls,
            resultConstructor,
            read,
            refresh,
            expectedStatus: 0,
            "build_guard_short_read_classification");
        RequireStatusReturnInRange(
            instructions,
            calls,
            resultConstructor,
            refresh,
            digestComparison,
            expectedStatus: 0,
            "build_guard_post_refresh_classification");

        bool finalCompatible = false;
        bool finalLocked = false;
        for (int index = digestComparison; index < instructions.Count; index++)
        {
            finalCompatible |= instructions[index].IntegerConstant == 1;
            finalLocked |= instructions[index].IntegerConstant == 2;
        }

        if (!finalCompatible || !finalLocked)
        {
            throw new VerificationException("build_guard_digest_classification");
        }

        _buildGuardStructureSha256 = ComputeNormalizedTypeStructure(
            _policy.Filesystem.BuildGuardOwner);
        if (_buildGuardStructureSha256 != _policy.BuildGuardStructure.TypeStructureSha256)
        {
            throw new VerificationException("build_guard_path_provenance");
        }
    }

    private static int RequireSingleCall(
        List<(int Index, ResolvedMethod Method)> calls,
        string identity,
        string code)
    {
        int[] matches = calls
            .Where(call => call.Method.Identity == identity)
            .Select(call => call.Index)
            .ToArray();
        if (matches.Length != 1)
        {
            throw new VerificationException(code);
        }

        return matches[0];
    }

    private string ComputeNormalizedTypeStructure(string typeName)
    {
        if (!_typesByName.TryGetValue(typeName, out TypeDefinitionHandle typeHandle))
        {
            throw new VerificationException("structure_type_missing");
        }

        TypeDefinition type = _reader.GetTypeDefinition(typeHandle);
        using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        AppendFingerprintString(hash, "br0_normalized_type_structure_v1");
        AppendFingerprintString(hash, typeName);
        AppendFingerprintInt32(hash, (int)type.Attributes);
        AppendNormalizedCustomAttributes(hash, type.GetCustomAttributes());
        AppendFingerprintString(
            hash,
            type.BaseType.IsNil
                ? string.Empty
                : MetadataNames.EntityTypeName(_reader, type.BaseType, _names));

        string[] interfaces = type.GetInterfaceImplementations()
            .Select(handle => MetadataNames.EntityTypeName(
                _reader,
                _reader.GetInterfaceImplementation(handle).Interface,
                _names))
            .OrderBy(value => value, StringComparer.Ordinal)
            .ToArray();
        AppendFingerprintInt32(hash, interfaces.Length);
        foreach (string interfaceName in interfaces)
        {
            AppendFingerprintString(hash, interfaceName);
        }

        var fields = type.GetFields()
            .Select(handle =>
            {
                FieldDefinition field = _reader.GetFieldDefinition(handle);
                return (
                    Handle: handle,
                    Name: _reader.GetString(field.Name),
                    Type: field.DecodeSignature(_names, null));
            })
            .OrderBy(field => field.Name, StringComparer.Ordinal)
            .ThenBy(field => field.Type, StringComparer.Ordinal)
            .ToArray();
        AppendFingerprintInt32(hash, fields.Length);
        foreach ((FieldDefinitionHandle handle, string name, string fieldType) in fields)
        {
            FieldDefinition field = _reader.GetFieldDefinition(handle);
            AppendFingerprintString(hash, name);
            AppendFingerprintString(hash, fieldType);
            AppendFingerprintInt32(hash, (int)field.Attributes);
            AppendFingerprintString(hash, DescribeFieldDefinition(handle));
            AppendNormalizedCustomAttributes(hash, field.GetCustomAttributes());
            ConstantHandle defaultValue = field.GetDefaultValue();
            if (defaultValue.IsNil)
            {
                AppendFingerprintInt32(hash, -1);
            }
            else
            {
                Constant constant = _reader.GetConstant(defaultValue);
                AppendFingerprintInt32(hash, (int)constant.TypeCode);
                BlobReader valueReader = _reader.GetBlobReader(constant.Value);
                AppendFingerprintBytes(hash, valueReader.ReadBytes(valueReader.Length));
            }
        }

        MethodDefinitionHandle[] methods = type.GetMethods()
            .OrderBy(handle => _methodIdentities[handle], StringComparer.Ordinal)
            .ToArray();
        AppendFingerprintInt32(hash, methods.Length);
        foreach (MethodDefinitionHandle methodHandle in methods)
        {
            AppendNormalizedMethod(hash, methodHandle);
        }

        return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
    }

    private string ComputeNormalizedTypeFamilyStructure(string ownerType)
    {
        string[] typeNames = _typesByName.Keys
            .Where(name => name == ownerType || name.StartsWith(ownerType + "+", StringComparison.Ordinal))
            .OrderBy(name => name, StringComparer.Ordinal)
            .ToArray();
        if (typeNames.Length == 0 || typeNames[0] != ownerType)
        {
            throw new VerificationException("structure_type_missing");
        }

        using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        AppendFingerprintString(hash, "br0_normalized_type_family_structure_v1");
        AppendFingerprintString(hash, ownerType);
        AppendFingerprintInt32(hash, typeNames.Length);
        foreach (string typeName in typeNames)
        {
            AppendFingerprintString(hash, typeName);
            AppendFingerprintString(hash, ComputeNormalizedTypeStructure(typeName));
        }

        return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
    }

    private string ComputeNormalizedAssemblyStructure()
    {
        string[] typeNames = _typesByName.Keys
            .OrderBy(name => name, StringComparer.Ordinal)
            .ToArray();
        using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        AppendFingerprintString(hash, "br0_normalized_release_assembly_structure_v1");
        AssemblyDefinition assembly = _reader.GetAssemblyDefinition();
        AppendFingerprintString(hash, _reader.GetString(assembly.Name));
        AppendFingerprintString(hash, assembly.Version.ToString());
        AppendFingerprintString(
            hash,
            assembly.Culture.IsNil ? string.Empty : _reader.GetString(assembly.Culture));
        AppendFingerprintInt32(hash, (int)assembly.Flags);
        AppendFingerprintInt32(hash, (int)assembly.HashAlgorithm);
        BlobReader publicKey = _reader.GetBlobReader(assembly.PublicKey);
        AppendFingerprintBytes(hash, publicKey.ReadBytes(publicKey.Length));
        AppendNormalizedCustomAttributes(hash, assembly.GetCustomAttributes());

        ModuleDefinition module = _reader.GetModuleDefinition();
        AppendFingerprintString(hash, _reader.GetString(module.Name));
        AppendNormalizedCustomAttributes(hash, module.GetCustomAttributes());
        AppendFingerprintInt32(hash, typeNames.Length);
        foreach (string typeName in typeNames)
        {
            AppendFingerprintString(hash, typeName);
            AppendFingerprintString(hash, ComputeNormalizedTypeStructure(typeName));
        }

        return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
    }

    private void AppendNormalizedCustomAttributes(
        IncrementalHash hash,
        CustomAttributeHandleCollection handles)
    {
        string[] attributes = handles
            .Select(handle =>
            {
                CustomAttribute attribute = _reader.GetCustomAttribute(handle);
                BlobReader valueReader = _reader.GetBlobReader(attribute.Value);
                string value = Convert.ToHexString(valueReader.ReadBytes(valueReader.Length))
                    .ToLowerInvariant();
                return CustomAttributeConstructor(attribute) + ":" + value;
            })
            .OrderBy(value => value, StringComparer.Ordinal)
            .ToArray();
        AppendFingerprintInt32(hash, attributes.Length);
        foreach (string attribute in attributes)
        {
            AppendFingerprintString(hash, attribute);
        }
    }

    private void AppendNormalizedMethod(IncrementalHash hash, MethodDefinitionHandle methodHandle)
    {
        MethodDefinition method = _reader.GetMethodDefinition(methodHandle);
        MethodSignature<string> signature = method.DecodeSignature(_names, null);
        AppendFingerprintString(hash, _methodIdentities[methodHandle]);
        AppendFingerprintString(hash, signature.ReturnType);
        AppendFingerprintInt32(hash, signature.GenericParameterCount);
        AppendFingerprintInt32(hash, signature.RequiredParameterCount);
        AppendFingerprintInt32(hash, signature.Header.IsInstance ? 1 : 0);
        AppendFingerprintInt32(hash, signature.ParameterTypes.Length);
        foreach (string parameter in signature.ParameterTypes)
        {
            AppendFingerprintString(hash, parameter);
        }

        AppendFingerprintInt32(hash, (int)method.Attributes);
        AppendFingerprintInt32(hash, (int)method.ImplAttributes);
        AppendNormalizedCustomAttributes(hash, method.GetCustomAttributes());
        if (method.RelativeVirtualAddress == 0)
        {
            AppendFingerprintInt32(hash, -1);
            return;
        }

        MethodBodyBlock body = _peReader.GetMethodBody(method.RelativeVirtualAddress);
        AppendFingerprintInt32(hash, body.MaxStack);
        AppendFingerprintInt32(hash, body.LocalVariablesInitialized ? 1 : 0);

        if (body.LocalSignature.IsNil)
        {
            AppendFingerprintInt32(hash, 0);
        }
        else
        {
            ImmutableArray<string> locals;
            try
            {
                StandaloneSignature localSignature = _reader.GetStandaloneSignature(body.LocalSignature);
                locals = localSignature.DecodeLocalSignature(_names, null);
            }
            catch (BadImageFormatException)
            {
                throw new VerificationException("unresolved_local_signature");
            }

            AppendFingerprintInt32(hash, locals.Length);
            foreach (string local in locals)
            {
                AppendFingerprintString(hash, local);
            }
        }

        byte[]? ilBytes = body.GetILBytes();
        if (ilBytes is null)
        {
            throw new VerificationException("unresolved_method_body");
        }

        IReadOnlyList<IlInstruction> instructions = IlDecoder.Decode(ilBytes);
        var instructionIndices = instructions
            .Select((instruction, index) => (instruction.Offset, index))
            .ToDictionary(pair => pair.Offset, pair => pair.index);
        AppendFingerprintInt32(hash, instructions.Count);
        foreach (IlInstruction instruction in instructions)
        {
            AppendFingerprintInt32(hash, instruction.OpCode);
            AppendFingerprintInt32(hash, instruction.VariableIndex ?? -1);
            if (instruction.IntegerConstant.HasValue)
            {
                AppendFingerprintInt32(hash, 1);
                AppendFingerprintInt64(hash, instruction.IntegerConstant.Value);
            }
            else
            {
                AppendFingerprintInt32(hash, 0);
            }

            if (instruction.BranchTarget.HasValue)
            {
                if (!instructionIndices.TryGetValue(instruction.BranchTarget.Value, out int branchIndex))
                {
                    throw new VerificationException("structure_branch_target");
                }

                AppendFingerprintInt32(hash, branchIndex);
            }
            else
            {
                AppendFingerprintInt32(hash, -1);
            }

            AppendFingerprintInt32(hash, instruction.SwitchTargets.Length);
            foreach (int target in instruction.SwitchTargets)
            {
                if (!instructionIndices.TryGetValue(target, out int switchIndex))
                {
                    throw new VerificationException("structure_branch_target");
                }

                AppendFingerprintInt32(hash, switchIndex);
            }

            AppendFingerprintString(
                hash,
                instruction.MetadataToken.HasValue
                    ? DescribeMetadataOperand(instruction)
                    : string.Empty);
        }

        AppendFingerprintInt32(hash, body.ExceptionRegions.Length);
        foreach (ExceptionRegion region in body.ExceptionRegions)
        {
            AppendFingerprintInt32(hash, (int)region.Kind);
            AppendFingerprintInt32(hash, RequireInstructionIndex(instructionIndices, region.TryOffset));
            AppendFingerprintInt32(hash, region.TryLength);
            AppendFingerprintInt32(hash, RequireInstructionIndex(instructionIndices, region.HandlerOffset));
            AppendFingerprintInt32(hash, region.HandlerLength);
            AppendFingerprintInt32(
                hash,
                region.Kind == ExceptionRegionKind.Filter
                    ? RequireInstructionIndex(instructionIndices, region.FilterOffset)
                    : -1);
            AppendFingerprintString(
                hash,
                region.CatchType.IsNil
                    ? string.Empty
                    : MetadataNames.EntityTypeName(_reader, region.CatchType, _names));
        }
    }

    private string DescribeMetadataOperand(IlInstruction instruction)
    {
        int token = instruction.MetadataToken ?? throw new VerificationException("structure_metadata_token");
        if (instruction.OpCode == 0x0072)
        {
            try
            {
                return "string:" + _reader.GetUserString(MetadataTokens.UserStringHandle(token));
            }
            catch (ArgumentException)
            {
                throw new VerificationException("structure_metadata_token");
            }
        }

        EntityHandle handle = IlDecoder.RequireEntityHandle(token);
        return handle.Kind switch
        {
            HandleKind.TypeDefinition or HandleKind.TypeReference or HandleKind.TypeSpecification =>
                "type:" + MetadataNames.EntityTypeName(_reader, handle, _names),
            HandleKind.MethodDefinition or HandleKind.MethodSpecification =>
                "method:" + DescribeMethodOperand(handle),
            HandleKind.FieldDefinition => "field:" + DescribeFieldOperand(handle),
            HandleKind.MemberReference => DescribeMemberReferenceOperand((MemberReferenceHandle)handle),
            HandleKind.StandaloneSignature => "signature:" + DescribeStandaloneSignature(
                (StandaloneSignatureHandle)handle),
            _ => throw new VerificationException("structure_metadata_token"),
        };
    }

    private string DescribeMethodOperand(EntityHandle handle)
    {
        string genericArguments = string.Empty;
        if (handle.Kind == HandleKind.MethodSpecification)
        {
            MethodSpecification specification = _reader.GetMethodSpecification((MethodSpecificationHandle)handle);
            ImmutableArray<string> arguments = specification.DecodeSignature(_names, null);
            genericArguments = "<" + string.Join(",", arguments) + ">";
            handle = specification.Method;
        }

        string owner;
        string name;
        MethodSignature<string> signature;
        if (handle.Kind == HandleKind.MethodDefinition)
        {
            MethodDefinition method = _reader.GetMethodDefinition((MethodDefinitionHandle)handle);
            owner = MetadataNames.TypeDefinitionName(_reader, method.GetDeclaringType());
            name = _reader.GetString(method.Name);
            signature = method.DecodeSignature(_names, null);
        }
        else if (handle.Kind == HandleKind.MemberReference)
        {
            MemberReference member = _reader.GetMemberReference((MemberReferenceHandle)handle);
            if (member.GetKind() != MemberReferenceKind.Method)
            {
                throw new VerificationException("structure_metadata_token");
            }

            owner = MetadataNames.ParentTypeName(_reader, member.Parent, _names);
            name = _reader.GetString(member.Name);
            signature = member.DecodeMethodSignature(_names, null);
        }
        else
        {
            throw new VerificationException("structure_metadata_token");
        }

        return owner + "." + name + genericArguments + "(" +
            MetadataNames.FormatParameters(signature.ParameterTypes) + ")->" + signature.ReturnType +
            (signature.Header.IsInstance ? ":instance" : ":static");
    }

    private string DescribeMemberReferenceOperand(MemberReferenceHandle handle)
    {
        MemberReference member = _reader.GetMemberReference(handle);
        return member.GetKind() == MemberReferenceKind.Method
            ? "method:" + DescribeMethodOperand(handle)
            : "field:" + DescribeFieldOperand(handle);
    }

    private string DescribeFieldOperand(EntityHandle handle)
    {
        if (handle.Kind == HandleKind.FieldDefinition)
        {
            return DescribeFieldDefinition((FieldDefinitionHandle)handle);
        }

        if (handle.Kind == HandleKind.MemberReference)
        {
            MemberReference member = _reader.GetMemberReference((MemberReferenceHandle)handle);
            if (member.GetKind() != MemberReferenceKind.Field)
            {
                throw new VerificationException("structure_metadata_token");
            }

            return MetadataNames.ParentTypeName(_reader, member.Parent, _names) + "." +
                _reader.GetString(member.Name) + ":" + member.DecodeFieldSignature(_names, null);
        }

        throw new VerificationException("structure_metadata_token");
    }

    private string DescribeFieldDefinition(FieldDefinitionHandle handle)
    {
        FieldDefinition field = _reader.GetFieldDefinition(handle);
        string fieldType = field.DecodeSignature(_names, null);
        string description = MetadataNames.TypeDefinitionName(_reader, field.GetDeclaringType()) + "." +
            _reader.GetString(field.Name) + ":" + fieldType;
        int relativeVirtualAddress = field.GetRelativeVirtualAddress();
        if (relativeVirtualAddress == 0)
        {
            return description;
        }

        int size = RequireRvaFieldSize(fieldType);
        ImmutableArray<byte> content;
        try
        {
            content = _peReader.GetSectionData(relativeVirtualAddress).GetContent(0, size);
        }
        catch (BadImageFormatException)
        {
            throw new VerificationException("structure_rva_field");
        }

        if (content.Length != size)
        {
            throw new VerificationException("structure_rva_field");
        }

        string contentHash = Convert.ToHexString(SHA256.HashData(content.AsSpan())).ToLowerInvariant();
        return description + ":rva-size=" + size + ":rva-sha256=" + contentHash;
    }

    private int RequireRvaFieldSize(string fieldType)
    {
        if (_typesByName.TryGetValue(fieldType, out TypeDefinitionHandle typeHandle))
        {
            TypeLayout layout = _reader.GetTypeDefinition(typeHandle).GetLayout();
            if (layout.Size > 0 && layout.Size <= 1024 * 1024)
            {
                return layout.Size;
            }
        }

        int primitiveSize = fieldType switch
        {
            "System.Byte" or "System.SByte" or "System.Boolean" => 1,
            "System.Char" or "System.Int16" or "System.UInt16" => 2,
            "System.Int32" or "System.UInt32" or "System.Single" => 4,
            "System.Int64" or "System.UInt64" or "System.Double" => 8,
            _ => 0,
        };
        if (primitiveSize == 0)
        {
            throw new VerificationException("structure_rva_field");
        }

        return primitiveSize;
    }

    private string DescribeStandaloneSignature(StandaloneSignatureHandle handle)
    {
        StandaloneSignature signature = _reader.GetStandaloneSignature(handle);
        BlobReader reader = _reader.GetBlobReader(signature.Signature);
        return Convert.ToHexString(reader.ReadBytes(reader.Length)).ToLowerInvariant();
    }

    private static int RequireInstructionIndex(
        IReadOnlyDictionary<int, int> instructionIndices,
        int offset)
    {
        if (!instructionIndices.TryGetValue(offset, out int index))
        {
            throw new VerificationException("structure_branch_target");
        }

        return index;
    }

    private static void AppendFingerprintString(IncrementalHash hash, string value)
    {
        byte[] bytes = Encoding.UTF8.GetBytes(value);
        AppendFingerprintBytes(hash, bytes);
    }

    private static void AppendFingerprintBytes(IncrementalHash hash, ReadOnlySpan<byte> value)
    {
        AppendFingerprintInt32(hash, value.Length);
        hash.AppendData(value);
    }

    private static void AppendFingerprintInt32(IncrementalHash hash, int value)
    {
        Span<byte> bytes = stackalloc byte[sizeof(int)];
        BinaryPrimitives.WriteInt32LittleEndian(bytes, value);
        hash.AppendData(bytes);
    }

    private static void AppendFingerprintInt64(IncrementalHash hash, long value)
    {
        Span<byte> bytes = stackalloc byte[sizeof(long)];
        BinaryPrimitives.WriteInt64LittleEndian(bytes, value);
        hash.AppendData(bytes);
    }

    private static int RequireCallAt(
        List<(int Index, ResolvedMethod Method)> calls,
        string identity,
        int occurrence,
        int requiredCount)
    {
        int[] matches = calls
            .Where(call => call.Method.Identity == identity)
            .Select(call => call.Index)
            .ToArray();
        if (matches.Length != requiredCount || occurrence < 0 || occurrence >= matches.Length)
        {
            throw new VerificationException("build_guard_call_count");
        }

        return matches[occurrence];
    }

    private static int RequireSingleNamedCall(
        List<(int Index, ResolvedMethod Method)> calls,
        string declaringType,
        string name,
        string code)
    {
        int[] matches = calls
            .Where(call => call.Method.DeclaringType == declaringType && call.Method.Name == name)
            .Select(call => call.Index)
            .ToArray();
        if (matches.Length != 1)
        {
            throw new VerificationException(code);
        }

        return matches[0];
    }

    private static void RequireStatusReturnInRange(
        IReadOnlyList<IlInstruction> instructions,
        List<(int Index, ResolvedMethod Method)> calls,
        string constructor,
        int startExclusive,
        int endExclusive,
        long expectedStatus,
        string code)
    {
        foreach ((int index, ResolvedMethod method) in calls)
        {
            if (method.Identity != constructor || index <= startExclusive || index >= endExclusive || index == 0)
            {
                continue;
            }

            bool exits = false;
            for (int following = index + 1;
                 following < instructions.Count && following <= index + 3;
                 following++)
            {
                exits |= instructions[following].OpCode is 0x002a or 0x00dd or 0x00de;
            }

            if (instructions[index - 1].IntegerConstant == expectedStatus && exits)
            {
                return;
            }
        }

        throw new VerificationException(code);
    }

    private void VerifyRoutes()
    {
        if (!_observedRoutes.SetEquals(_routeLiterals))
        {
            throw new VerificationException("route_literals");
        }
    }

    private void VerifyUserString(int token, string owner)
    {
        UserStringHandle handle;
        try
        {
            handle = MetadataTokens.UserStringHandle(token);
        }
        catch (ArgumentException)
        {
            throw new VerificationException("unresolved_user_string");
        }

        string value = _reader.GetUserString(handle);
        if (owner.StartsWith(_policy.Filesystem.ConfigurationOwner + ".", StringComparison.Ordinal))
        {
            if (value is "Library" or "Application Support" or "Sts2AgentBridge" or
                "r0a" or "config.json" or "credential.hex")
            {
                _observedConfigurationPathComponents.Add(value);
            }
            else if (value.EndsWith(".json", StringComparison.Ordinal) ||
                value.EndsWith(".hex", StringComparison.Ordinal))
            {
                throw new VerificationException("configuration_path_provenance");
            }
        }

        foreach (Match match in RoutePattern.Matches(value))
        {
            string route = match.Value;
            if (!_routeLiterals.Contains(route))
            {
                throw new VerificationException("fourth_route_literal");
            }

            _observedRoutes.Add(route);
        }

        RejectForbiddenName(value);
    }

    private void VerifySourceSurface()
    {
        string sourceDirectory = Path.Combine(
            _sourceRoot,
            _policy.ReleaseStructure.SourceRootRelativePath.Replace('/', Path.DirectorySeparatorChar));
        var root = new DirectoryInfo(sourceDirectory);
        if (root.LinkTarget is not null || !root.Exists)
        {
            throw new VerificationException("source_boundary");
        }

        var sourceRoutes = new HashSet<string>(StringComparer.Ordinal);
        FileInfo[] sources = EnumerateProductionSources(root)
            .OrderBy(
                source => Path.GetRelativePath(_sourceRoot, source.FullName).Replace(
                    Path.DirectorySeparatorChar,
                    '/'),
                StringComparer.Ordinal)
            .ToArray();
        var projection = new StringBuilder();
        foreach (FileInfo source in sources)
        {
            if (source.LinkTarget is not null || source.Length < 0 || source.Length > 1024 * 1024)
            {
                throw new VerificationException("source_boundary");
            }

            byte[] bytes = File.ReadAllBytes(source.FullName);
            source.Refresh();
            if (source.LinkTarget is not null || source.Length != bytes.Length)
            {
                throw new VerificationException("source_changed");
            }

            string text;
            try
            {
                text = new UTF8Encoding(false, true).GetString(bytes);
            }
            catch (DecoderFallbackException)
            {
                throw new VerificationException("source_encoding");
            }

            string relative = Path.GetRelativePath(_sourceRoot, source.FullName)
                .Replace(Path.DirectorySeparatorChar, '/');
            projection.Append(Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant())
                .Append("  ./")
                .Append(relative)
                .Append('\n');

            foreach (string fragment in HardForbiddenSourceFragments.Concat(_policy.ForbiddenNameFragments))
            {
                if (text.Contains(fragment, StringComparison.Ordinal))
                {
                    throw new VerificationException("source_forbidden_fragment");
                }
            }

            foreach (Match match in RoutePattern.Matches(text))
            {
                if (!_routeLiterals.Contains(match.Value))
                {
                    throw new VerificationException("source_fourth_route");
                }

                sourceRoutes.Add(match.Value);
            }
        }

        if (sources.Length != _policy.ReleaseStructure.SourceFileCount)
        {
            throw new VerificationException("release_source_projection");
        }

        if (!sourceRoutes.SetEquals(_routeLiterals))
        {
            throw new VerificationException("source_route_literals");
        }

        _sourceProjectionSha256 = Convert.ToHexString(
                SHA256.HashData(Encoding.UTF8.GetBytes(projection.ToString())))
            .ToLowerInvariant();
        if (_sourceProjectionSha256 != _policy.ReleaseStructure.SourceProjectionSha256)
        {
            throw new VerificationException("release_source_projection");
        }
    }

    private void VerifyReleaseStructure()
    {
        _releaseAssemblyStructureSha256 = ComputeNormalizedAssemblyStructure();
        if (_releaseAssemblyStructureSha256 != _policy.ReleaseStructure.AssemblyStructureSha256)
        {
            throw new VerificationException("release_structure");
        }
    }

    private static IEnumerable<FileInfo> EnumerateProductionSources(DirectoryInfo root)
    {
        var pending = new Stack<DirectoryInfo>();
        pending.Push(root);
        while (pending.Count > 0)
        {
            DirectoryInfo directory = pending.Pop();
            FileSystemInfo[] entries = directory.GetFileSystemInfos();
            Array.Sort(entries, static (left, right) =>
                StringComparer.Ordinal.Compare(left.Name, right.Name));
            foreach (FileSystemInfo entry in entries)
            {
                if (entry.LinkTarget is not null)
                {
                    throw new VerificationException("source_symlink");
                }

                if (entry is DirectoryInfo child)
                {
                    if (child.Name is "bin" or "obj")
                    {
                        continue;
                    }

                    pending.Push(child);
                }
                else if (entry is FileInfo file && file.Extension == ".cs")
                {
                    yield return file;
                }
            }
        }
    }

    private ResolvedMethod ResolveCalledMethod(EntityHandle handle)
    {
        ImmutableArray<string> methodArguments = ImmutableArray<string>.Empty;
        if (handle.Kind == HandleKind.MethodSpecification)
        {
            MethodSpecification specification = _reader.GetMethodSpecification((MethodSpecificationHandle)handle);
            methodArguments = specification.DecodeSignature(_names, null);
            handle = specification.Method;
        }

        ResolvedMethod result;
        if (handle.Kind == HandleKind.MemberReference)
        {
            MemberReferenceHandle referenceHandle = (MemberReferenceHandle)handle;
            MemberReference reference = _reader.GetMemberReference(referenceHandle);
            if (reference.GetKind() != MemberReferenceKind.Method)
            {
                throw new VerificationException("unresolved_call_target");
            }

            string declaringType = MetadataNames.ParentTypeName(_reader, reference.Parent, _names);
            MethodSignature<string> signature = reference.DecodeMethodSignature(_names, null);
            string name = _reader.GetString(reference.Name);
            result = new ResolvedMethod(
                declaringType,
                name,
                declaringType + "." + name + "(" + MetadataNames.FormatParameters(signature.ParameterTypes) + ")");
        }
        else if (handle.Kind == HandleKind.MethodDefinition)
        {
            MethodDefinitionHandle definitionHandle = (MethodDefinitionHandle)handle;
            MethodDefinition definition = _reader.GetMethodDefinition(definitionHandle);
            string declaringType = MetadataNames.TypeDefinitionName(_reader, definition.GetDeclaringType());
            result = new ResolvedMethod(
                declaringType,
                _reader.GetString(definition.Name),
                _methodIdentities[definitionHandle]);
        }
        else
        {
            throw new VerificationException("unresolved_call_target");
        }

        if (!methodArguments.IsDefaultOrEmpty)
        {
            if (result.DeclaringType == "Godot.Callable" &&
                result.Name == "From" &&
                methodArguments.Length == 1 &&
                methodArguments[0] == "System.Action")
            {
                return result with { Identity = "Godot.Callable.From(System.Action)" };
            }

            if (ContainsGameType(result.DeclaringType) ||
                IsNamespaceFamily(result.DeclaringType, _policy.Network.NamespaceFamily) ||
                IsNamespaceFamily(result.DeclaringType, _policy.Filesystem.NamespaceFamily))
            {
                throw new VerificationException("external_method_spec_forbidden");
            }
        }

        return result;
    }

    private ResolvedMember ResolveField(EntityHandle handle)
    {
        if (handle.Kind == HandleKind.MemberReference)
        {
            MemberReferenceHandle referenceHandle = (MemberReferenceHandle)handle;
            MemberReference reference = _reader.GetMemberReference(referenceHandle);
            if (reference.GetKind() != MemberReferenceKind.Field)
            {
                throw new VerificationException("unresolved_field_target");
            }

            string declaring = MetadataNames.ParentTypeName(_reader, reference.Parent, _names);
            _ = reference.DecodeFieldSignature(_names, null);
            string name = _reader.GetString(reference.Name);
            return new ResolvedMember(declaring, declaring + "." + name);
        }

        if (handle.Kind == HandleKind.FieldDefinition)
        {
            FieldDefinition definition = _reader.GetFieldDefinition((FieldDefinitionHandle)handle);
            string declaring = MetadataNames.TypeDefinitionName(_reader, definition.GetDeclaringType());
            string name = _reader.GetString(definition.Name);
            return new ResolvedMember(declaring, declaring + "." + name);
        }

        throw new VerificationException("unresolved_field_target");
    }

    private string CustomAttributeType(CustomAttribute attribute)
    {
        EntityHandle constructor = attribute.Constructor;
        if (constructor.Kind == HandleKind.MemberReference)
        {
            MemberReference member = _reader.GetMemberReference((MemberReferenceHandle)constructor);
            return MetadataNames.ParentTypeName(_reader, member.Parent, _names);
        }

        if (constructor.Kind == HandleKind.MethodDefinition)
        {
            MethodDefinition method = _reader.GetMethodDefinition((MethodDefinitionHandle)constructor);
            return MetadataNames.TypeDefinitionName(_reader, method.GetDeclaringType());
        }

        throw new VerificationException("unresolved_custom_attribute");
    }

    private string CustomAttributeConstructor(CustomAttribute attribute)
    {
        if (attribute.Constructor.Kind == HandleKind.MemberReference)
        {
            return MetadataNames.MemberReferenceIdentity(
                _reader,
                (MemberReferenceHandle)attribute.Constructor,
                _names);
        }

        if (attribute.Constructor.Kind == HandleKind.MethodDefinition)
        {
            return _methodIdentities[(MethodDefinitionHandle)attribute.Constructor];
        }

        throw new VerificationException("unresolved_custom_attribute_constructor");
    }

    private bool HasCustomAttribute(CustomAttributeHandleCollection attributes, string expectedType)
    {
        int count = 0;
        foreach (CustomAttributeHandle handle in attributes)
        {
            if (CustomAttributeType(_reader.GetCustomAttribute(handle)) == expectedType)
            {
                count++;
            }
        }

        return count == 1;
    }

    private string ReadSingleTypeAttributeArgument(CustomAttribute attribute)
    {
        string value = ReadSingleStringAttributeArgument(attribute);
        int assemblySeparator = value.IndexOf(',', StringComparison.Ordinal);
        return assemblySeparator < 0 ? value : value[..assemblySeparator];
    }

    private string ReadSingleStringAttributeArgument(CustomAttribute attribute)
    {
        BlobReader blob = _reader.GetBlobReader(attribute.Value);
        if (blob.ReadUInt16() != 1)
        {
            throw new VerificationException("custom_attribute_blob");
        }

        string? value = blob.ReadSerializedString();
        if (value is null || blob.ReadUInt16() != 0 || blob.RemainingBytes != 0)
        {
            throw new VerificationException("custom_attribute_blob");
        }

        return value;
    }

    private bool IsFilesystemOwner(string owner, string member)
    {
        if (owner.StartsWith(_policy.Filesystem.ConfigurationOwner + ".", StringComparison.Ordinal))
        {
            return true;
        }

        if (!owner.StartsWith(_policy.Filesystem.BuildGuardOwner + ".", StringComparison.Ordinal))
        {
            return false;
        }

        return !member.StartsWith("System.IO.DirectoryInfo.", StringComparison.Ordinal) &&
            member != "System.IO.File.GetUnixFileMode(System.String)";
    }

    private static string NormalizeFilesystemMember(string member, string owner)
    {
        if (member == "System.IO.FileSystemInfo.get_Exists()")
        {
            return owner.Contains(".CheckDirectory(", StringComparison.Ordinal)
                ? "System.IO.DirectoryInfo.get_Exists()"
                : "System.IO.FileInfo.get_Exists()";
        }

        return member switch
        {
            "System.IO.Stream.get_Length()" => "System.IO.FileStream.get_Length()",
            "System.IO.Stream.Read(System.Span<System.Byte>)" =>
                "System.IO.FileStream.Read(System.Span<System.Byte>)",
            _ => member,
        };
    }

    private bool IsPotentialFilesystemMember(string member)
    {
        return _allowedFilesystemMembers.Contains(member) ||
            member == "System.IO.FileSystemInfo.get_Exists()" ||
            member == "System.IO.Stream.get_Length()" ||
            member == "System.IO.Stream.Read(System.Span<System.Byte>)";
    }

    private static bool RequiresPriorLinkCheck(string member)
    {
        return member.Contains(".get_Exists()", StringComparison.Ordinal) ||
            member.Contains(".get_Attributes()", StringComparison.Ordinal) ||
            member.Contains(".get_Length()", StringComparison.Ordinal) ||
            member.Contains(".Refresh()", StringComparison.Ordinal) ||
            member.StartsWith("System.IO.File.GetUnixFileMode", StringComparison.Ordinal) ||
            member.StartsWith("System.IO.FileStream..ctor", StringComparison.Ordinal);
    }

    private static void RequireTrailingConstants(
        IReadOnlyList<IlInstruction> instructions,
        int callIndex,
        string code,
        params long[] expected)
    {
        if (callIndex < expected.Length)
        {
            throw new VerificationException(code);
        }

        int start = callIndex - expected.Length;
        for (int index = 0; index < expected.Length; index++)
        {
            if (instructions[start + index].IntegerConstant != expected[index])
            {
                throw new VerificationException(code);
            }
        }
    }

    private static void RequireRecentConstant(
        IReadOnlyList<IlInstruction> instructions,
        int callIndex,
        long expected,
        int maximumDistance)
    {
        int start = Math.Max(0, callIndex - maximumDistance);
        long? lastConstant = null;
        for (int index = start; index < callIndex; index++)
        {
            if (instructions[index].IntegerConstant is long value)
            {
                lastConstant = value;
            }
        }

        if (lastConstant != expected)
        {
            throw new VerificationException("socket_flags_constant");
        }
    }

    private static string NormalizePolicyMember(string value)
    {
        string normalized = value;
        if (normalized.StartsWith("static ", StringComparison.Ordinal))
        {
            normalized = normalized[7..];
        }

        if (normalized.StartsWith("readonly ", StringComparison.Ordinal))
        {
            normalized = normalized[9..];
        }

        int firstSpace = normalized.IndexOf(' ');
        if (firstSpace >= 0)
        {
            normalized = normalized[(firstSpace + 1)..];
        }

        normalized = normalized
            .Replace(".Exists.get", ".get_Exists()", StringComparison.Ordinal)
            .Replace(".Length.get", ".get_Length()", StringComparison.Ordinal)
            .Replace(".Attributes.get", ".get_Attributes()", StringComparison.Ordinal)
            .Replace(".LinkTarget.get", ".get_LinkTarget()", StringComparison.Ordinal);
        return normalized;
    }

    private void RejectForbiddenName(string value)
    {
        foreach (string fragment in _policy.ForbiddenNameFragments)
        {
            if (value.Contains(fragment, StringComparison.Ordinal))
            {
                throw new VerificationException("forbidden_name_fragment");
            }
        }

        if (value.Contains("HarmonyLib", StringComparison.Ordinal) ||
            value.Contains("0Harmony", StringComparison.Ordinal) ||
            value.Contains("MegaCrit.Sts2.Core.Saves", StringComparison.Ordinal))
        {
            throw new VerificationException("forbidden_name");
        }
    }

    private bool ContainsGameType(string value)
    {
        foreach (string type in _allowedGameTypes)
        {
            if (ContainsExactType(value, type))
            {
                return true;
            }
        }

        return value.StartsWith("MegaCrit.Sts2.", StringComparison.Ordinal) ||
            value.StartsWith("Godot.", StringComparison.Ordinal);
    }

    private static bool ContainsNamespaceFamily(string value, string family) =>
        value.Contains(family + ".", StringComparison.Ordinal) ||
        value.StartsWith(family + ".", StringComparison.Ordinal) ||
        value == family;

    private static bool ContainsExactType(string container, string type)
    {
        int index = container.IndexOf(type, StringComparison.Ordinal);
        while (index >= 0)
        {
            int end = index + type.Length;
            bool left = index == 0 || !IsTypeNameCharacter(container[index - 1]);
            bool right = end == container.Length || !IsTypeNameCharacter(container[end]);
            if (left && right)
            {
                return true;
            }

            index = container.IndexOf(type, end, StringComparison.Ordinal);
        }

        return false;
    }

    private static bool IsTypeNameCharacter(char value) =>
        char.IsLetterOrDigit(value) || value is '_' or '.' or '+' or '`';

    private static string StripTypeDecorations(string type)
    {
        int generic = type.IndexOf('<');
        return generic < 0 ? type.TrimEnd('&', '*', '[', ']', ',') : type[..generic];
    }

    private static bool IsNamespaceFamily(string typeName, string family) =>
        typeName == family || typeName.StartsWith(family + ".", StringComparison.Ordinal);

    private static bool IsFrameworkAssembly(string name) =>
        name == "mscorlib" ||
        name == "netstandard" ||
        name == "System" ||
        name.StartsWith("System.", StringComparison.Ordinal) ||
        name == "Microsoft.CSharp";

    private sealed record ResolvedMethod(string DeclaringType, string Name, string Identity);

    private sealed record ResolvedMember(string DeclaringType, string Identity);
}
