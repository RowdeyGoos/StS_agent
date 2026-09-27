using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Items.Native;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

internal sealed partial class GenericEventCompoundRewards
{
    private static bool DeckRelic(RelicModel relic)=>Named(relic,"PreciseScissors","PrecariousShears","Pomander","NewLeaf","LeafyPoultice");
    private readonly List<DeckLeaf> _decks=new();
    private DeckLeaf? _publishedDeck;
    internal sealed class DeckLeaf:IPinnedClosingOverlay
    {
        internal readonly GenericEventCompoundRewards Owner;
        internal readonly RewardFrame Reward;
        internal readonly PinnedRelicPickupChain.Frame Pickup;
        internal readonly string Kind;
        private bool Automatic=>Named(Pickup.Relic,"LeafyPoultice");
        internal readonly PinnedAutomaticRelicEffects.State Before;
        internal readonly CardModel[] Eligible;
        internal readonly List<(string Kind,Task<IEnumerable<CardModel>>? Task)> Requests=new();
        internal readonly List<Removal> Removals=new();
        internal PinnedAutomaticRelicEffects? Effects;
        internal GenericEventV7TransformState? Transform;
        internal PinnedDeckCardChoice? Choice;
        internal Control? Screen;
        internal DeckChoiceView? View;
        internal CardSelectorPrefs Prefs;
        internal CardModel[]? Selected;
        internal Receipt? Pending;
        internal CardModel[]? Desired;
        internal bool Done,Cleaned,ScreenEntering;
        private readonly HashSet<CardModel> _upgraded=new(ReferenceEqualityComparer.Instance);
        private readonly Dictionary<CardModel,PinnedAutomaticRelicEffects.Card> _insertions=new(ReferenceEqualityComparer.Instance);
        private PinnedAutomaticRelicEffects.State? _certificate;
        public bool EffectCertified=>_certificate is not null;
        public bool ClosingOwnerValid=>Owner.Context()&&Requests.All(r=>r.Task?.IsFaulted!=true&&r.Task?.IsCanceled!=true)&&
            Pickup.AfterTask?.IsFaulted!=true&&Pickup.AfterTask?.IsCanceled!=true;
        public PinnedOverlayPrefix Ancestors {get;}
        public IReadOnlyList<Control> ClosingScreens=>Screen is null?Array.Empty<Control>():new[]{Screen};
        internal DeckLeaf(GenericEventCompoundRewards owner,RewardFrame reward,PinnedRelicPickupChain.Frame pickup)
        {
            Owner=owner;Reward=reward;Pickup=pickup;Before=new(owner._binding.Player);
            Kind=Named(pickup.Relic,"Pomander")?"upgrade":Named(pickup.Relic,"NewLeaf","LeafyPoultice")?"transform":"remove";
            Eligible=Before.Deck.Select(c=>c.Model).Where(c=>Kind=="upgrade"?c.IsUpgradable:Kind=="transform"?(int)c.Type!=6&&c.IsTransformable:c.IsRemovable).ToArray();
            if(Automatic) {
                var basics=Before.Deck.Select(c=>c.Model).Where(c=>Rarity(c)=="Basic").ToArray();
                Eligible=new[]{basics.FirstOrDefault(c=>Tagged(c,"Strike")),basics.FirstOrDefault(c=>Tagged(c,"Defend"))}
                    .Where(c=>c is not null).Cast<CardModel>().Distinct<CardModel>(ReferenceEqualityComparer.Instance).ToArray();
                Selected=Eligible.ToArray();
            }
            if(Kind=="remove")Eligible=Eligible.OrderBy(c=>(int)c.Type==5?-1:Array.FindIndex(Before.Deck,d=>ReferenceEquals(d.Model,c))).ToArray();
            Ancestors=new(owner._binding.Overlays,owner.Path(reward).Select(f=>(Control)f.Screen!).ToArray());
        }
        internal IDisposable Enter()
        {
            if(!Automatic)Owner.ObserveGridPreviews();
            if(Kind=="remove")Owner.ObserveRemovals();
            var policy=new PinnedAutomaticRelicEffects.CompoundPolicy {
                Authority=()=>ReferenceEquals(Owner.NativePickup,Pickup)&&Pickup.Certificate is null,
                Hp=Named(Pickup.Relic,"PrecariousShears","LeafyPoultice"),Damage=Named(Pickup.Relic,"PrecariousShears","LeafyPoultice"),
                Added=c=>Transform?.AddedCard(c)==true,Modifying=()=>Transform?.InModification==true,
                BeforeMutation=AdvanceDeck,
                PreviewUpgrade=c=>Owner.PreviewUpgrade(this,c),
                Upgrade=c=>Kind=="upgrade"&&PrepareSelected()&&Selected!.Contains(c)&&_upgraded.Add(c)
            };
            Effects=new(Owner._binding.Player,Pickup.Relic,Owner.Context,policy);return Effects.EnterLease();
        }
        internal int Request(Player player,CardSelectorPrefs prefs,string source,object? filter)
        {
            Owner.Require(!Automatic&&ReferenceEquals(player,Owner._binding.Player)&&ReferenceEquals(Owner.NativePickup,Pickup)&&
                ReferenceEquals(Owner.CurrentFrame(),Reward)&&!EffectCertified&&Screen is null&&Effects!.Valid());
            if(Requests.Count==0) {
                Owner.Require(source==Kind||Kind=="remove"&&source=="generic");
                int count=Pickup.Relic.DynamicVars["Cards"].IntValue;
                Owner.Require(count==(Named(Pickup.Relic,"PrecariousShears")?2:1)&&prefs.MinSelect==count&&prefs.MaxSelect==count&&
                    !prefs.Cancelable&&!prefs.RequireManualConfirmation&&Eligible.Length<=64&&(source=="generic"||filter is null));
                Prefs=prefs;
            } else Owner.Require(Kind=="remove"&&source=="generic"&&Requests.Count==1&&Requests[0].Kind=="remove"&&SamePrefs(prefs));
            Requests.Add((source,null));return Requests.Count-1;
        }
        private bool SamePrefs(CardSelectorPrefs prefs)=>prefs.MinSelect==Prefs.MinSelect&&prefs.MaxSelect==Prefs.MaxSelect&&prefs.Cancelable==Prefs.Cancelable&&
            prefs.RequireManualConfirmation==Prefs.RequireManualConfirmation&&prefs.Prompt is {} prompt&&Prefs.Prompt is {} expected&&prompt.LocTable==expected.LocTable&&prompt.LocEntryKey==expected.LocEntryKey;
        internal void Requested(int index,Task<IEnumerable<CardModel>> task)
        {Owner.Require(index>=0&&index<Requests.Count&&Requests[index].Task is null&&task is not null);Requests[index]=(Requests[index].Kind,task);}
        internal void EnterScreen(IReadOnlyList<CardModel> domain,CardSelectorPrefs prefs,string kind,object? run=null)
        {
            Owner.Require(Owner.Context()&&ReferenceEquals(Owner.NativePickup,Pickup)&&ReferenceEquals(Owner.CurrentFrame(),Reward)&&
                Requests.Count>0&&Kind==kind&&Screen is null&&!ScreenEntering&&SamePrefs(prefs)&&
                (run is null||ReferenceEquals(run,Before.Run))&&Eligible.Length>Prefs.MinSelect&&
                domain.SequenceEqual(Eligible,ReferenceEqualityComparer.Instance)&&Effects!.Valid());
            ScreenEntering=true;
        }
        internal void BindScreen(Control screen)
        {
            Owner.Require(ScreenEntering&&Screen is null&&screen.GetType()==(Kind=="upgrade"?typeof(NDeckUpgradeSelectScreen):Kind=="transform"?typeof(NDeckTransformSelectScreen):typeof(NDeckCardSelectScreen)));
            Screen=screen;ScreenEntering=false;
            Choice=new(screen,Owner._binding.Overlays,Eligible,Owner.Context,null,0,Prefs.MinSelect,Prefs.MaxSelect,false,Kind=="upgrade",
                Owner.Path(Reward).Select(f=>(Control)f.Screen!).ToArray(),Kind=="transform");
        }
        private bool PrepareSelected()
        {
            if(Automatic)return Selected is not null;
            Owner.Require(Requests.Count is >=1 and <=2&&Requests.All(r=>r.Task?.IsFaulted!=true&&r.Task?.IsCanceled!=true));
            if(Requests.Any(r=>r.Task?.IsCompletedSuccessfully!=true))return false;
            var expected=Choice is not null?(Choice.ConfirmationDispatched?Choice.Selected:null):Eligible.Length<=Prefs.MinSelect?Eligible:null;
            Owner.Require(expected is not null&&expected.Length<=Prefs.MaxSelect&&expected.All(Eligible.Contains));
            foreach(var request in Requests) {
                var result=request.Task!.Result.Take(4).ToArray();
                Owner.Require(result.Length==expected!.Length&&result.Distinct(ReferenceEqualityComparer.Instance).Count()==result.Length&&result.All(expected.Contains));
            }
            if(Selected is null)Selected=expected!.ToArray();else Owner.Require(Selected.SequenceEqual(expected,ReferenceEqualityComparer.Instance));
            return true;
        }
        internal GenericEventV7TransformState Transformation()
        {
            Owner.Require(Kind=="transform"&&ReferenceEquals(Owner.NativePickup,Pickup)&&PrepareSelected()&&(Automatic||Selected!.Length>0));
            if(Transform is null) {
                Transform=new(Owner._binding.Player,Before.Run,Owner.Context,Owner.Fail,GenericEventV7Binding.CopyDeck(Owner._binding.Player),Eligible,
                    Selected!.Length,Automatic?Math.Max(1,Selected.Length):Prefs.MaxSelect,AdvanceDeck);
                Transform.Reserve(Selected);
            }
            return Transform;
        }
        private void AdvanceDeck()
        {
            if(Kind=="upgrade"){Owner.Require(Effects!.Valid());return;}
            if(!Automatic&&Requests.Count==0||!PrepareSelected()){Owner.Require(Effects!.Valid());return;}
            Owner.Require(Removals.All(r=>r.Task?.IsFaulted!=true&&r.Task?.IsCanceled!=true));
            var removed=Kind=="remove"?Removals.Select(r=>(object)r.Card).Where(c=>!Owner._binding.Player.Deck.Cards.Any(d=>ReferenceEquals(c,d))).ToArray():
                Transform?.Capture().RemovedOriginals.ToArray()??Array.Empty<object>();
            var inserted=Transform?.Capture().OrderedCommittedInsertions.Select(i=>(CardModel)i.FinalIdentity).ToArray()??Array.Empty<CardModel>();
            var now=new PinnedAutomaticRelicEffects.State(Owner._binding.Player);
            foreach(var card in inserted)if(!_insertions.ContainsKey(card))_insertions.Add(card,now.Deck.Single(c=>ReferenceEquals(c.Model,card)));
            var expected=Before.Deck.Where(c=>!removed.Contains(c.Model,ReferenceEqualityComparer.Instance)).Concat(inserted.Select(c=>_insertions[c])).ToArray();
            Effects!.CertifyDeck((_,after)=>after.SequenceEqual(expected));
        }
        internal bool Validate()
        {
            if(EffectCertified)return true;
            AdvanceDeck();if(!Effects!.Valid())return false;
            if(Pickup.AfterTask?.IsCompletedSuccessfully!=true||Pickup.ObtainTask?.IsCompletedSuccessfully!=true)return true;
            Owner.Require(PrepareSelected()&&Effects.CardEffectsCompleted);
            if(Kind=="remove")Owner.Require(Removals.Count==Selected!.Length&&Removals.All(r=>r.Task?.IsCompletedSuccessfully==true)&&Selected.All(c=>!Owner._binding.Player.Deck.Cards.Contains(c)));
            if(Kind=="upgrade")Owner.Require(Selected!.All(c=>c.CurrentUpgradeLevel==Before.Deck.Single(d=>ReferenceEquals(d.Model,c)).Level+1));
            if(Kind=="transform")Owner.Require(!Automatic&&Selected!.Length==0?Transform is null:Transform?.Complete==true);
            Owner.Require(Screen is null?Ancestors.Bare:Ancestors.Bare||Ancestors.Matches(Screen));
            _certificate=new(Owner._binding.Player);Owner._expected[Pickup]=_certificate;return true;
        }
        internal void CleanupEffects()
        {if(Cleaned)return;Owner.Require(EffectCertified);Effects!.Dispose();Cleaned=true;}
        internal void Read()
        {
            Owner.Require(ClosingOwnerValid);View=null;if(Done)return;
            if(!EffectCertified&&Pickup.AfterTask?.IsCompletedSuccessfully==true&&Pickup.ObtainTask?.IsCompletedSuccessfully==true)Owner.Require(Pickup.Owner.TryCertify(Pickup));
            if(EffectCertified) {
                Owner.Require(Screen is null||Ancestors.Retiring(Screen,Array.Empty<IPinnedClosingOverlay>()));
                if(Screen is null||Ancestors.Closed(Screen)&&Choice!.Completed){Done=true;if(Pending is not null){Pending.Done=true;Pending=null;}}return;
            }
            AdvanceDeck();Owner.Require(Effects!.Valid());
            if(Choice is null)return;
            if(Choice.ConfirmationDispatched){Choice.Read();return;}
            Owner.DeckInput(this,()=>View=Choice.Read());
            if(EffectCertified){Read();return;}
            if(View is not null&&Pending is not null) {
                Owner.Require(Desired is not null&&View.Selected.Length==Desired.Length&&View.Selected.All(Desired.Contains));Pending.Done=true;Pending=null;Desired=null;
            }
        }
        internal void Apply(string decision,string action)
        {
            Owner.Require(View is not null&&Pending is null&&Choice is not null);
            Pending=new(decision,action,0,Reward);Owner._receipts.Add(Pending);
            CardModel? card=null;string verb=action;
            if(action.Contains(':')){var parts=action.Split(':');verb=parts[0];card=Eligible[int.Parse(parts[1])];}
            Desired=verb=="select"?View!.Selected.Append(card!).ToArray():verb=="deselect"?View!.Selected.Where(c=>!ReferenceEquals(c,card)).ToArray():View!.Selected;
            Owner.DeckInput(this,()=>Choice!.Apply(verb,card));
        }
        internal Removal Removing(CardModel card,bool preview)
        {
            AdvanceDeck();
            Owner.Require(Kind=="remove"&&ReferenceEquals(Owner.NativePickup,Pickup)&&PrepareSelected()&&Selected!.Contains(card)&&
                !Removals.Any(r=>ReferenceEquals(r.Card,card))&&Removals.All(r=>r.Task?.IsCompletedSuccessfully==true)&&preview&&Effects!.Valid());
            var call=new Removal(this,card);Removals.Add(call);return call;
        }
    }
    private void DeckInput(DeckLeaf leaf,Action input)
    {
        Require(Native.Value is null);Native.Value=leaf.Reward;
        try{leaf.Pickup.Owner.InvokeChildInput(leaf.Pickup,input);}finally{Native.Value=null;}
    }
    internal DeckLeaf DeckRequest(Player player,CardSelectorPrefs prefs,string source,object? filter,out int index)
    {
        var leaf=_decks.SingleOrDefault(d=>ReferenceEquals(d.Pickup,NativePickup));Require(leaf is not null);
        index=leaf!.Request(player,prefs,source,filter);return leaf;
    }
    internal DeckLeaf DeckScreen(IReadOnlyList<CardModel> cards,CardSelectorPrefs prefs,string kind,object? run=null)
    {var leaf=_decks.SingleOrDefault(d=>ReferenceEquals(d.Pickup,NativePickup));Require(leaf is not null);leaf!.EnterScreen(cards,prefs,kind,run);return leaf;}
    internal GenericEventV7TransformState? NativeTransformation()
    {
        var leaf=_decks.SingleOrDefault(d=>ReferenceEquals(d.Pickup,NativePickup));
        Require(leaf is not null);return leaf!.Transformation();
    }
    private void ReadDecks(){foreach(var leaf in _decks)leaf.Read();}
    private GenericEventV7RewardRead? ReadDeckLeaf()
    {
        var leaf=_decks.LastOrDefault(d=>!d.Done);if(leaf is null)return null;
        if(leaf.View is not {} view||leaf.Pending is not null)return Value("waiting","waiting");
        var actions=new List<string>();
        for(int i=0;i<view.Domain.Length;i++) {
            if(view.Selected.Contains(view.Domain[i]))actions.Add("deselect:"+i);
            else if(view.Selected.Length<view.Maximum)actions.Add("select:"+i);
        }
        if(view.Selected.Length>=view.Minimum)actions.Add("confirm");Require(actions.Count>0);
        Publish(leaf.Reward,"deck:"+_decks.IndexOf(leaf)+":"+string.Join(",",view.Selected.Select(c=>Array.IndexOf(leaf.Eligible,c))));_publishedDeck=leaf;
        return Value("ready","deck_"+leaf.Kind,actions);
    }
    private bool ApplyDeckLeaf(string decision,string action)
    {if(_publishedDeck is not {} leaf)return false;leaf.Apply(decision,action);return true;}
    private IEnumerable<IPinnedClosingOverlay> ClosingDecks(RewardFrame frame)=>_decks.Where(d=>!d.Done&&d.EffectCertified&&Path(d.Reward).Contains(frame)&&
        d.Screen is {} screen&&!d.Ancestors.Closed(screen)).Cast<IPinnedClosingOverlay>();
    private void DisposeDecks()
    {
        Exception? failure=null;
        foreach(var leaf in _decks)try{leaf.Effects?.Dispose();leaf.Transform?.Close();}catch(Exception error){failure??=error;}
        if(failure is not null)throw new InvalidOperationException("compound_deck_cleanup",failure);
    }
    private sealed class GridPreview
    {
        internal readonly DeckLeaf Leaf;
        internal readonly NGridCardHolder Holder;
        internal readonly CardModel Original;
        internal readonly object? Previous;
        internal readonly PinnedAutomaticRelicEffects.State Before;
        internal readonly int Level;
        internal readonly bool Upgradable;
        internal CardModel? Clone;
        internal GridPreview(DeckLeaf leaf,NGridCardHolder holder)
        {
            Leaf=leaf;Holder=holder;Original=holder.CardNode.Model;Previous=Field(holder,"_upgradedCard");
            Before=new(leaf.Owner._binding.Player);Level=Original.CurrentUpgradeLevel;Upgradable=Original.IsUpgradable;
        }
    }
    private GridPreview? _gridPreview;
    private MethodInfo? _gridPreviewMethod;
    private void ObserveGridPreviews()
    {
        if(_gridPreviewMethod is not null)return;
        var method=typeof(NGridCardHolder).GetMethod("UpdateCardModel",BindingFlags.Instance|BindingFlags.NonPublic);
        Require(method is not null&&method.ReturnType==typeof(void)&&method.GetParameters().Length==0&&
            method.GetMethodBody() is not null&&!(Harmony.GetPatchInfo(method)?.Owners.Any()??false));
        _gridPreviewMethod=method;
        _hooks.Patch(method,new HarmonyMethod(typeof(GenericEventCompoundRewards),nameof(GridPreviewEntering)),
            new HarmonyMethod(typeof(GenericEventCompoundRewards),nameof(GridPreviewFinished)),
            finalizer:new HarmonyMethod(typeof(GenericEventCompoundRewards),nameof(GridPreviewFailed)));
    }
    private bool GridPreviewHooksValid()=>_gridPreviewMethod is null||Harmony.GetPatchInfo(_gridPreviewMethod) is {} info&&info.Owners.Count==1&&info.Owners.Contains(_hooks.Id);
    private static void GridPreviewEntering(NGridCardHolder __instance,out GridPreview? __state)
    {
        __state=null;var owner=Active;if(owner is null)return;
        var leaf=owner._decks.SingleOrDefault(d=>d.Effects?.IsCurrent==true);if(leaf is null)return;
        owner.Require(owner.Context()&&owner._gridPreview is null&&ReferenceEquals(owner.NativePickup,leaf.Pickup)&&
            ReferenceEquals(owner.CurrentFrame(),leaf.Reward)&&!leaf.EffectCertified&&leaf.Requests.Count>0&&
            __instance.GetType()==typeof(NGridCardHolder)&&leaf.Eligible.Contains(__instance.CardNode.Model)&&leaf.Effects!.Valid());
        var call=new GridPreview(leaf,__instance);
        owner.Require(call.Before.Deck.Any(c=>ReferenceEquals(c.Model,call.Original)));
        owner._gridPreview=__state=call;
    }
    private bool PreviewUpgrade(DeckLeaf leaf,CardModel card)
    {
        if(_gridPreview is not {} call)return false;
        Require(ReferenceEquals(call.Leaf,leaf)&&leaf.Effects!.IsCurrent&&call.Upgradable&&call.Clone is null&&
            ReferenceEquals(NativePickup,leaf.Pickup)&&leaf.Effects.Valid()&&
            ReferenceEquals(Field(call.Holder,"_baseCard"),call.Original)&&ReferenceEquals(Field(call.Holder,"_upgradedCard"),card)&&
            !ReferenceEquals(card,call.Previous)&&!call.Before.Deck.Any(c=>ReferenceEquals(c.Model,card))&&
            ReferenceEquals(card.Owner,_binding.Player)&&ReferenceEquals(card.RunState,call.Before.Run)&&
            card.GetType()==call.Original.GetType()&&card.Id.Entry==call.Original.Id.Entry&&card.Type==call.Original.Type&&
            card.CurrentUpgradeLevel==call.Level&&card.IsUpgradable);
        call.Clone=card;return true;
    }
    private static void GridPreviewFinished(GridPreview? __state)
    {
        if(__state is not {} call)return;var owner=call.Leaf.Owner;
        try {
            owner.Require(ReferenceEquals(owner._gridPreview,call)&&call.Leaf.Effects!.IsCurrent&&call.Leaf.Effects.Valid()&&
                ReferenceEquals(owner.NativePickup,call.Leaf.Pickup)&&call.Before.Same(new(owner._binding.Player))&&
                ReferenceEquals(Field(call.Holder,"_baseCard"),call.Original)&&
                (call.Upgradable?call.Clone is {} clone&&ReferenceEquals(Field(call.Holder,"_upgradedCard"),clone)&&clone.CurrentUpgradeLevel==call.Level+1:call.Clone is null));
        }finally{if(ReferenceEquals(owner._gridPreview,call))owner._gridPreview=null;}
    }
    private static void GridPreviewFailed(Exception? __exception,GridPreview? __state)
    {
        if(__state is not {} call)return;var owner=call.Leaf.Owner;
        if(__exception is not null)owner.Fail();
        if(ReferenceEquals(owner._gridPreview,call))owner._gridPreview=null;
    }
    internal sealed class Removal
    {
        internal readonly DeckLeaf Leaf;internal readonly CardModel Card;internal Task? Task;
        internal Removal(DeckLeaf leaf,CardModel card){Leaf=leaf;Card=card;}
    }
    private MethodInfo? _removeMethod;
    private void ObserveRemovals()
    {
        if(_removeMethod is not null)return;
        var method=typeof(CardPileCmd).GetMethod("RemoveFromDeck",new[]{typeof(CardModel),typeof(bool)})!;
        Require(method is not null&&method.ReturnType==typeof(Task)&&!(Harmony.GetPatchInfo(method)?.Owners.Any()??false));
        _removeMethod=method;
        _hooks.Patch(method,new HarmonyMethod(typeof(GenericEventCompoundRewards),nameof(Removing)),new HarmonyMethod(typeof(GenericEventCompoundRewards),nameof(Removed)),
            finalizer:new HarmonyMethod(typeof(GenericEventCompoundRewards),nameof(RemovalFailed)));
    }
    private bool RemovalHooksValid()=>_removeMethod is null||Harmony.GetPatchInfo(_removeMethod) is {} info&&info.Owners.Count==1&&info.Owners.Contains(_hooks.Id);
    private static void Removing(CardModel __0,bool __1,out Removal? __state)
    {
        __state=null;var owner=Active;if(owner is null)return;
        var leaf=owner._decks.SingleOrDefault(d=>ReferenceEquals(d.Pickup,owner.NativePickup));
        if(leaf?.Kind=="remove")__state=leaf.Removing(__0,__1);
    }
    private static void Removed(Task __result,Removal? __state)
    {if(__state is {} call){call.Leaf.Owner.Require(__result is not null&&call.Task is null);call.Task=__result;}}
    private static void RemovalFailed(Exception? __exception,Removal? __state)
    {if(__exception is not null)__state?.Leaf.Owner.Fail();}
}
