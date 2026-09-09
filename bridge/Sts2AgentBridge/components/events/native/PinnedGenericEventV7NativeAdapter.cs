using System;
using Sts2AgentBridge.Successors.GenericEventReleaseV5;
using System.Collections.Generic;
using System.Linq;
using Godot;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.addons.mega_text;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardTransformV2;
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

public sealed class PinnedGenericEventV7NativeAdapter : IGenericEventV7NativeAdapter
{
    private readonly GenericEventV7Hooks _hooks;
    private readonly int _thread=System.Environment.CurrentManagedThreadId;
    private NRun? _run;
    private NEventRoom? _room;
    private NMapScreen? _map;
    private NOverlayStack? _overlays;
    private NEventLayout? _layout;
    private EventModel? _event;
    private Player? _player;
    private GenericEventV7Binding? _pending;
    private bool _childCreated,_disposed;
    private readonly Dictionary<NEventOptionButton,OptionBinding> _options=new();
    private readonly HashSet<object> _screens=new(ReferenceEqualityComparer.Instance);
    private readonly HashSet<object> _upgradeClones=new(ReferenceEqualityComparer.Instance);
    private readonly HashSet<object> _previewClones=new(ReferenceEqualityComparer.Instance);
    private readonly HashSet<object> _commandTasks=new(ReferenceEqualityComparer.Instance);
    private readonly HashSet<object> _itemIdentities=new(ReferenceEqualityComparer.Instance);
    private readonly HashSet<object> _tasks=new(ReferenceEqualityComparer.Instance);
    public PinnedGenericEventV7NativeAdapter()=>_hooks=new GenericEventV7Hooks();
    private static GenericEventV7NativeCapture Fixed(string status)=>new(status,false,Array.Empty<GenericEventV7NativeOption>());
    public GenericEventDiagnosticCode LastDiagnostic { get; private set; }
    public GenericEventV7NativeCapture Capture()
    {
        try {var capture=CaptureCore(out GenericEventDiagnosticCode diagnostic);LastDiagnostic=diagnostic;return capture;}
        catch {if(_pending is not null)_pending.Failed=true;LastDiagnostic=GenericEventDiagnosticCode.CaptureException;return Fixed("unsupported");}
    }
    private GenericEventV7NativeCapture CaptureCore(out GenericEventDiagnosticCode diagnostic)
    {
        diagnostic=GenericEventDiagnosticCode.CaptureDisposed;
        if(_disposed) return Fixed("unsupported");
        if(_pending is { } b)
        {
            diagnostic=GenericEventDiagnosticCode.PendingBindingFailed;
            if(b.Failed) return Fixed("unsupported");
            diagnostic=GenericEventDiagnosticCode.PendingOwnership;
            if(!GenericEventV7Hooks.Owns(b)) return Fixed("unsupported");
            diagnostic=GenericEventDiagnosticCode.PendingContext;
            if(!b.ContextValid(b.Option.IsProceed)) return Fixed("unsupported");
            diagnostic=GenericEventDiagnosticCode.PendingTaskFailed;
            if(b.ChosenTask?.IsFaulted==true || b.ChosenTask?.IsCanceled==true ||
                b.RequestTask?.IsFaulted==true || b.RequestTask?.IsCanceled==true) return Fixed("unsupported");
            if(b.Option.IsProceed)
            {
                diagnostic=GenericEventDiagnosticCode.PendingOverlay;
                if(b.RequestSeen || _overlays!.ScreenCount!=0) return Fixed("unsupported");
                if(b.ChosenTask?.IsCompletedSuccessfully==true && _map!.IsOpen && _map.IsTravelEnabled && !_map.IsTraveling)
                { diagnostic=GenericEventDiagnosticCode.MapReady; return Fixed("map"); }
                diagnostic=GenericEventDiagnosticCode.PendingProceed;
                return Fixed("waiting");
            }
            if(b.Item is {} item)
            {
                diagnostic=GenericEventDiagnosticCode.PendingOffers;
                if(!item.Context()||item.FailedTask)return Fixed("unsupported");
                if(item.OfferTask?.IsCompleted==true&&item.Screen is null)return Fixed("unsupported");
                if(!item.Ready){diagnostic=GenericEventDiagnosticCode.PendingRequestTask;return Fixed("waiting");}
                if(!item.Domain()||!item.Overlay())return Fixed("unsupported");
                if(!item.TryButton(out _)){diagnostic=GenericEventDiagnosticCode.PrepareCandidates;return Fixed("waiting");}
                if(item.HasCards) {
                    if(item.IsMixed&&(!GenericEventV7ItemAdapter.Slots(b.Player,out _,out var mixedSlots)||
                        mixedSlots.Count(s=>s.ModelIdentity is null)<item.Entries!.Count(e=>e.CardReward is null&&e.Kind==Sts2AgentBridge.Successors.ItemV1.ItemV1ItemKind.Potion)))return Fixed("unsupported");
                    b.Admission??=new GenericEventV7RewardAdmission(new object(),item.OfferCount,item.IsMixed);
                    return new GenericEventV7NativeCapture("child",false,Array.Empty<GenericEventV7NativeOption>(),item.Screen,b.Admission);
                }
                if(!GenericEventV7ItemAdapter.Slots(b.Player,out _,out var slots)||
                    slots.Count(s=>s.ModelIdentity is null)<item.Entries!.Count(e=>e.Kind==Sts2AgentBridge.Successors.ItemV1.ItemV1ItemKind.Potion))return Fixed("unsupported");
                b.Admission??=new GenericEventV7ItemAdmission(new object(),item.OfferCount);
                diagnostic=GenericEventDiagnosticCode.ChildReady;
                return new GenericEventV7NativeCapture("child",false,Array.Empty<GenericEventV7NativeOption>(),item.Screen,b.Admission);
            }
            if(b.RequestSeen)
            {
                diagnostic=GenericEventDiagnosticCode.PendingSelectorlessRequest;
                if(b.RequestTask?.IsCompleted==true && b.Screen is null) return Fixed("unsupported");
                if(!b.Ready)
                {
                    diagnostic=b.ChosenTask is null?GenericEventDiagnosticCode.PendingChosenTask:
                        b.RequestTask is null?GenericEventDiagnosticCode.PendingRequestTask:GenericEventDiagnosticCode.PendingScreen;
                    return Fixed("waiting");
                }
                diagnostic=GenericEventDiagnosticCode.PendingOverlay;
                if(_overlays!.ScreenCount!=1 || !ReferenceEquals(_overlays.Peek(),b.Screen)) return Fixed("unsupported");
                diagnostic=GenericEventDiagnosticCode.PendingDeck;
                if(!b.MatchesCurrentDeck()) return Fixed("unsupported");
                diagnostic=GenericEventDiagnosticCode.PendingOffers;
                if(!b.MatchesOffers()) return Fixed("unsupported");
                diagnostic=GenericEventDiagnosticCode.PrepareFamily;
                if(!(b.Screen is NDeckUpgradeSelectScreen upgrade ? (b.Prefs.MaxSelect==1?GenericEventV7CardAdapter.IsReady(b,upgrade,out diagnostic):GenericEventV7MultiUpgradeAdapter.IsReady(b,upgrade,out diagnostic)) :
                    b.Screen is NDeckEnchantSelectScreen enchant ? (b.Prefs.MaxSelect==1?GenericEventV7CardAdapter.IsReady(b,enchant,out diagnostic):GenericEventV7RemovalAdapter.IsReady(b,enchant,out diagnostic)):
                    b.Screen is NDeckTransformSelectScreen transform ? GenericEventV7TransformAdapter.IsReady(b,transform,out diagnostic):
                    b.Screen is NDeckCardSelectScreen removal ? GenericEventV7RemovalAdapter.IsReady(b,removal,out diagnostic):
                    b.Screen is NSimpleCardSelectScreen reward && GenericEventV7RewardAdapter.IsReady(b,reward,out diagnostic)))return Fixed("waiting");
                b.Admission ??= new GenericEventV7CardAdmission(new object(),b.Operation==CardSelectionV1Operation.Enchant?"enchant":b.Operation==CardSelectionV1Operation.Upgrade?"upgrade":b.Operation==CardSelectionV1Operation.Remove?"remove":b.Operation==CardSelectionV1Operation.Transform?"transform":"add",
                    b.Prefs.MinSelect,b.Prefs.MaxSelect,b.CommitModeName,b.DomainCount);
                diagnostic=GenericEventDiagnosticCode.ChildReady;
                return new GenericEventV7NativeCapture("child",false,Array.Empty<GenericEventV7NativeOption>(),b.Screen,b.Admission);
            }
            diagnostic=GenericEventDiagnosticCode.PendingOverlay;
            if(_overlays!.ScreenCount!=0) return Fixed("unsupported");
            if(b.ChosenTask?.IsCompletedSuccessfully!=true)
            {
                diagnostic=!b.ChosenSeen?GenericEventDiagnosticCode.PendingChosenEntry:
                    b.ChosenTask is null?GenericEventDiagnosticCode.PendingChosenTask:GenericEventDiagnosticCode.PendingChosenCompletion;
                return Fixed("waiting");
            }
        }
        diagnostic=GenericEventDiagnosticCode.ParentUnavailable;
        var run=NRun.Instance; var room=run?.EventRoom;var map=run?.GlobalUi?.MapScreen;var overlays=run?.GlobalUi?.Overlays;
        if(!Exact(run)||!Exact(room)||!Exact(map)||!Exact(overlays)||
            !ReferenceEquals(NEventRoom.Instance,room)||!ReferenceEquals(NMapScreen.Instance,map)||
            map!.IsOpen||map.IsTravelEnabled||map.IsTraveling||overlays!.ScreenCount!=0||
            !room!.IsVisibleInTree()||room.CustomEventNode is not null||room.EmbeddedCombatRoom is not null||
            CardSelectCmd.Selector is not null) return Fixed("unsupported");
        NEventLayout? layout=room.Layout;
        if(!Exact(layout)||!layout!.IsVisibleInTree()) {diagnostic=_pending is null?GenericEventDiagnosticCode.ParentUnavailable:GenericEventDiagnosticCode.ParentWaiting;return _pending is null?Fixed("unsupported"):Fixed("waiting");}
        var options=new List<GenericEventV7NativeOption>(); EventModel? model=null;Player? player=null;
        foreach(NEventOptionButton button in layout.OptionButtons)
        {
            if(options.Count>=8||!Exact(button)||button.Option is not EventOption option||option.GetType()!=typeof(EventOption)||
                button.Event is not EventModel current||current.Owner is not Player owner) return Fixed("unsupported");
            if(model is null){model=current;player=owner;}
            else if(!ReferenceEquals(model,current)||!ReferenceEquals(player,owner))return Fixed("unsupported");
            if(button.GetNodeOrNull<MegaRichTextLabel>("%Text") is not MegaRichTextLabel label||!Exact(label))return Fixed("unsupported");
            if(!_options.TryGetValue(button,out var bound))
            {bound=new OptionBinding(button,option);_options.Add(button,bound);}
            if(!ReferenceEquals(bound.Option,option))return Fixed("unsupported");
            bool dangerous=option.WillKillPlayer is Func<Player,bool> predicate&&predicate(owner);
            options.Add(new GenericEventV7NativeOption(bound,option.TextKey,label.Text,
                button.IsVisibleInTree()&&button.IsEnabled&&!option.IsLocked,dangerous,option.IsProceed));
        }
        if(model is null||player is null) {diagnostic=_pending is null?GenericEventDiagnosticCode.ParentUnavailable:GenericEventDiagnosticCode.ParentWaiting;return _pending is null?Fixed("unsupported"):Fixed("waiting");}
        if(_run is null){_run=run;_room=room;_map=map;_overlays=overlays;_layout=layout;_event=model;_player=player;}
        if(!ReferenceEquals(_run,run)||!ReferenceEquals(_room,room)||!ReferenceEquals(_map,map)||
            !ReferenceEquals(_overlays,overlays)||!ReferenceEquals(_layout,layout)||!ReferenceEquals(_event,model)||
            !ReferenceEquals(_player,player))return Fixed("unsupported");
        diagnostic=GenericEventDiagnosticCode.ParentReady;
        return new GenericEventV7NativeCapture("parent",model.IsFinished,options);
    }
    public void Dispatch(object candidateIdentity,string nonce,string decisionId,string actionId)
    {
        if(_disposed||_pending is not null||candidateIdentity is not OptionBinding c||
            !_options.TryGetValue(c.Button,out var owned)||!ReferenceEquals(owned,c))throw new InvalidOperationException("Unowned option.");
        _pending=new GenericEventV7Binding(_run!,_player!,_room!,_map!,_overlays!,_layout!,_event!,c.Option,c.Button,nonce,decisionId,actionId);
        _pending.ObservedPreviewClones=_previewClones;
        _pending.ObservedUpgradeClones=_upgradeClones;
        _pending.ObservedCommandTasks=_commandTasks;
        _childCreated=false;
        GenericEventV7Hooks.Arm(_pending);
        try {using(var scope=GenericEventV7Hooks.EnterDispatch(_pending)) c.Button.ForceClick();}
        catch {_pending.Failed=true;throw;}
    }
    public IGenericEventV7ChildSession CreateChild(object admissionIdentity)
    {
        var b=_pending;
        if(b?.Item is {} item)
        {
            if(_childCreated||!item.Ready||b.Admission is not {} admission||
                !ReferenceEquals(admission.Identity,admissionIdentity)||!item.TryButton(out _)||
                !_screens.Add(item.Screen!)||!_itemIdentities.Add(item.Set)||!_itemIdentities.Add(item.Reward!))
                throw new InvalidOperationException("Unowned or repeated item child.");
            _childCreated=true;
            if(item.HasCards) {
                if(item.OfferCount>1)return new GenericEventV7CardRewardSetSession(b.Nonce,new GenericEventV7CardRewardSetAdapter(item));
                item.CardReward!.Start();return new GenericEventV7CardRewardSession(b.Nonce,item.CardReward);
            }
            if(item.OfferCount>1) {
                var set=new GenericEventV7ItemSetAdapter(item);
                try{return new GenericEventV7ItemSetSession(b.Nonce,set);}catch{set.Dispose();throw;}
            }
            var native=new GenericEventV7ItemAdapter(item);
            try{return new GenericEventV7ItemChildSession(b.Nonce,native);}catch{native.Dispose();throw;}
        }
        if(b is null||!b.Ready||_childCreated||b.Admission is null||!ReferenceEquals(b.Admission.Identity,admissionIdentity)||
            !b.Admission.IsSupported||!b.MatchesCurrentDeck()||!b.MatchesOffers()||
            !_screens.Add(b.Screen!)||!_tasks.Add(b.RequestTask!)||!_tasks.Add(b.ChosenTask!))
            throw new InvalidOperationException("Unowned or repeated child.");
        _childCreated=true;
        var context=b.Context();
        if(b.Screen is NDeckTransformSelectScreen transform)
        {
            var native=new GenericEventV7TransformAdapter(b,context,transform);
            try{return new GenericEventV7CardChildSession(new CardTransformV2Session(context,native));}catch{native.Dispose();throw;}
        }
        if(b.GenericDeckTransform && b.Screen is NDeckCardSelectScreen generic)
        {
            var native=new GenericEventV7DeckTransformAdapter(b,context,generic);
            try{return new GenericEventV7CardChildSession(new CardTransformV2Session(context,native));}catch{native.Dispose();throw;}
        }
        ICardSelectionV1NativeAdapter adapter=b.Screen is NDeckUpgradeSelectScreen upgrade
            ?(b.Prefs.MaxSelect==1?new GenericEventV7CardAdapter(b,context,upgrade):new GenericEventV7MultiUpgradeAdapter(b,context,upgrade))
            :b.Screen is NDeckEnchantSelectScreen enchant?(b.Prefs.MaxSelect==1?new GenericEventV7CardAdapter(b,context,enchant):new GenericEventV7RemovalAdapter(b,context,enchant))
            :b.Screen is NDeckCardSelectScreen removal?new GenericEventV7RemovalAdapter(b,context,removal)
            :b.Screen is NSimpleCardSelectScreen reward?new GenericEventV7RewardAdapter(b,context,reward)
            :throw new InvalidOperationException("Unsupported selector family.");
        try{return new GenericEventV7CardChildSession(b.Operation==CardSelectionV1Operation.Enchant
            ?new GenericEventV7EnchantChildSession(context,adapter)
            :b.Operation==CardSelectionV1Operation.Remove?new GenericEventV7RemovalChildSession(context,adapter)
            :new Sts2AgentBridge.Successors.GenericEventV5.GenericEventV5FrozenChildSession(new CardSelectionV1Session(context,adapter)));}catch{adapter.Dispose();throw;}
    }
    public void CompleteParent()
    {
        if(_pending is null||_pending.Failed||_pending.ChosenTask?.IsCompletedSuccessfully!=true)
            throw new InvalidOperationException("Parent callback is incomplete.");
        GenericEventV7Hooks.Close(_pending);_pending=null;_childCreated=false;
    }
    public void Dispose()
    {
        if(_disposed)return;
        if(System.Environment.CurrentManagedThreadId!=_thread)throw new InvalidOperationException("Owner thread cleanup required.");
        if(_pending is not null)GenericEventV7Hooks.Close(_pending);
        _hooks.Dispose();_disposed=true;
    }
    private static bool Exact<T>(T? value)where T:GodotObject=>value is not null&&value.GetType()==typeof(T)&&GodotObject.IsInstanceValid(value);
    private sealed record OptionBinding(NEventOptionButton Button,EventOption Option);
}
