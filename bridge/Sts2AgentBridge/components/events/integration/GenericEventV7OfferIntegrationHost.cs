using System;
using System.Linq;
using System.Text.Json;
using Sts2AgentBridge.Successors.GenericEventV7;
internal static partial class GenericEventV7NativeIntegrationHost {
    private static int RunOffers(string scenario) {
        bool bundle=!scenario.StartsWith("O_CARD",StringComparison.Ordinal);
        using var f=new Program.OfferFixture(bundle,bundle?5:3,bundle?8:1,dialogue:3) {
            CanSkip=scenario.Contains("OPTIONAL",StringComparison.Ordinal),
            DelayCreation=scenario.EndsWith("CREATION",StringComparison.Ordinal),DelayCompletion=scenario.EndsWith("COMPLETION",StringComparison.Ordinal),
            DeferChoice=scenario.EndsWith("CHOICE",StringComparison.Ordinal),DeferConfirm=scenario.EndsWith("CONFIRM",StringComparison.Ordinal),
            PartialAddition=scenario.EndsWith("PARTIAL",StringComparison.Ordinal),Fault=scenario.EndsWith("FAULT",StringComparison.Ordinal),
            WrongRequest=scenario.EndsWith("WRONG",StringComparison.Ordinal),ExtraCard=scenario.EndsWith("EXTRA",StringComparison.Ordinal)||scenario.Contains("GRANT",StringComparison.Ordinal)
        };
        using var wire=new GenericEventV7WireService(new string('e',32),f.Session);
        for(int count=0;count<2200;count++) {
            var line=ReadLineBounded();if(line is null)return 0;using var doc=JsonDocument.Parse(line);var request=doc.RootElement;
            if(!request.EnumerateObject().Select(p=>p.Name).SequenceEqual(new[]{"method","route","body"}))return 3;
            var body=request.GetProperty("body").ValueKind==JsonValueKind.Null?null:Convert.FromBase64String(request.GetProperty("body").GetString()!);
            var response=CheckedHandle(wire,request.GetProperty("method").GetString(),request.GetProperty("route").GetString(),body);
            Console.WriteLine(JsonSerializer.Serialize(new{body=Convert.ToBase64String(response),map_open=f.World.Map.IsOpen,overlay_count=f.World.Overlays.ScreenCount,choices=f.Choices,confirms=f.Confirms,selected=f.Selected,deck=f.World.Player.Deck.Cards.Select(c=>c.Id.Entry).ToArray()}));
            using var reply=JsonDocument.Parse(response);var root=reply.RootElement;var parent=root.GetProperty("parent");var payload=root.GetProperty("payload");
            bool waiting=root.GetProperty("kind").GetString()=="decision"&&((parent.ValueKind==JsonValueKind.Object&&parent.GetProperty("status").GetString()=="waiting")||(payload.ValueKind==JsonValueKind.Object&&payload.GetProperty("status").GetString()=="waiting"));
            if(waiting) {
                if(f.DelayCreation&&!f.Creation.Task.IsCompleted)f.Creation.SetResult();
                else if(f.PendingChoice is {} choose){f.PendingChoice=null;choose();}
                else if(f.PendingConfirm is {} confirm){f.PendingConfirm=null;confirm();}
                else if(f.PartialAddition&&!f.Insertion.Task.IsCompleted)f.Insertion.SetResult();
                else if(f.DelayCompletion&&!f.Completion.Task.IsCompleted)f.Completion.SetResult();
            }
        }
        return 4;
    }
}
