using System;
using System.Collections.Generic;
using System.Text.Json;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.RoomFlowsV1;
using Sts2AgentBridge.Successors.RoomFlowsV1.Event;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop;

internal static class Program
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    public static int Main(string[] args)
    {
        if (args.Length != 1) return 2;
        string mode = args[0];
        if (mode == "selftest") return SelfTest();
        if (mode is not ("shop" or "shop_uncertain" or "event" or "event_item" or "event_item_uncertain" or "event_unicode" or "event_choices" or "event_item_choices")) return 2;
        var shop = new ShopFixture(mode);
        var ev = new EventFixture(mode);
        using RoomFlowWireService service = mode.StartsWith("shop", StringComparison.Ordinal)
            ? new RoomFlowWireService(Nonce, new ShopV1Session(Nonce, shop))
            : new RoomFlowWireService(Nonce, new EventV1Session(Nonce, ev, new FrozenEventItemChildFactory()));
        string? line;
        int requests = 0;
        while ((line = Console.ReadLine()) is not null)
        {
            if (++requests > 2048 || line.Length > 2048) return 2;
            using JsonDocument input = JsonDocument.Parse(line);
            JsonElement root = input.RootElement;
            byte[] body = service.Handle(Get(root,"method"),Get(root,"route"),Get(root,"decision_id"),Get(root,"action_id"));
            try { Console.WriteLine(System.Text.Encoding.UTF8.GetString(body)); }
            finally { Array.Clear(body); }
        }
        service.Dispose();
        Console.Error.WriteLine(JsonSerializer.Serialize(new { shop_dispatches=shop.Dispatches,
            event_dispatches=ev.Dispatches, item_dispatches=ev.ItemDispatches, shop_disposals=shop.Disposals }));
        return 0;
    }
    private static JsonElement Read(RoomFlowWireService service) =>
        Parse(service.Handle("GET", RoomFlowWireProtocol.DecisionRoute, null, null));
    private static JsonElement ApplyFirst(RoomFlowWireService service, JsonElement ready) =>
        Parse(service.Handle("POST", RoomFlowWireProtocol.ActionRoute, ready.GetProperty("decision_id").GetString(),
            ready.GetProperty("legal_actions")[0].GetString()));
    private static JsonElement Parse(byte[] body)
    {
        try { using JsonDocument value = JsonDocument.Parse(body); return value.RootElement.Clone(); }
        finally { Array.Clear(body); }
    }
    private static int SelfTest()
    {
        int checks = 0;
        void Check(bool value) { checks++; if (!value) throw new InvalidOperationException("Wire fixture failure."); }
        foreach (bool isShop in new[] { true, false })
        {
            var shop = new ShopFixture("shop");
            var ev = new EventFixture("event_item");
            var eventSession = new EventV1Session(Nonce, ev, new FrozenEventItemChildFactory());
            using var service = isShop ? new RoomFlowWireService(Nonce, new ShopV1Session(Nonce, shop)) :
                new RoomFlowWireService(Nonce, eventSession);
            Check(ApplyFirst(service, Read(service)).GetProperty("status").GetString() == "accepted");
            IEventItemChildBroker? child = null;
            if (!isShop)
            {
                Check(Read(service).GetProperty("status").GetString() == "item_child");
                child = eventSession.ActiveItemChild;
                Check(child is not null);
            }
            bool rejected = System.Threading.Tasks.Task.Run(() =>
            {
                try { service.Dispose(); return false; }
                catch (InvalidOperationException) { return true; }
            }).GetAwaiter().GetResult();
            Check(rejected && shop.Disposals == 0);
            if (child is not null) Check(child.Status is EventItemChildActive);
            service.Dispose();
            Check(isShop ? shop.Disposals == 1 : eventSession.ActiveItemChild is null);
            if (child is not null) Check(child.Status is EventItemChildFailed);
            Check(Read(service).GetProperty("status").GetString() == "error");
        }
        foreach (string route in new[] { "/invalid", Sts2AgentBridge.Successors.ItemWireV1.ItemWireV1Protocol.DecisionRoute })
        {
            var shop = new ShopFixture("shop");
            using var service = new RoomFlowWireService(Nonce, new ShopV1Session(Nonce, shop));
            Check(Parse(service.Handle("GET", route, null, null)).GetProperty("status").GetString() == "error");
            Check(Read(service).GetProperty("status").GetString() == "error" && shop.Dispatches == 0);
        }
        Console.WriteLine(JsonSerializer.Serialize(new {schema_version=1,status="passed",suite="room_flows_wire",check_count=checks}));
        return 0;
    }
    private static string? Get(JsonElement root,string name) => root.GetProperty(name).GetString();

    private sealed class ShopFixture(string mode) : IShopV1NativeAdapter
    {
        private readonly object Run=new(),Room=new(),Inventory=new(),InventoryModel=new(),Player=new(),Map=new(),
            Back=new(),Merchant=new(),Proceed=new(),Card=new(),OldCard=new(),Slot=new(),Entry=new(),Control=new(),Label=new();
        private bool Bought, Closed, Left;
        public int Dispatches, Disposals;
        private IReadOnlyList<ShopV1DeckCardBinding> Deck => Bought
            ? new[] { new ShopV1DeckCardBinding(OldCard,"OLD"),new ShopV1DeckCardBinding(Card,"NEW") }
            : new[] { new ShopV1DeckCardBinding(OldCard,"OLD") };
        private ShopV1NativeControl MerchantControl() => new(Merchant,true,Closed,null);
        private ShopV1NativeControl ProceedControl() => new(Proceed,true,Closed,()=>{Dispatches++;Left=true;});
        public ShopV1SurfaceCapture CaptureSurface() => new(ShopV1SurfaceStatus.Available,
            Run,Room,Inventory,InventoryModel,Player,Map,true,!Closed,!Closed,false,Left,Left,false,
            Bought?75:100,Deck,
            Bought||Closed?Array.Empty<ShopV1NativeOffer>():new[]{new ShopV1NativeOffer(0,ShopV1OfferKind.Card,
                "NEW",25,true,true,true,Slot,Entry,Card,Control,Label,new Purchase(this,mode))},
            new ShopV1NativeControl(Back,true,!Closed,()=>{Dispatches++;Closed=true;}),MerchantControl(),ProceedControl());
        public ShopV1PendingCapture CapturePending(ShopV1PendingProbe probe) => new(ShopV1SurfaceStatus.Available,
            Run,Room,Inventory,InventoryModel,Player,Map,!Left,!Closed,!Closed,false,Left,Left,false,
            Bought?75:100,Deck,MerchantControl(),ProceedControl(),true,Slot,Entry,!Bought,Bought?null:Card,
            Bought?ShopV1Completion.Succeeded:ShopV1Completion.Pending);
        private sealed class Purchase(ShopFixture owner,string mode) : IShopV1NativeDispatch
        {
            public ShopV1Completion Completion => owner.Bought?ShopV1Completion.Succeeded:ShopV1Completion.Pending;
            public void Invoke() { owner.Dispatches++; owner.Bought=true; if(mode=="shop_uncertain")throw new InvalidOperationException("fixture"); }
            public void Dispose() { owner.Disposals++; }
        }
    }

    private sealed class EventFixture(string mode) : IEventV1NativeAdapter, IItemV1NativeAdapter
    {
        private readonly object Run=new(),Player=new(),Room=new(),Map=new(),Screen=new(),Reward=new(),Item=new(),ItemButton=new();
        private readonly object[] Buttons={new(),new(),new()};
        private readonly object[] Options={new(),new(),new()};
        private int Stage;
        private bool MapOpen, Collected;
        public int Dispatches, ItemDispatches;
        private bool HasChild => mode is "event_item" or "event_item_uncertain" or "event_item_choices";
        public EventV1SurfaceCapture CaptureSurface()
        {
            if(HasChild&&Stage==1&&!Collected)
                return EventV1SurfaceCapture.ItemChild(Run,Player,Room,Map,Screen,this);
            int display=Stage==0?0:Stage==1||Stage==2?1:2;
            bool final=display==2;
            string text=mode=="event_unicode"&&display==0 ? "[b]Choose[/b]\n\u4e16\u754c\ud83d\ude00 \"quote\" \u2028" : final?"Proceed":"Option "+display;
            var candidates = new List<EventV1NativeCandidate>
            { new(0,final?"PROCEED":display==0?"FIRST":"SECOND",text,true,true,false,false,
                final,Buttons[display],Options[display],()=>{Dispatches++;if(final)MapOpen=true;else if(Stage==0)Stage=HasChild?1:2;else Stage=3;}) };
            if((mode=="event_choices"||mode=="event_item_choices")&&display==0)
                candidates.Add(new EventV1NativeCandidate(1,"ALTERNATIVE","Alternative",true,true,false,false,false,
                    Buttons[1],Options[1],()=>{Dispatches++;Stage=2;}));
            return EventV1SurfaceCapture.Parent(Run,Player,Room,Map,final,MapOpen,MapOpen,false,candidates);
        }
        public EventV1ExitCapture CaptureExit(EventV1ExitProbe probe) => new(Run,Player,Room,Map,MapOpen,MapOpen,false);
        ItemV1SurfaceCapture IItemV1NativeAdapter.CaptureSurface() => ItemV1SurfaceCapture.Available(Run,Player,Screen,0,
            new[]{new ItemV1NativeOffer(0,ItemV1ItemKind.Relic,"FIXTURE_RELIC",true,false,true,true,ItemButton,Reward,Item,
            ()=>{ItemDispatches++;if(mode=="event_item_uncertain")throw new InvalidOperationException("fixture");Collected=true;Stage=2;})},
            Array.Empty<ItemV1PotionSlotBinding>());
        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe probe) => new(Run,Player,Reward,Item,"FIXTURE_RELIC",
            Collected,Collected?Item:null,Collected?"FIXTURE_RELIC":null,0,Array.Empty<ItemV1PotionSlotBinding>());
    }
}
