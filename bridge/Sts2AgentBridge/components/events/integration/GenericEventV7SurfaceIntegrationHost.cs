using System;
using System.Linq;
using System.Text.Json;
using Sts2AgentBridge.Successors.GenericEventV7;
internal static partial class GenericEventV7NativeIntegrationHost {
    private static int RunAbandon(string scenario) {
        if(scenario is not ("AB_CANCEL" or "AB_CONFIRM" or "AB_DELAY" or "AB_FAULT" or "AB_STALE"))return 2;
        using var f=new Program.AbandonFixture{StrictCleanup=true,Delay=scenario=="AB_DELAY",Fault=scenario=="AB_FAULT"};
        using var wire=new GenericEventV7WireService(new string('a',32),f.Session);
        bool changed=false;
        for(int count=0;count<2200;count++) {
            string? line=ReadLineBounded();if(line is null)return 0;
            using var doc=JsonDocument.Parse(line);var request=doc.RootElement;
            if(!request.EnumerateObject().Select(p=>p.Name).SequenceEqual(new[]{"method","route","body"}))return 3;
            byte[]? body=request.GetProperty("body").ValueKind==JsonValueKind.Null?null:Convert.FromBase64String(request.GetProperty("body").GetString()!);
            byte[] response=CheckedHandle(wire,request.GetProperty("method").GetString(),request.GetProperty("route").GetString(),body);
            Console.WriteLine(JsonSerializer.Serialize(new{body=Convert.ToBase64String(response),map_open=f.World.Map.IsOpen,abandons=f.Abandons,cancels=f.Cancels,hp=f.World.Player.Creature.CurrentHp,modal_open=f.Modal.OpenModal is not null}));
            using var reply=JsonDocument.Parse(response);var root=reply.RootElement;
            if(root.GetProperty("kind").GetString()=="decision"&&root.GetProperty("payload") is var payload&&payload.ValueKind==JsonValueKind.Object) {
                if(payload.GetProperty("status").GetString()=="waiting"&&f.Delay)f.Finish();
                if(payload.GetProperty("status").GetString()=="ready"&&!changed&&scenario=="AB_STALE"){changed=true;f.Popup.Vertical.YesButton=new();}
            }
            if(body is not null)Array.Clear(body);Array.Clear(response);
        }
        return 4;
    }
    private static int RunSphere(string scenario) {
        if(scenario is not ("CS_EMPTY" or "CS_MIXED" or "CS_SKIP" or "CS_DELAY" or "CS_CURSE" or "CS_BAD" or "CS_FREED"))return 2;
        using var f=new Program.SphereFixture(scenario=="CS_EMPTY"?"":scenario=="CS_SKIP"?"c":"gpcr",10);
        f.Delay=scenario=="CS_DELAY";f.Curse=scenario=="CS_CURSE";
        if(scenario=="CS_BAD")f.AfterReward=()=>f.World.Player.Gold++;
        if(scenario=="CS_FREED")f.FreeRewards=true;
        using var wire=new GenericEventV7WireService(new string('e',32),f.Session);
        for(int count=0;count<2200;count++) {
            string? line=ReadLineBounded();if(line is null)return 0;
            using var doc=JsonDocument.Parse(line);var request=doc.RootElement;
            if(!request.EnumerateObject().Select(p=>p.Name).SequenceEqual(new[]{"method","route","body"}))return 3;
            byte[]? body=request.GetProperty("body").ValueKind==JsonValueKind.Null?null:Convert.FromBase64String(request.GetProperty("body").GetString()!);
            byte[] response=CheckedHandle(wire,request.GetProperty("method").GetString(),request.GetProperty("route").GetString(),body);
            Console.WriteLine(JsonSerializer.Serialize(new{body=Convert.ToBase64String(response),map_open=f.World.Map.IsOpen,reveals=f.Reveals,tools=f.Tools,leaves=f.Leaves,purchases=f.Purchases,choices=f.Choices,skips=f.Skips,gold=f.World.Player.Gold,deck=f.World.Player.Deck.Cards.Select(c=>c.Id.Entry).ToArray()}));
            using var reply=JsonDocument.Parse(response);var root=reply.RootElement;
            if(root.GetProperty("kind").GetString()=="decision"&&root.GetProperty("payload") is var payload&&payload.ValueKind==JsonValueKind.Object&&payload.GetProperty("status").GetString()=="waiting"&&f.Pending is {} complete){f.Pending=null;complete();}
            if(body is not null)Array.Clear(body);Array.Clear(response);
        }
        return 4;
    }
    private static int RunMerchant(string scenario) {
        if(scenario is not ("FM_BUY" or "FM_POOR" or "FM_LEAVE" or "FM_DELAY" or "FM_WRONG"))return 2;
        using var f=new Program.MerchantFixture();
        if(scenario=="FM_POOR")f.World.Player.Gold=0;
        if(scenario=="FM_DELAY")f.Delay=true;
        if(scenario=="FM_WRONG")f.AfterPurchase=_=>f.World.Player.Gold++;
        using var wire=new GenericEventV7WireService(new string('a',32),f.Session);
        for(int count=0;count<2200;count++) {
            string? line=ReadLineBounded();if(line is null)return 0;
            using var doc=JsonDocument.Parse(line);var request=doc.RootElement;
            if(!request.EnumerateObject().Select(p=>p.Name).SequenceEqual(new[]{"method","route","body"}))return 3;
            byte[]? body=request.GetProperty("body").ValueKind==JsonValueKind.Null?null:Convert.FromBase64String(request.GetProperty("body").GetString()!);
            byte[] response=CheckedHandle(wire,request.GetProperty("method").GetString(),request.GetProperty("route").GetString(),body);
            Console.WriteLine(JsonSerializer.Serialize(new{body=Convert.ToBase64String(response),map_open=f.World.Map.IsOpen,opens=f.Opens,closes=f.Closes,leaves=f.Leaves,
                purchases=f.Screen.Inventory.Slots.Sum(s=>s.Inputs),gold=f.World.Player.Gold,relics=f.World.Player.Relics.Select(r=>r.Id.Entry).ToArray()}));
            using var reply=JsonDocument.Parse(response);var root=reply.RootElement;
            if(root.GetProperty("kind").GetString()=="decision"&&root.GetProperty("parent").GetProperty("status").GetString()=="waiting"&&f.Pending is {} complete){f.Pending=null;complete();}
            if(body is not null)Array.Clear(body);Array.Clear(response);
        }
        return 4;
    }
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
