using System;
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
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.addons.mega_text;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.GenericEventV1.Native;

public sealed class PinnedGenericEventV1NativeAdapter : IGenericEventV1NativeAdapter
{
    private readonly GenericEventV1Hooks _hooks;
    private readonly int _thread=System.Environment.CurrentManagedThreadId;
    private NRun? _run;
    private NEventRoom? _room;
    private NMapScreen? _map;
    private NOverlayStack? _overlays;
    private NEventLayout? _layout;
    private EventModel? _event;
    private Player? _player;
    private GenericEventV1Binding? _pending;
    private bool _childCreated,_disposed;
    private readonly Dictionary<NEventOptionButton,OptionBinding> _options=new();
    private readonly HashSet<object> _screens=new(ReferenceEqualityComparer.Instance);
    private readonly HashSet<object> _tasks=new(ReferenceEqualityComparer.Instance);
    public PinnedGenericEventV1NativeAdapter()=>_hooks=new GenericEventV1Hooks();
    private static GenericEventV1NativeCapture Fixed(string status)=>new(status,false,Array.Empty<GenericEventV1NativeOption>());
    public GenericEventV1NativeCapture Capture()
    {
        try {return CaptureCore();} catch {if(_pending is not null)_pending.Failed=true;return Fixed("unsupported");}
    }
    private GenericEventV1NativeCapture CaptureCore()
    {
        if(_disposed) return Fixed("unsupported");
        if(_pending is { } b)
        {
            if(b.Failed || !GenericEventV1Hooks.Owns(b) || !b.ContextValid(b.Option.IsProceed) ||
                b.ChosenTask?.IsFaulted==true || b.ChosenTask?.IsCanceled==true ||
                b.RequestTask?.IsFaulted==true || b.RequestTask?.IsCanceled==true) return Fixed("unsupported");
            if(b.Option.IsProceed)
            {
                if(b.RequestSeen || _overlays!.ScreenCount!=0) return Fixed("unsupported");
                if(b.ChosenTask?.IsCompletedSuccessfully==true && _map!.IsOpen && _map.IsTravelEnabled && !_map.IsTraveling)
                    return Fixed("map");
                return Fixed("waiting");
            }
            if(b.RequestSeen)
            {
                if(b.RequestTask?.IsCompleted==true && b.Screen is null) return Fixed("unsupported");
                if(!b.Ready) return Fixed("waiting");
                if(_overlays!.ScreenCount!=1 || !ReferenceEquals(_overlays.Peek(),b.Screen)) return Fixed("unsupported");
                if(!b.MatchesCurrentDeck()) return Fixed("unsupported");
                if(!GenericEventV1CardAdapter.IsReady(b,b.Screen!)) return Fixed("waiting");
                return new GenericEventV1NativeCapture("child",false,Array.Empty<GenericEventV1NativeOption>(),b.Screen,b.DomainCount);
            }
            if(_overlays!.ScreenCount!=0) return Fixed("unsupported");
            if(b.ChosenTask?.IsCompletedSuccessfully!=true) return Fixed("waiting");
        }
        var run=NRun.Instance; var room=run?.EventRoom;var map=run?.GlobalUi?.MapScreen;var overlays=run?.GlobalUi?.Overlays;
        if(!Exact(run)||!Exact(room)||!Exact(map)||!Exact(overlays)||
            !ReferenceEquals(NEventRoom.Instance,room)||!ReferenceEquals(NMapScreen.Instance,map)||
            map!.IsOpen||map.IsTravelEnabled||map.IsTraveling||overlays!.ScreenCount!=0||
            !room!.IsVisibleInTree()||room.CustomEventNode is not null||room.EmbeddedCombatRoom is not null||
            CardSelectCmd.Selector is not null) return Fixed("unsupported");
        NEventLayout? layout=room.Layout;
        if(!Exact(layout)||!layout!.IsVisibleInTree()) return _pending is null?Fixed("unsupported"):Fixed("waiting");
        var options=new List<GenericEventV1NativeOption>(); EventModel? model=null;Player? player=null;
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
            options.Add(new GenericEventV1NativeOption(bound,option.TextKey,label.Text,
                button.IsVisibleInTree()&&button.IsEnabled&&!option.IsLocked,dangerous,option.IsProceed));
        }
        if(model is null||player is null) return _pending is null?Fixed("unsupported"):Fixed("waiting");
        if(_run is null){_run=run;_room=room;_map=map;_overlays=overlays;_layout=layout;_event=model;_player=player;}
        if(!ReferenceEquals(_run,run)||!ReferenceEquals(_room,room)||!ReferenceEquals(_map,map)||
            !ReferenceEquals(_overlays,overlays)||!ReferenceEquals(_layout,layout)||!ReferenceEquals(_event,model)||
            !ReferenceEquals(_player,player))return Fixed("unsupported");
        return new GenericEventV1NativeCapture("parent",model.IsFinished,options);
    }
    public void Dispatch(object candidateIdentity,string nonce,string decisionId,string actionId)
    {
        if(_disposed||_pending is not null||candidateIdentity is not OptionBinding c||
            !_options.TryGetValue(c.Button,out var owned)||!ReferenceEquals(owned,c))throw new InvalidOperationException("Unowned option.");
        _pending=new GenericEventV1Binding(_run!,_player!,_room!,_map!,_overlays!,_layout!,_event!,c.Option,c.Button,nonce,decisionId,actionId);
        _childCreated=false;
        GenericEventV1Hooks.Arm(_pending);
        try {using(var scope=GenericEventV1Hooks.EnterDispatch(_pending)) c.Button.ForceClick();}
        catch {_pending.Failed=true;throw;}
    }
    public CardSelectionV1Session CreateChild()
    {
        var b=_pending;
        if(b is null||!b.Ready||_childCreated||!b.MatchesCurrentDeck()||
            !_screens.Add(b.Screen!)||!_tasks.Add(b.RequestTask!)||!_tasks.Add(b.ChosenTask!))
            throw new InvalidOperationException("Unowned or repeated child.");
        _childCreated=true;
        var context=b.Context();var adapter=new GenericEventV1CardAdapter(b,context,b.Screen!);
        try{return new CardSelectionV1Session(context,adapter);}catch{adapter.Dispose();throw;}
    }
    public void CompleteParent()
    {
        if(_pending is null||_pending.Failed||_pending.ChosenTask?.IsCompletedSuccessfully!=true)
            throw new InvalidOperationException("Parent callback is incomplete.");
        GenericEventV1Hooks.Close(_pending);_pending=null;_childCreated=false;
    }
    public void Dispose()
    {
        if(_disposed)return;
        if(System.Environment.CurrentManagedThreadId!=_thread)throw new InvalidOperationException("Owner thread cleanup required.");
        if(_pending is not null)GenericEventV1Hooks.Close(_pending);
        _hooks.Dispose();_disposed=true;
    }
    private static bool Exact<T>(T? value)where T:GodotObject=>value is not null&&value.GetType()==typeof(T)&&GodotObject.IsInstanceValid(value);
    private sealed record OptionBinding(NEventOptionButton Button,EventOption Option);
}
