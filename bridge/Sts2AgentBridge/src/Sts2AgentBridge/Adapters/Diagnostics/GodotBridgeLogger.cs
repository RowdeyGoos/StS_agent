using Godot;

namespace Sts2AgentBridge.Adapters.Diagnostics;

public sealed class GodotBridgeLogger
{
    public void Info(string code)
    {
        try
        {
            GD.Print(Format(code));
        }
        catch
        {
        }
    }

    public void Error(string code)
    {
        try
        {
            GD.PrintErr(Format(code));
        }
        catch
        {
        }
    }

    private static string Format(string code) => code switch
    {
        "disabled" => "[Sts2AgentBridge] disabled",
        "invalid_configuration" => "[Sts2AgentBridge] invalid_configuration",
        "uncertain_build_identity" => "[Sts2AgentBridge] uncertain_build_identity",
        "incompatible_locked" => "[Sts2AgentBridge] incompatible_locked",
        "running" => "[Sts2AgentBridge] running",
        "startup_failed" => "[Sts2AgentBridge] startup_failed",
        "stopped" => "[Sts2AgentBridge] stopped",
        _ => "[Sts2AgentBridge] startup_failed",
    };
}
