using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection;
using Godot;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.ControllerInput;
using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Events.Custom;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Nodes.Screens.Shops;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// The custom merchant presents one native control frame at a time through the
// existing event choices. A new frame is issued only after the exact preceding
// open/purchase/close effect settles, even though Godot reuses inventory nodes.
internal sealed class GenericEventV7MerchantScreen : IDisposable
{
    internal sealed record Choice(string Kind,int Slot,string Key,int Price,object Control,object? Entry,object? Model);
    private readonly NRun _run;
    private readonly NEventRoom _room;
    private readonly NFakeMerchant _screen;
    private readonly MegaCrit.Sts2.Core.Models.Events.FakeMerchant _event;
    private readonly Player _player;
    private readonly IRunState _state;
    private readonly EventRoom _roomModel;
    private readonly NMapScreen _map;
    private readonly NOverlayStack _overlays;
    private readonly NMerchantInventory _inventory;
    private readonly MerchantInventory _inventoryModel;
    private readonly NMerchantButton _open;
    private readonly NBackButton _back;
    private readonly NProceedButton _proceed;
    private readonly Control _blocker;
    private readonly CardSelectionV1DeckCard[] _deck;
    private readonly PotionModel?[] _potions;
    private readonly int _capacity;
    private readonly string?[] _potionKeys;
    private readonly List<RelicModel> _relics;
    private readonly List<string> _relicKeys;
    private int _gold;
    private Choice[]? _frame;
    private NMerchantRelic[]? _slots;
    private MerchantRelicEntry[]? _entries;
    private RelicModel[]? _models;
    private string[]? _keys;
    private int[]? _prices;
    private readonly HashSet<int> _bought=new();
    private Choice? _pending;
    private bool _opened,_closed,_settled,_disposed,_failed,_subscribed,_cleanupFailed;
    private PurchaseStatus? _purchase;
    private int _thread=System.Environment.CurrentManagedThreadId;
    internal GenericEventV7MerchantScreen(NRun run,NEventRoom room,NFakeMerchant screen)
    {
        _run=run;_room=room;_screen=screen;
        _event=Field<MegaCrit.Sts2.Core.Models.Events.FakeMerchant>(screen,"_event");
        _player=_event.Owner??throw new InvalidOperationException("Custom merchant owner missing.");_state=_player.RunState;
        _roomModel=_state.CurrentRoom as EventRoom??throw new InvalidOperationException("Custom merchant room missing.");
        _map=run.GlobalUi.MapScreen;_overlays=run.GlobalUi.Overlays;
        _inventory=screen.Inventory;_inventoryModel=_inventory.Inventory??throw new InvalidOperationException("Custom merchant inventory missing.");
        _open=screen.MerchantButton;_back=_inventory.GetNodeOrNull<NBackButton>("%BackButton")!;
        _proceed=Field<NProceedButton>(screen,"_proceedButton");_blocker=Field<Control>(screen,"_inputBlocker");
        _deck=GenericEventV7Binding.CopyDeck(_player);_capacity=_player.MaxPotionCount;_potions=_player.PotionSlots.ToArray();_potionKeys=_potions.Select(p=>p?.Id.Entry).ToArray();
        _relics=_player.Relics.ToList();_relicKeys=_relics.Select(r=>r.Id.Entry).ToList();_gold=_player.Gold;
        Require(!_inventory.IsOpen);Domain(false);Baseline(false);
    }
    private static T Field<T>(object value,string name)=> (T)(value.GetType().GetField(name,BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(value)??throw new InvalidOperationException("Custom merchant binding missing."));
    private void Require(bool value){if(!value){_failed=true;throw new InvalidOperationException("Custom merchant ownership/effect lost.");}}
    private static bool Valid(GodotObject? value)=>value is not null&&GodotObject.IsInstanceValid(value);
    private void Domain(bool exit)
    {
        Require(!_disposed&&!_failed&&System.Environment.CurrentManagedThreadId==_thread&&
            ReferenceEquals(NRun.Instance,_run)&&ReferenceEquals(_run.EventRoom,_room)&&ReferenceEquals(NEventRoom.Instance,_room)&&
            ReferenceEquals(_room.CustomEventNode,_screen)&&_screen.GetType()==typeof(NFakeMerchant)&&
            ReferenceEquals(Field<object>(_screen,"_event"),_event)&&!_event.StartedFight&&ReferenceEquals(_event.Owner,_player)&&
            ReferenceEquals(_player.RunState,_state)&&ReferenceEquals(_state.CurrentRoom,_roomModel)&&ReferenceEquals(_roomModel.LocalMutableEvent,_event)&&
            ReferenceEquals(_run.GlobalUi.MapScreen,_map)&&ReferenceEquals(NMapScreen.Instance,_map)&&ReferenceEquals(_run.GlobalUi.Overlays,_overlays)&&
            ReferenceEquals(_screen.Inventory,_inventory)&&ReferenceEquals(_inventory.Inventory,_inventoryModel)&&ReferenceEquals(_event.Inventory,_inventoryModel)&&ReferenceEquals(_inventoryModel.Player,_player)&&
            ReferenceEquals(_screen.MerchantButton,_open)&&ReferenceEquals(_inventory.GetNodeOrNull<NBackButton>("%BackButton"),_back)&&
            ReferenceEquals(Field<object>(_screen,"_proceedButton"),_proceed)&&ReferenceEquals(_screen.GetNodeOrNull<NProceedButton>("%ProceedButton"),_proceed)&&
            ReferenceEquals(Field<object>(_screen,"_inputBlocker"),_blocker)&&ReferenceEquals(_screen.GetNodeOrNull<Control>("%InputBlocker"),_blocker)&&
            Valid(_run)&&Valid(_room)&&Valid(_screen)&&Valid(_inventory)&&Valid(_map)&&Valid(_overlays)&&Valid(_open)&&Valid(_back)&&Valid(_proceed)&&Valid(_blocker)&&
            _overlays.ScreenCount==0&&!_map.IsTraveling&&GenericEventV7Binding.CapstoneReady()&&CardSelectCmd.Selector is null&&
            !_open.IsLocalPlayerDead&&(exit||_room.IsVisibleInTree()&&_screen.IsVisibleInTree()&&!_map.IsOpen));
    }
    private void RetainOffers()
    {
        if(_slots is null)return;
        var slots=_inventory.GetAllSlots().ToArray();Require(slots.Length==_slots.Length);
        for(int i=0;i<slots.Length;i++) {
            var entry=_entries![i];Require(ReferenceEquals(slots[i],_slots[i])&&ReferenceEquals(slots[i].Entry,entry)&&
                ReferenceEquals(typeof(MerchantEntry).GetField("_player",BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(entry),_player));
            if(!_bought.Contains(i)&&!(_pending?.Kind=="purchase"&&_pending.Slot==i))Require(entry.IsStocked&&ReferenceEquals(entry.Model,_models![i])&&entry.Model!.Id.Entry==_keys![i]&&entry.Cost==_prices![i]);
        }
    }
    private void Baseline(bool pendingPurchase)
    {
        var deck=GenericEventV7Binding.CopyDeck(_player);
        Require(deck.Length==_deck.Length);
        for(int i=0;i<deck.Length;i++)Require(GenericEventV7Binding.SameDeckCard(deck[i],_deck[i])&&deck[i].ModelIdentity is CardModel card&&ReferenceEquals(card.Owner,_player)&&ReferenceEquals(card.RunState,_state));
        Require(_player.MaxPotionCount==_capacity&&_player.PotionSlots.Count==_potions.Length);
        for(int i=0;i<_potions.Length;i++)Require(ReferenceEquals(_player.PotionSlots[i],_potions[i])&&_potions[i]?.Id.Entry==_potionKeys[i]&&(_potions[i] is null||ReferenceEquals(_potions[i]!.Owner,_player)));
        for(int i=0;i<_relics.Count;i++){var relic=_relics[i];Require(relic.Id.Entry==_relicKeys[i]&&ReferenceEquals(relic.Owner,_player)&&_player.Relics.Count(r=>ReferenceEquals(r,relic))==1);}
        if(!pendingPurchase)Require(_player.Gold==_gold&&_player.Relics.Count==_relics.Count);
    }
    private Choice[] Choices()
    {
        if(_closed)return new[]{new Choice("leave",0,"FAKE_MERCHANT.LEAVE",0,_proceed,null,null)};
        if(!_opened)return new[]{new Choice("open",0,"FAKE_MERCHANT.OPEN",0,_open,null,null)};
        Require(_inventory.IsOpen&&_inventory.IsVisibleInTree());
        var currentSlots=_inventory.GetAllSlots().ToArray();
        Require(currentSlots.Length==6&&currentSlots.All(s=>s is NMerchantRelic)&&currentSlots.Select(s=>s.Entry).Distinct(ReferenceEqualityComparer.Instance).Count()==6);
        if(_slots is null){
            _slots=currentSlots.Cast<NMerchantRelic>().ToArray();_entries=_slots.Select(s=>s.Entry as MerchantRelicEntry??throw new InvalidOperationException("Unsupported merchant entry.")).ToArray();
            Require(_entries.All(e=>e.IsStocked&&e.Model is not null));
            _models=_entries.Select(e=>e.Model!).ToArray();_keys=_models.Select(m=>m.Id.Entry).ToArray();_prices=_entries.Select(e=>e.Cost).ToArray();
        }
        var choices=new List<Choice>();int index=0;
        var entries=new HashSet<object>(ReferenceEqualityComparer.Instance);var models=new HashSet<object>(ReferenceEqualityComparer.Instance);
        foreach(var slot in _inventory.GetAllSlots()) {
            Require(index<6&&slot is NMerchantRelic&&Valid(slot)&&ReferenceEquals(slot,_slots[index])&&ReferenceEquals(slot.Entry,_entries![index])&&slot.Entry.IsStocked==!_bought.Contains(index));
            var entry=slot.Entry as MerchantRelicEntry;Require(entry is not null&&entries.Add(entry)&&ReferenceEquals(typeof(MerchantEntry).GetField("_player",BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(entry),_player));
            if(entry!.IsStocked) {
                var model=entry.Model;var label=slot.GetNodeOrNull<Label>("%CostLabel");
                Require(model is not null&&ReferenceEquals(model,_models![index])&&model.Id.Entry==_keys![index]&&entry.Cost==_prices![index]&&models.Add(model)&&model.Owner is null&&!_player.Relics.Any(r=>ReferenceEquals(r,model))&&GenericEventV7ItemState.ValidKey(model.Id.Entry)&&
                    Valid(slot.Hitbox)&&Valid(label)&&int.TryParse(label!.Text,NumberStyles.None,CultureInfo.InvariantCulture,out int price)&&price>=0&&price==entry.Cost);
                choices.Add(new Choice("purchase",index,model!.Id.Entry,entry.Cost,slot,entry,model));
            }
            index++;
        }
        Require(index==6);choices.Add(new Choice("close",0,"FAKE_MERCHANT.CLOSE",0,_back,null,null));return choices.ToArray();
    }
    private bool Enabled(Choice choice)=>_blocker.MouseFilter==Control.MouseFilterEnum.Ignore&&choice.Kind switch {
        "open"=>!_inventory.IsOpen&&_open.IsVisibleInTree()&&_open.IsEnabled,
        "close"=>_inventory.IsOpen&&_back.IsVisibleInTree()&&_back.IsEnabled,
        "leave"=>!_inventory.IsOpen&&_proceed.IsVisibleInTree()&&_proceed.IsEnabled&&_map.IsTravelEnabled,
        "purchase"=>choice.Control is NMerchantRelic slot&&slot.IsVisibleInTree()&&slot.Hitbox.IsVisibleInTree()&&slot.Hitbox.IsEnabled&&
            choice.Entry is MerchantRelicEntry entry&&entry.IsStocked&&entry.EnoughGold&&_player.Gold>=choice.Price,
        _=>false};
    internal GenericEventV7NativeCapture Capture()
    {
        Domain(_pending?.Kind=="leave");RetainOffers();Baseline(_pending?.Kind=="purchase"&&!_settled);
        if(_pending is {} pending&&!_settled) {
            if(pending.Kind=="purchase") {
                Require(_inventory.IsOpen&&ReferenceEquals(((NMerchantRelic)pending.Control).Entry,pending.Entry));
                if(_purchase is null)return Fixed("waiting");
                Require(_purchase==PurchaseStatus.Success&&pending.Model is RelicModel relic&&ReferenceEquals(relic.Owner,_player)&&
                    _player.Relics.Count==_relics.Count+1&&_player.Relics.Count(r=>ReferenceEquals(r,relic))==1&&_player.Gold==_gold-pending.Price);
                Require(!((MerchantRelicEntry)pending.Entry!).IsStocked);_relics.Add((RelicModel)pending.Model!);_relicKeys.Add(pending.Key);_bought.Add(pending.Slot);_gold=_player.Gold;Unsubscribe();
            }else if(pending.Kind=="open") {if(!_inventory.IsOpen||!_inventory.IsVisibleInTree()||!_back.IsVisibleInTree()||!_back.IsEnabled)return Fixed("waiting");_opened=true;}
            else if(pending.Kind=="close") {if(_inventory.IsOpen||!_open.IsEnabled||!_proceed.IsEnabled)return Fixed("waiting");_closed=true;}
            else if(pending.Kind=="leave") {if(!_map.IsOpen||!_map.IsTravelEnabled)return Fixed("waiting");_settled=true;return Fixed("map");}
            _settled=true;_frame=null;Baseline(false);
        }
        if(_pending?.Kind=="leave")return Fixed("map");
        var current=Choices();
        if(_frame is null)_frame=current;
        else Require(current.SequenceEqual(_frame));
        return new("parent",_closed,_frame.Select(c=>new GenericEventV7NativeOption(c,
            c.Kind=="purchase"?$"FAKE_MERCHANT.BUY.{c.Slot}.{c.Key}.{c.Price}":c.Key,
            c.Kind=="purchase"?$"{c.Key} — {c.Price} gold":c.Kind=="open"?"Open merchant inventory":c.Kind=="close"?"Close merchant inventory":"Leave",Enabled(c),false,_closed)).ToArray());
    }
    private static GenericEventV7NativeCapture Fixed(string status)=>new(status,false,Array.Empty<GenericEventV7NativeOption>());
    internal bool Owns(object identity)=>_frame?.Any(c=>ReferenceEquals(c,identity))==true;
    internal void Dispatch(object identity)
    {
        Require(_pending is null&&Owns(identity));Capture();var choice=(Choice)identity;Require(Enabled(choice));_pending=choice;_settled=false;
        if(choice.Kind=="purchase") {
            var entry=(MerchantRelicEntry)choice.Entry!;entry.PurchaseCompleted+=Purchased;_subscribed=true;
            using var input=new InputEventAction{Action=MegaInput.select,Pressed=true};((NMerchantRelic)choice.Control)._GuiInput(input);
        }else if(choice.Kind=="open")_open.ForceClick();else if(choice.Kind=="close")_back.ForceClick();else _proceed.ForceClick();
    }
    private void Purchased(PurchaseStatus status,MerchantEntry entry){if(_disposed||_purchase is not null||!ReferenceEquals(_pending?.Entry,entry)){_failed=true;return;}_purchase=status;}
    internal void CompleteParent(){Require(_settled);_pending=null;_purchase=null;_settled=false;}
    private void Unsubscribe(){if(_subscribed&&_pending?.Entry is MerchantRelicEntry entry){entry.PurchaseCompleted-=Purchased;_subscribed=false;}}
    public void Dispose(){
        if(_cleanupFailed)throw new InvalidOperationException("Custom merchant cleanup previously failed.");
        if(_disposed)return;Require(System.Environment.CurrentManagedThreadId==_thread);
        bool uncertain=_pending is not null&&!_settled;_cleanupFailed=uncertain;Unsubscribe();_disposed=true;
        if(uncertain)throw new InvalidOperationException("Custom merchant input is unresolved; cleanup cannot release ownership.");
    }
}
