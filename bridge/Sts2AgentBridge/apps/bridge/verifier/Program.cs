using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Text.Json;

// Metadata only: the target assembly and game dependencies are never loaded.
internal static class Program
{
    private static int Main(string[] args)
    {
        try
        {
            if (args.Length is not (1 or 3)) return 2;
            using var stream = File.OpenRead(args[0]);
            using var pe = new PEReader(stream);
            if (!pe.HasMetadata || pe.PEHeaders.CorHeader is not { } cor ||
                (cor.Flags & CorFlags.ILOnly) == 0 || cor.EntryPointTokenOrRelativeVirtualAddress != 0) return 3;
            var reader = pe.GetMetadataReader();
            var assembly = reader.GetAssemblyDefinition();
            if (reader.GetString(assembly.Name) != "Sts2AgentBridgeUnified" || assembly.Version != new Version(1,0,0,0)) return 3;
            var references = reader.AssemblyReferences.Select(h => reader.GetString(reader.GetAssemblyReference(h).Name)).Order().ToArray();
            var allowed = new HashSet<string>(StringComparer.Ordinal) {
                "System.Runtime", "System.Collections", "System.Collections.Concurrent", "System.Collections.Immutable", "System.Linq",
                "System.Memory", "System.Text.Encoding.Extensions", "System.Text.Json", "System.Text.Encodings.Web",
                "System.Threading", "System.Threading.Thread", "System.Threading.ThreadPool", "System.Threading.Tasks", "System.Threading.Tasks.Parallel",
                "System.Net.Primitives", "System.Net.Sockets", "System.Security.Cryptography", "System.Runtime.InteropServices",
                "System.Diagnostics.TraceSource", "System.Runtime.Loader", "System.Runtime.CompilerServices.Unsafe",
                "sts2", "GodotSharp", "0Harmony"
            };
            if (references.Any(n => !allowed.Contains(n)) || !new[] { "sts2", "GodotSharp", "0Harmony" }.All(references.Contains))
                throw new InvalidOperationException("Unexpected references: " + string.Join(",", references.Where(n => !allowed.Contains(n))));
            var initializers = new List<string>();
            foreach (var handle in reader.TypeDefinitions)
            {
                var type = reader.GetTypeDefinition(handle);
                string name = reader.GetString(type.Namespace) + "." + reader.GetString(type.Name);
                foreach (var methodHandle in type.GetMethods())
                {
                    var method = reader.GetMethodDefinition(methodHandle);
                    if (reader.GetString(method.Name).Contains("ForTests", StringComparison.Ordinal)) return 3;
                    if (method.Attributes.HasFlag(MethodAttributes.PinvokeImpl))
                    {
                        var import = method.GetImport();
                        if (reader.GetString(reader.GetModuleReference(import.Module).Name) != "/usr/lib/libSystem.B.dylib") return 3;
                    }
                }
                foreach (var attributeHandle in type.GetCustomAttributes())
                {
                    var attribute = reader.GetCustomAttribute(attributeHandle);
                    if (attribute.Constructor.Kind != HandleKind.MemberReference) continue;
                    var member = reader.GetMemberReference((MemberReferenceHandle)attribute.Constructor);
                    if (member.Parent.Kind != HandleKind.TypeReference) continue;
                    var attributeType = reader.GetTypeReference((TypeReferenceHandle)member.Parent);
                    if (reader.GetString(attributeType.Namespace) == "MegaCrit.Sts2.Core.Modding" &&
                        reader.GetString(attributeType.Name) == "ModInitializerAttribute") initializers.Add(name);
                }
            }
            if (!initializers.SequenceEqual(new[] { "Sts2AgentBridge.Unified.BridgeModEntry" })) return 3;
            if(args.Length==3) CheckResultsSignature(reader,args[1],args[2]);
            Console.WriteLine(JsonSerializer.Serialize(new { status = "passed", initializer = initializers[0], references, results_hook_metadata_checked=args.Length==3 }));
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error.Message); return 3; }
    }
    // Compare declarations in independent PE metadata. A concrete returned object
    // does not establish the declared return type needed by a Harmony postfix.
    private static void CheckResultsSignature(MetadataReader production,string gamePath,string fixturePath)
    {
        using var gameStream=File.OpenRead(gamePath);using var gamePe=new PEReader(gameStream);
        using var fixtureStream=File.OpenRead(fixturePath);using var fixturePe=new PEReader(fixtureStream);
        var game=gamePe.GetMetadataReader();var fixture=fixturePe.GetMetadataReader();
        const string screen="MegaCrit.Sts2.Core.Nodes.Screens.NSimpleCardsViewScreen";
        const string hooks="Sts2AgentBridge.Successors.GenericEventV7.Native.GenericEventV7Hooks";
        var names=new MetadataNames();
        MethodDefinition Method(MetadataReader reader,string typeName,string methodName) {
            var type=reader.TypeDefinitions.Single(h=>MetadataNames.TypeDefinitionName(reader,h)==typeName);
            return reader.GetMethodDefinition(reader.GetTypeDefinition(type).GetMethods().Single(h=>reader.GetString(reader.GetMethodDefinition(h).Name)==methodName));
        }
        var actual=Method(game,screen,"ShowScreen");var stub=Method(fixture,screen,"ShowScreen");
        var target=actual.DecodeSignature(names,null);var inert=stub.DecodeSignature(names,null);
        var postfix=Method(production,hooks,"ResultsScreenPostfix").DecodeSignature(names,null);
        var fixturePostfix=Method(fixture,hooks,"ResultsScreenPostfix").DecodeSignature(names,null);
        var flags=MethodAttributes.MemberAccessMask|MethodAttributes.Static;
        if((actual.Attributes&flags)!=(MethodAttributes.Public|MethodAttributes.Static)||
            (stub.Attributes&flags)!=(actual.Attributes&flags)||actual.GetGenericParameters().Count!=0||stub.GetGenericParameters().Count!=0||
            target.ReturnType!=inert.ReturnType||!target.ParameterTypes.SequenceEqual(inert.ParameterTypes)||
            postfix.ParameterTypes.Length!=2||postfix.ParameterTypes[0]!=target.ReturnType||
            fixturePostfix.ParameterTypes.Length!=2||fixturePostfix.ParameterTypes[0]!=target.ReturnType)
            throw new InvalidOperationException("Results hook declaration differs from pinned game metadata.");
    }

}

