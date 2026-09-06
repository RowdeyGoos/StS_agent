using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Native;
namespace Sts2AgentBridge.Successors.GenericEventV1.Native;

internal sealed class GenericEventV1Binding
{
    internal GenericEventV1Binding(NRun run,Player player,NEventRoom room,NMapScreen map,
        NOverlayStack overlays,NEventLayout layout,EventModel model,EventOption option,
        NEventOptionButton controller,string nonce,string decision,string action)
    {
        Run=run; Player=player; Room=room; Map=map; Overlays=overlays; Layout=layout;
        EventModel=model; Option=option; Controller=controller; Nonce=nonce; Decision=decision; Action=action;
        RunState=player.RunState; OptionKey=option.TextKey;
        PreDispatchDeck=CopyDeck(player);
        if (!ContextValid(false) || overlays.ScreenCount!=0) throw new InvalidOperationException("Invalid reservation.");
    }
    internal NRun Run {get;}
    internal Player Player {get;}
    internal IRunState RunState {get;}
    internal NEventRoom Room {get;}
    internal NMapScreen Map {get;}
    internal NOverlayStack Overlays {get;}
    internal NEventLayout Layout {get;}
    internal EventModel EventModel {get;}
    internal EventOption Option {get;}
    internal NEventOptionButton Controller {get;}
    internal string Nonce {get;}
    internal string Decision {get;}
    internal string Action {get;}
    internal string OptionKey {get;}
    internal CardSelectionV1DeckCard[] PreDispatchDeck {get;}
    internal CardSelectorPrefs Prefs;
    internal bool Failed,Closed,ChosenSeen,RequestSeen,ScreenSeen;
    internal Task? ChosenTask;
    internal Task<IEnumerable<CardModel>>? RequestTask;
    internal NDeckUpgradeSelectScreen? Screen;
    internal CardModel[] Originals=Array.Empty<CardModel>();
    internal int DomainCount=>Originals.Length;
    internal IReadOnlyList<CardModel> EligibleOriginals=>Originals;
    internal bool Ready=>!Failed && !Closed && ChosenTask is not null && RequestTask is not null && Screen is not null;
    internal bool SamePrefs(CardSelectorPrefs other)=>other.MinSelect==Prefs.MinSelect &&
        other.MaxSelect==Prefs.MaxSelect && other.Cancelable==Prefs.Cancelable &&
        other.RequireManualConfirmation==Prefs.RequireManualConfirmation &&
        ReferenceEquals(other.Comparison,Prefs.Comparison) && other.UnpoweredPreviews==Prefs.UnpoweredPreviews &&
        other.PretendCardsCanBePlayed==Prefs.PretendCardsCanBePlayed && ReferenceEquals(other.ShouldGlowGold,Prefs.ShouldGlowGold);
    internal bool MatchesChildBinding()=>!Failed && !Closed && GenericEventV1Hooks.Owns(this) && ContextValid(false);
    internal bool ContextValid(bool exit)=>
        !Closed && ReferenceEquals(NRun.Instance,Run) && ReferenceEquals(Run.EventRoom,Room) &&
        ReferenceEquals(NEventRoom.Instance,Room) && ReferenceEquals(NMapScreen.Instance,Map) &&
        ReferenceEquals(Run.GlobalUi?.MapScreen,Map) && ReferenceEquals(Run.GlobalUi?.Overlays,Overlays) &&
        ReferenceEquals(Room.Layout,Layout) && ReferenceEquals(EventModel.Owner,Player) &&
        ReferenceEquals(Player.RunState,RunState) && ReferenceEquals(Controller.Event,EventModel) &&
        ReferenceEquals(Controller.Option,Option) && Option.TextKey==OptionKey &&
        Valid(Run)&&Valid(Room)&&Valid(Map)&&Valid(Overlays)&&Valid(Layout)&&Valid(Controller) &&
        (exit || Room.IsVisibleInTree()) && Room.CustomEventNode is null && Room.EmbeddedCombatRoom is null &&
        CardSelectCmd.Selector is null && (exit || !Map.IsOpen && !Map.IsTravelEnabled && !Map.IsTraveling);
    private static bool Valid(GodotObject obj)=>GodotObject.IsInstanceValid(obj);
    internal bool MatchesCurrentDeck()
    {
        try
        {
            var deck=CopyDeck(Player);
            return deck.Length==PreDispatchDeck.Length && deck.Where((c,i)=>
                !ReferenceEquals(c.ModelIdentity,PreDispatchDeck[i].ModelIdentity)||
                c.StableKey!=PreDispatchDeck[i].StableKey || c.UpgradeLevel!=PreDispatchDeck[i].UpgradeLevel).Any()==false;
        }
        catch{return false;}
    }
    internal static CardSelectionV1DeckCard[] CopyDeck(Player player)
    {
        var deck=new List<CardSelectionV1DeckCard>(); var seen=new HashSet<object>(ReferenceEqualityComparer.Instance);
        foreach(var card in player.Deck.Cards)
        {
            if(card is null || deck.Count>=512 || !seen.Add(card) ||
                !CardSelectionV1NativeRules.IsStableKey(card.Id.Entry)||card.CurrentUpgradeLevel<0)
                throw new InvalidOperationException("Incomplete deck.");
            deck.Add(new CardSelectionV1DeckCard(card,card.Id.Entry,card.CurrentUpgradeLevel));
        }
        return deck.ToArray();
    }
    private CardModel[]? _requestResult;
    internal bool EffectCompleted(IReadOnlyList<object> selected)
    {
        if(!MatchesChildBinding() || ChosenTask?.IsCompletedSuccessfully!=true ||
            RequestTask?.IsCompletedSuccessfully!=true || selected.Count!=1) return false;
        try
        {
            var values=_requestResult ??= RequestTask.Result.Take(2).ToArray();
            if(values.Length!=1 || !ReferenceEquals(values[0],selected[0])) {Failed=true;return false;}
            return true;
        }
        catch {Failed=true;return false;}
    }
    internal CardSelectionV1ParentContext Context()=>new(Nonce,CardSelectionV1ParentKind.Event,
        Decision,Action,this,Run,Player,Room,Map,Option,Controller,CardSelectionV1Operation.Upgrade,
        1,1,CardSelectionV1CommitMode.PreviewConfirm,DomainCount);
    internal bool MatchesAcceptedParent(CardSelectionV1ParentContext context)=>
        ReferenceEquals(context.ParentReceiptIdentity,this)&&ReferenceEquals(context.ParentOptionIdentity,Option)&&
        context.Operation==CardSelectionV1Operation.Upgrade&&context.MinSelect==1&&context.MaxSelect==1&&
        context.ExpectedDomainCount==DomainCount;
}
