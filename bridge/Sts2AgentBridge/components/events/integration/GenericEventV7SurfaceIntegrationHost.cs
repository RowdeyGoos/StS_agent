using System;
using System.Linq;
using System.Text.Json;
using Sts2AgentBridge.Successors.GenericEventV7;
internal static partial class GenericEventV7NativeIntegrationHost {
    private static int RunResults(string scenario){
        using var f=new Program.ResultsFixture(scenario=="S_ONE"?1:scenario=="S_MAX"?64:10,dialogue:3){
            DelayCreation=scenario=="S_CREATION",DelayCompletion=scenario is "S_COMPLETION" or "S_FAULT",Defer=scenario=="S_DEFERRED"};
        using var wire=new GenericEventV7WireService(new string('e',32),f.Session);
        bool changed=false;
        for(int count=0;count<2200;count++){
            string? line=ReadLineBounded();if(line is null)return 0;using var doc=JsonDocument.Parse(line);var request=doc.RootElement;
            if(!request.EnumerateObject().Select(p=>p.Name).SequenceEqual(new[]{"method","route","body"}))return 3;
            var body=request.GetProperty("body").ValueKind==JsonValueKind.Null?null:Convert.FromBase64String(request.GetProperty("body").GetString()!);
            var response=CheckedHandle(wire,request.GetProperty("method").GetString(),request.GetProperty("route").GetString(),body);
            Console.WriteLine(JsonSerializer.Serialize(new{body=Convert.ToBase64String(response),map_open=f.World.Map.IsOpen,capstone_open=f.Container.InUse,confirms=f.Confirms,chosen_calls=f.World.OptionCalls,deck=f.World.Player.Deck.Cards.Select(c=>c.Id.Entry).ToArray()}));
            using var reply=JsonDocument.Parse(response);var root=reply.RootElement;var parent=root.GetProperty("parent");var payload=root.GetProperty("payload");
            if(root.GetProperty("kind").GetString()!="decision")continue;
            bool waiting=(parent.ValueKind==JsonValueKind.Object&&parent.GetProperty("status").GetString()=="waiting")||(payload.ValueKind==JsonValueKind.Object&&payload.GetProperty("status").GetString()=="waiting");
            if(waiting){
                if(f.DelayCreation&&!f.Creation.Task.IsCompleted)f.Creation.SetResult();
                else if(f.Pending is {} close){f.Pending=null;close();}
                else if(f.DelayCompletion&&!f.Completion.Task.IsCompleted){if(scenario=="S_FAULT")f.Completion.SetException(new InvalidOperationException("late"));else f.Completion.SetResult();}
            }
            if(!changed&&payload.ValueKind==JsonValueKind.Object&&payload.GetProperty("status").GetString()=="ready"){
                changed=true;if(scenario=="S_STALE")f.Screen.Bind("ConfirmButton",new MegaCrit.Sts2.Core.Nodes.GodotExtensions.NButton());
                if(scenario=="S_DECK")f.World.Player.Deck.Cards.Reverse();
                if(scenario=="S_FOREIGN")f.Container.Open(new MegaCrit.Sts2.Core.Nodes.Screens.NSimpleCardsViewScreen());
            }
        }
        return 4;
    }
}
