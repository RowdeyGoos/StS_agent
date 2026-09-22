using System;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Sts2AgentBridge.Unified;
using Sts2AgentBridge.Successors.RoomFlowsV1;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop;
using Sts2AgentBridge.Successors.RoomReleaseV1;

internal static partial class Program
{
    private static int ServeShop(string scenario)
    {
        var fixture=new MultiplePurchaseFixture(scenario.StartsWith("removal_")?3:scenario.StartsWith("potion_")||scenario.StartsWith("relic_")?5:9);
        if(scenario=="restock_card"){fixture.Restock=true;fixture.Gold=200;}
        else if(scenario=="replacement_potion") {fixture.Restock=true;fixture.AllowDiscards=true;foreach(var offer in fixture.Offers)offer.Kind=ShopV1OfferKind.Potion;fixture.Potions.Add(new(new object(),"OLD_A"));fixture.Potions.Add(new(new object(),"OLD_B"));}
        else if(scenario.StartsWith("removal_")) {
            Check(new[]{"removal_mixed","removal_empty","removal_bad_debit"}.Contains(scenario),"known removal fixture");
            fixture.Offers[1].Kind=ShopV1OfferKind.Removal;fixture.Offers[2].Kind=ShopV1OfferKind.Potion;
            fixture.Deck.Add(new(new object(),"REMOVE_ME",1,scenario!="removal_empty"));fixture.Deck.Add(new(new object(),"KEEP",0,scenario!="removal_empty"));
            fixture.Potions.Add(new(null,null));
            if(scenario=="removal_bad_debit")fixture.BadDebitAt=2;
        }
        else if(scenario.StartsWith("relic_")) {
            Check(new[]{"relic_mixed","relic_full","relic_owned","relic_bad_debit"}.Contains(scenario),"known relic fixture");
            fixture.Offers[1].Kind=ShopV1OfferKind.Relic;fixture.Offers[1].KeyOverride="POTION_BELT";fixture.Offers[1].CapacityGain=2;
            fixture.Offers[2].Kind=ShopV1OfferKind.Potion;fixture.Offers[3].Kind=ShopV1OfferKind.Relic;
            fixture.Offers[4].Kind=ShopV1OfferKind.Potion;
            fixture.Relics.Add(new(new object(),"OLD_RELIC"));
            fixture.Potions.Add(new(new object(),"OLD_POTION"));
            if(scenario=="relic_full")for(int i=1;i<8;i++)fixture.Potions.Add(new(new object(),"OLD_"+i));
            if(scenario=="relic_owned")fixture.Relics.Add(new(new object(),"POTION_BELT"));
            if(scenario=="relic_bad_debit")fixture.BadDebitAt=2;
        }
        else if(scenario.StartsWith("potion_")) {
            Check(new[]{"potion_mixed","potion_full","potion_zero","potion_bad_debit","potion_holes"}.Contains(scenario),"known potion fixture");
            foreach(int i in new[]{1,2,4})fixture.Offers[i].Kind=ShopV1OfferKind.Potion;
            if(scenario!="potion_zero") {
                fixture.Potions.Add(new(scenario=="potion_holes"?null:new object(),scenario=="potion_holes"?null:"OLD"));
                fixture.Potions.Add(new(scenario is "potion_full" or "potion_holes"?new object():null,scenario is "potion_full" or "potion_holes"?"OLD_1":null));
                fixture.Potions.Add(new(scenario=="potion_full"?new object():null,scenario=="potion_full"?"OLD_2":null));
            }
            if(scenario=="potion_bad_debit")fixture.BadDebitAt=2;
        }
        else if(scenario=="unaffordable")fixture.Gold=15;
        else if(scenario=="free")foreach(var offer in fixture.Offers)offer.Price=0;
        else if(scenario=="prices"){fixture.Offers[0].Price=80;fixture.Offers[1].Price=5;}
        else if(scenario=="repriced")fixture.PriceAfterFirst=30;
        else if(scenario=="bad_debit")fixture.BadDebitAt=2;
        else if(scenario!="normal")throw new ArgumentException("Unknown shop fixture.");
        var (runtime,port)=Start((_,nonce)=>new ShopModule(nonce,fixture),new CoreFixture{MapReady=true});
        Console.WriteLine(JsonSerializer.Serialize(new{port}));
        var stop=Task.Run(Console.ReadLine);
        var until=DateTime.UtcNow.AddSeconds(30);
        while(!stop.IsCompleted&&DateTime.UtcNow<until){runtime.DrainFrame();Thread.Sleep(1);}
        Stop(runtime);
        Console.WriteLine(JsonSerializer.Serialize(new{purchases=fixture.Purchases,disposals=fixture.Disposals,gold=fixture.Gold,deck=fixture.Deck.Count,potions=fixture.Potions.Select(p=>p.StableKey).ToArray(),deck_keys=fixture.Deck.Select(c=>c.StableKey).ToArray(),relics=fixture.Relics.Select(r=>r.StableKey).ToArray(),closes=fixture.Closes,leaves=fixture.Leaves}));
        return 0;
    }
    private sealed class ShopModule : IBridgeModule
    {
        private readonly string _nonce;
        private readonly RoomFlowWireService _wire;
        internal ShopModule(string nonce,MultiplePurchaseFixture fixture){_nonce=nonce;_wire=new(nonce,new ShopV1Session(nonce,fixture));}
        public Capability Capability=>Capability.Rooms;
        public bool Owns(BridgeRequest request)=>request.Capability==Capability.Rooms;
        public ModuleReply Handle(BridgeRequest request)
        {
            var route=request.IsPost?RoomFlowTransportRoute.ParentPost:RoomFlowTransportRoute.ParentGet;
            byte[] body=_wire.Handle(request.Method,request.Path,request.Decision,request.Action);
            var classification=RoomFlowTerminalClassifier.Classify(route,RoomFlowSelection.Shop,_nonce,body);
            Check(classification!=TerminalClassification.Invalid,"shop socket classifier accepts current protocol");
            using var document=JsonDocument.Parse(body);
            bool complete=document.RootElement.GetProperty("status").GetString()=="complete";
            return new(body,Complete:complete,Terminal:!complete&&classification==TerminalClassification.Terminal);
        }
        public void Dispose()=>_wire.Dispose();
    }
}
