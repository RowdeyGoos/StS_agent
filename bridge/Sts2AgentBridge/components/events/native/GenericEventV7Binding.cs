using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
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
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

internal sealed class GenericEventV7Binding
{
    internal GenericEventV7Binding(NRun run,Player player,NEventRoom room,NMapScreen map,
        NOverlayStack overlays,NEventLayout layout,EventModel model,EventOption option,
        NEventOptionButton controller,string nonce,string decision,string action)
    {
        Run=run; Player=player; Room=room; Map=map; Overlays=overlays; Layout=layout;
        EventModel=model; Option=option; Controller=controller; Nonce=nonce; Decision=decision; Action=action;
        RunState=player.RunState; OptionKey=option.TextKey;
        PreDispatchDeck=CopyDeck(player); SelectionDeck=PreDispatchDeck;
        // Reservation is the final authority check for this presentation node.
        // Native event dispatch may remove and free it before Chosen runs.
        if (!ContextValid(false) || overlays.ScreenCount!=0 || !Valid(Controller) ||
            !ReferenceEquals(Controller.Event,EventModel) || !ReferenceEquals(Controller.Option,Option)) throw new InvalidOperationException("Invalid reservation.");
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
    // Opaque receipt after reservation; never read or click the retired node.
    internal NEventOptionButton Controller {get;}
    internal string Nonce {get;}
    internal string Decision {get;}
    internal string Action {get;}
    internal string OptionKey {get;}
    internal CardSelectionV1DeckCard[] PreDispatchDeck {get;}
    internal CardSelectionV1DeckCard[] SelectionDeck {get;private set;}
    private bool _selectionDeckBound;
    internal CardSelectorPrefs Prefs;
    internal bool Failed,Closed,ChosenSeen,RequestSeen,ScreenSeen;
    internal Task? ChosenTask;
    internal Task<IEnumerable<CardModel>>? RequestTask;
    internal NCardGridSelectionScreen? Screen;
    internal CardSelectionV1Operation Operation=CardSelectionV1Operation.Upgrade;
    internal Func<CardModel,bool>? RemovalPredicate;
    internal bool GenericDeckTransform;
    internal EnchantmentModel? EnchantmentModel;
    internal CardSelectionV1Enchantment? Enchantment;
    internal GenericEventV7Admission? Admission;
    internal PlayerChoiceContext? RewardContext;
    internal List<CardCreationResult>? RewardList;
    internal CardCreationResult[] RewardEntries=Array.Empty<CardCreationResult>();
    internal string[] RewardKeys=Array.Empty<string>();
    internal int[] RewardLevels=Array.Empty<int>();
    internal CardSelectionV1CommitMode CommitMode=>Operation!=CardSelectionV1Operation.Add?CardSelectionV1CommitMode.PreviewConfirm:
        Prefs.RequireManualConfirmation?CardSelectionV1CommitMode.ExplicitConfirm:CardSelectionV1CommitMode.AutoAtMax;
    internal string CommitModeName=>CommitMode==CardSelectionV1CommitMode.PreviewConfirm?"preview_confirm":
        CommitMode==CardSelectionV1CommitMode.ExplicitConfirm?"explicit_confirm":"auto_at_max";
    internal bool CaptureOffers(List<CardCreationResult> offers)
    {
        if((Prefs.MinSelect==0 ? offers.Count<1 : offers.Count<=Prefs.MaxSelect)||offers.Count>64||SelectionDeck.Length+Prefs.MaxSelect>512)return false;
        RewardList=offers;RewardEntries=offers.ToArray();Originals=new CardModel[offers.Count];RewardKeys=new string[offers.Count];RewardLevels=new int[offers.Count];
        var entries=new HashSet<object>(ReferenceEqualityComparer.Instance);var originals=new HashSet<object>(ReferenceEqualityComparer.Instance);
        for(int i=0;i<RewardEntries.Length;i++)
        {
            var entry=RewardEntries[i];var card=entry?.Card;
            if(entry is null||!entries.Add(entry)||card is null||!originals.Add(card)||
                !ReferenceEquals(card.Owner,Player)||!ReferenceEquals(card.RunState,RunState)||
                SelectionDeck.Any(d=>ReferenceEquals(d.ModelIdentity,card))||
                !CardSelectionV1NativeRules.IsStableKey(card.Id.Entry)||card.CurrentUpgradeLevel<0)return false;
            Originals[i]=card;RewardKeys[i]=card.Id.Entry;RewardLevels[i]=card.CurrentUpgradeLevel;
        }
        return MatchesOffers();
    }
    internal bool MatchesOffers()
    {
        if(Operation!=CardSelectionV1Operation.Add)return true;
        try
        {
            if(RewardContext is null||RewardList is null||RewardList.Count!=RewardEntries.Length||Originals.Length!=RewardEntries.Length)return false;
            for(int i=0;i<RewardEntries.Length;i++)
            {
                var card=Originals[i];
                if(!ReferenceEquals(RewardList[i],RewardEntries[i])||!ReferenceEquals(RewardEntries[i].Card,card)||
                    !ReferenceEquals(card.Owner,Player)||!ReferenceEquals(card.RunState,RunState)||
                    card.Id.Entry!=RewardKeys[i]||card.CurrentUpgradeLevel!=RewardLevels[i])return false;
            }
            return true;
        }
        catch{return false;}
    }
    internal GenericEventV7ItemState? Item;
    internal GenericEventV7MultiUpgradeState? MultiUpgrade;
    internal GenericEventV7TransformState? Transform;
    internal Func<CardModel,CardTransformation>? TransformFunction,EffectiveTransformFunction;
    internal HashSet<object> ObservedCommandTasks=new(ReferenceEqualityComparer.Instance);
    internal HashSet<object> ObservedUpgradeClones=new(ReferenceEqualityComparer.Instance);
    internal HashSet<object> ObservedPreviewClones=new(ReferenceEqualityComparer.Instance);
    internal CardModel[] Originals=Array.Empty<CardModel>();
    internal int DomainCount=>Originals.Length;
    internal IReadOnlyList<CardModel> EligibleOriginals=>Originals;
    internal bool Ready=>!Failed && !Closed && ChosenTask is not null && RequestTask is not null && Screen is not null;
    internal bool SamePrefs(CardSelectorPrefs other)=>other.MinSelect==Prefs.MinSelect &&
        other.MaxSelect==Prefs.MaxSelect && other.Cancelable==Prefs.Cancelable &&
        other.RequireManualConfirmation==Prefs.RequireManualConfirmation &&
        ReferenceEquals(other.Comparison,Prefs.Comparison) && other.UnpoweredPreviews==Prefs.UnpoweredPreviews &&
        other.PretendCardsCanBePlayed==Prefs.PretendCardsCanBePlayed && ReferenceEquals(other.ShouldGlowGold,Prefs.ShouldGlowGold);
    internal bool MatchesChildBinding()=>!Failed && !Closed && GenericEventV7Hooks.Owns(this) && ContextValid(false) && MatchesOffers() && AddedCardInvariantsValid();
    internal bool ContextValid(bool exit)=>
        !Closed && ReferenceEquals(NRun.Instance,Run) && ReferenceEquals(Run.EventRoom,Room) &&
        ReferenceEquals(NEventRoom.Instance,Room) && ReferenceEquals(NMapScreen.Instance,Map) &&
        ReferenceEquals(Run.GlobalUi?.MapScreen,Map) && ReferenceEquals(Run.GlobalUi?.Overlays,Overlays) &&
        ReferenceEquals(Room.Layout,Layout) && ReferenceEquals(EventModel.Owner,Player) &&
        ReferenceEquals(Player.RunState,RunState) && Option.TextKey==OptionKey &&
        Valid(Run)&&Valid(Room)&&Valid(Map)&&Valid(Overlays)&&Valid(Layout) &&
        (exit || Room.IsVisibleInTree()) && Room.CustomEventNode is null && Room.EmbeddedCombatRoom is null &&
        CardSelectCmd.Selector is null && (exit || !Map.IsOpen && !Map.IsTravelEnabled && !Map.IsTraveling);
    private static bool Valid(GodotObject obj)=>GodotObject.IsInstanceValid(obj);
    // The native option may append cards before asking for a selector. Bind
    // once, at the owned request entry, without certifying those parent effects.
    // Existing originals cannot change, disappear, or move in this increment.
    internal bool BindSelectionDeck()
    {
        try
        {
            if (_selectionDeckBound || Failed || RequestSeen || ScreenSeen ||
                !GenericEventV7Hooks.Owns(this) || !ContextValid(false) || Overlays.ScreenCount!=0) return false;
            var deck=CopyDeck(Player);
            if (deck.Length<PreDispatchDeck.Length) return false;
            for (int i=0;i<PreDispatchDeck.Length;i++)
                if (!SameDeckCard(deck[i],PreDispatchDeck[i])) return false;
            if (deck.Skip(PreDispatchDeck.Length).Any(c=>c.ModelIdentity is not CardModel card ||
                !ReferenceEquals(card.Owner,Player) || !ReferenceEquals(card.RunState,RunState))) return false;
            SelectionDeck=deck; _selectionDeckBound=true;
            return true;
        }
        catch { return false; }
    }
    private static bool SameDeckCard(CardSelectionV1DeckCard a,CardSelectionV1DeckCard b)=>
        ReferenceEquals(a.ModelIdentity,b.ModelIdentity) && a.StableKey==b.StableKey &&
        a.UpgradeLevel==b.UpgradeLevel && CardSelectionV1Enchantment.Same(a.Enchantment,b.Enchantment);
    // Non-enchantment child codecs omit enchantments. Keep those identities
    // for the newly admitted baseline cards here; enchant children validate
    // selected-only enchantment changes with their full deck snapshots.
    private bool AddedCardInvariantsValid()=>SelectionDeck.Skip(PreDispatchDeck.Length).All(c=>
        c.ModelIdentity is CardModel card && (!Player.Deck.Cards.Contains(card) ||
        ReferenceEquals(card.Owner,Player) && ReferenceEquals(card.RunState,RunState) &&
        (Operation==CardSelectionV1Operation.Enchant || CardSelectionV1Enchantment.Same(CopyEnchantment(card),c.Enchantment))));
    internal bool MatchesCurrentDeck()
    {
        try
        {
            var deck=CopyDeck(Player);
            return AddedCardInvariantsValid() && deck.Length==SelectionDeck.Length && deck.Where((c,i)=>
                !ReferenceEquals(c.ModelIdentity,SelectionDeck[i].ModelIdentity)||
                c.StableKey!=SelectionDeck[i].StableKey || c.UpgradeLevel!=SelectionDeck[i].UpgradeLevel ||
                !CardSelectionV1Enchantment.Same(c.Enchantment,SelectionDeck[i].Enchantment)).Any()==false;
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
            deck.Add(new CardSelectionV1DeckCard(card,card.Id.Entry,card.CurrentUpgradeLevel,CopyEnchantment(card)));
        }
        return deck.ToArray();
    }
    internal static CardSelectionV1Enchantment? CopyEnchantment(CardModel card)
    {
        if (card.Enchantment is not { } e) return null;
        if (!ReferenceEquals(e.Card,card) || !CardSelectionV1NativeRules.IsStableKey(e.Id.Entry) || e.Amount < 1)
            throw new InvalidOperationException("Invalid card enchantment.");
        return new(e,e.Id.Entry,e.Amount);
    }
    private CardModel[]? _requestResult;
    internal bool EffectCompleted(IReadOnlyList<object> selected)
    {
        if(!MatchesChildBinding() || ChosenTask?.IsCompletedSuccessfully!=true ||
            RequestTask?.IsCompletedSuccessfully!=true || selected.Count<Prefs.MinSelect || selected.Count>Prefs.MaxSelect) return false;
        try
        {
            var values=_requestResult ??= RequestTask.Result.Take(Prefs.MaxSelect+1).ToArray();
            var set=new HashSet<object>(values,ReferenceEqualityComparer.Instance);
            if(values.Length!=selected.Count || set.Count!=values.Length || values.Any(c=>c is null) ||
                !set.SetEquals(selected) || !values.All(c=>Originals.Any(o=>ReferenceEquals(c,o)))) {Failed=true;return false;}
            return true;
        }
        catch {Failed=true;return false;}
    }
    internal CardSelectionV1ParentContext Context()=>new(Nonce,CardSelectionV1ParentKind.Event,
        Decision,Action,this,Run,Player,Room,Map,Option,Controller,Operation,
        Prefs.MinSelect,Prefs.MaxSelect,CommitMode,DomainCount,Enchantment,Operation==CardSelectionV1Operation.Remove,Prefs.MinSelect==0);
    internal bool MatchesAcceptedParent(CardSelectionV1ParentContext context)=>
        ReferenceEquals(context.ParentReceiptIdentity,this)&&ReferenceEquals(context.ParentOptionIdentity,Option)&&
        context.AllowRemovalParentAppend==(Operation==CardSelectionV1Operation.Remove)&&
        context.Operation==Operation&&context.MinSelect==Prefs.MinSelect&&context.MaxSelect==Prefs.MaxSelect&&
        context.CommitMode==CommitMode&&
        context.ExpectedDomainCount==DomainCount && CardSelectionV1Enchantment.Same(context.Enchantment,Enchantment);
}
