using System;
using System.Linq;
using System.Text.Json;
using Sts2AgentBridge.Successors.GenericEventV7;

internal static partial class GenericEventV7NativeIntegrationHost
{
    private static int RunRepeatedPage(string scenario)
    {
        if (!new[]{"P_REPEAT","P_REVISIT","P_DELAY","P_FAULT","P_STALE","P_DANGER","P_BOUND"}.Contains(scenario)) return 2;
        using var f=new Program.RepeatedPageFixture {
            Alternate=scenario=="P_REVISIT", Delayed=scenario=="P_DELAY", Fault=scenario=="P_FAULT",
            Refresh=scenario=="P_STALE"?"label":"fresh", Dangerous=scenario=="P_DANGER"
        };
        using var wire=new GenericEventV7WireService(new string('a',32),f.Session);
        bool released=false;
        for (int count=0;count<2200;count++) {
            string? line=ReadLineBounded(); if(line is null)return 0;
            using var document=JsonDocument.Parse(line); var request=document.RootElement;
            if(!request.EnumerateObject().Select(p=>p.Name).SequenceEqual(new[]{"method","route","body"}))return 3;
            byte[]? body=request.GetProperty("body").ValueKind==JsonValueKind.Null?null:
                Convert.FromBase64String(request.GetProperty("body").GetString()!);
            var response=CheckedHandle(wire,request.GetProperty("method").GetString(),request.GetProperty("route").GetString(),body);
            Console.WriteLine(JsonSerializer.Serialize(new {
                body=Convert.ToBase64String(response), map_open=f.Native.Map.IsOpen,
                chosen_calls=f.Native.OptionCalls, linger_calls=f.Lingers,
                control_calls=f.Buttons.Select(b=>b.ForceClickCalls).ToArray()
            }));
            // Release only after an actual GET has exposed the incomplete callback.
            if(f.Waiting&&!released&&request.GetProperty("method").GetString()=="GET") {
                released=true;f.Completion.SetResult();
            }
        }
        return 4;
    }
}
