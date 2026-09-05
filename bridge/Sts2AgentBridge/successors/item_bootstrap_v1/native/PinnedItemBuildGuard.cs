using System;
using System.Runtime.InteropServices;
using Godot;
using MegaCrit.Sts2.Core.Modding;

namespace Sts2AgentBridge.Successors.ItemBootstrapV1;

internal static class PinnedItemBuildGuard
{
    private const long Sts2Length = 9_363_456;
    private const string Sts2Sha256 =
        "e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18";
    private const long GodotLength = 5_613_568;
    private const string GodotSha256 =
        "0e4897ecdfb31456a97c7d8028dfb8d7dbdc632e2f73fc9b438d7b266a139289";

    internal static bool Verify()
    {
        try
        {
            if (!OperatingSystem.IsMacOS() ||
                RuntimeInformation.ProcessArchitecture != Architecture.Arm64)
            {
                return false;
            }

            string sts2Path = typeof(ModInitializerAttribute).Assembly.Location;
            string godotPath = typeof(GodotObject).Assembly.Location;
            return ItemPinnedFileIdentity.Verify(sts2Path, Sts2Length, Sts2Sha256) &&
                ItemPinnedFileIdentity.Verify(godotPath, GodotLength, GodotSha256);
        }
        catch
        {
            return false;
        }
    }
}
