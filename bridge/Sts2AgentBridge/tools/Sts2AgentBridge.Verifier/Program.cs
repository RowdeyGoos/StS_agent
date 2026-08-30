using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace Sts2AgentBridge.Verifier;

internal static class Program
{
    private const int ExitPassed = 0;
    private const int ExitInvalidInvocation = 2;
    private const int ExitUnsafeBoundary = 3;
    private const int ExitMismatch = 4;
    private const int ExitInternal = 5;

    public static int Main(string[] args)
    {
        try
        {
            Arguments parsed = Arguments.Parse(args);
            byte[] policyBytes = ReadBoundedRegularFile(parsed.Policy, 1024 * 1024, "policy_boundary");
            SurfacePolicy policy = SurfacePolicy.Parse(policyBytes);
            var verifier = new ProductionSurfaceVerifier(parsed.Assembly, parsed.SourceRoot, policy);
            VerificationReport report = verifier.Verify();
            Emit(new Dictionary<string, object?>
            {
                ["schema_version"] = 1,
                ["status"] = "passed",
                ["assembly_name"] = report.AssemblyName,
                ["assembly_sha256"] = report.AssemblySha256,
                ["route_count"] = report.RouteCount,
                ["checked_method_bodies"] = report.CheckedMethodBodies,
                ["configuration_structure_sha256"] = report.ConfigurationStructureSha256,
                ["build_guard_structure_sha256"] = report.BuildGuardStructureSha256,
                ["transport_structure_sha256"] = report.TransportStructureSha256,
                ["source_projection_sha256"] = report.SourceProjectionSha256,
                ["release_assembly_structure_sha256"] = report.ReleaseAssemblyStructureSha256,
            });
            return ExitPassed;
        }
        catch (InvocationException exception)
        {
            EmitFailure(exception.Code);
            return ExitInvalidInvocation;
        }
        catch (BoundaryException exception)
        {
            EmitFailure(exception.Code);
            return ExitUnsafeBoundary;
        }
        catch (VerificationException exception)
        {
            EmitFailure(exception.Code);
            return ExitMismatch;
        }
        catch (Exception)
        {
            EmitFailure("internal_failure");
            return ExitInternal;
        }
    }

    private static byte[] ReadBoundedRegularFile(string path, int maximumBytes, string code)
    {
        var info = new FileInfo(path);
        if (info.LinkTarget is not null || !info.Exists ||
            (info.Attributes & (FileAttributes.Directory | FileAttributes.ReparsePoint | FileAttributes.Device)) != 0 ||
            info.Length < 0 || info.Length > maximumBytes)
        {
            throw new BoundaryException(code);
        }

        byte[] data = File.ReadAllBytes(path);
        info.Refresh();
        if (info.LinkTarget is not null || !info.Exists || info.Length != data.Length)
        {
            throw new BoundaryException(code);
        }

        return data;
    }

    private static void EmitFailure(string code) => Emit(new Dictionary<string, object?>
    {
        ["schema_version"] = 1,
        ["status"] = "failed",
        ["code"] = code,
    });

    private static void Emit(Dictionary<string, object?> payload)
    {
        Console.Out.WriteLine(JsonSerializer.Serialize(payload));
    }

    private sealed class Arguments
    {
        private Arguments(string assembly, string policy, string sourceRoot)
        {
            Assembly = assembly;
            Policy = policy;
            SourceRoot = sourceRoot;
        }

        public string Assembly { get; }

        public string Policy { get; }

        public string SourceRoot { get; }

        public static Arguments Parse(string[] args)
        {
            if (args.Length != 6)
            {
                throw new InvocationException("invalid_arguments");
            }

            var values = new Dictionary<string, string>(StringComparer.Ordinal);
            for (int index = 0; index < args.Length; index += 2)
            {
                string name = args[index];
                if (name is not "--assembly" and not "--policy" and not "--source-root" ||
                    !values.TryAdd(name, args[index + 1]))
                {
                    throw new InvocationException("invalid_arguments");
                }
            }

            string assembly = RequireAbsolute(values, "--assembly");
            string policy = RequireAbsolute(values, "--policy");
            string sourceRoot = RequireAbsolute(values, "--source-root");
            if (!Directory.Exists(sourceRoot) || new DirectoryInfo(sourceRoot).LinkTarget is not null)
            {
                throw new BoundaryException("source_root_boundary");
            }

            return new Arguments(assembly, policy, sourceRoot);
        }

        private static string RequireAbsolute(Dictionary<string, string> values, string name)
        {
            if (!values.TryGetValue(name, out string? value) ||
                !Path.IsPathFullyQualified(value) ||
                !string.Equals(Path.GetFullPath(value), value, StringComparison.Ordinal))
            {
                throw new InvocationException("non_absolute_argument");
            }

            return value;
        }
    }

    private sealed class InvocationException : Exception
    {
        public InvocationException(string code)
            : base(code)
        {
            Code = code;
        }

        public string Code { get; }
    }

    private sealed class BoundaryException : Exception
    {
        public BoundaryException(string code)
            : base(code)
        {
            Code = code;
        }

        public string Code { get; }
    }
}

internal sealed record VerificationReport(
    string AssemblyName,
    string AssemblySha256,
    int RouteCount,
    int CheckedMethodBodies,
    string ConfigurationStructureSha256,
    string BuildGuardStructureSha256,
    string TransportStructureSha256,
    string SourceProjectionSha256,
    string ReleaseAssemblyStructureSha256);
