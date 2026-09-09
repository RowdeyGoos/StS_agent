using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// Owns one native request and its exact generated models. No reward-set owner is fabricated.
internal sealed class GenericEventV7OfferAdapter:IGenericEventV7OfferAdapter {
    internal readonly GenericEventV7Binding Binding;
    internal readonly bool Bundle;
    internal readonly object DomainIdentity;
    private readonly IReadOnlyList<CardModel>[] _lists;
    private readonly CardModel[][] _models;
    private readonly CardSelectionV1DeckCard[][] _cards;
    private readonly CardSelectionV1DeckCard[] _deck;
    private readonly GenericEventV7Offer[] _public;
    internal Control? Screen;internal Task? RequestTask;
    internal bool ScreenEntered;
    private Task? _selectorTask;
    private GodotObject[]? _hitboxes;
    private Control? _row,_preview,_previewCards;
    private NConfirmButton? _confirm;
    private NGridCardHolder[]? _holders;
    private NCardBundle[]? _bundles;
    private NCard[][]? _nodes;
    private NPreviewCardHolder[]? _previewHolders;
    private int? _selected;private bool _confirmed,_disposed;
    private int _added;
    internal int Count=>_models.Length;
    internal GenericEventV7OfferAdapter(GenericEventV7Binding binding,object identity,IReadOnlyList<CardModel>[] offers,bool bundle) {
        Binding=binding;DomainIdentity=identity;Bundle=bundle;_lists=offers;_models=offers.Select(o=>o.ToArray()).ToArray();
        _deck=GenericEventV7Binding.CopyDeck(binding.Player);
        if(Count<1||Count>(bundle?5:3)||_models.Any(o=>o.Length<1||o.Length>(bundle?8:1))||_deck.Length+_models.Max(o=>o.Length)>512)throw new InvalidOperationException("Offer bounds.");
        var all=_models.SelectMany(o=>o).ToArray();
        if(all.Distinct(ReferenceEqualityComparer.Instance).Count()!=all.Length||all.Any(c=>c is null||_deck.Any(d=>ReferenceEquals(d.ModelIdentity,c))))throw new InvalidOperationException("Ambiguous offers.");
        _cards=_models.Select(o=>o.Select(c=>new CardSelectionV1DeckCard(c,c.Id.Entry,c.CurrentUpgradeLevel,GenericEventV7Binding.CopyEnchantment(c))).ToArray()).ToArray();
        _public=_cards.Select((o,i)=>new GenericEventV7Offer(i,o.Select((c,j)=>new GenericEventV7RewardCard(j,c.StableKey,c.UpgradeLevel)).ToArray())).ToArray();
        Domain();
    }
    private static object? Field(object target,string name)=>target.GetType().GetField(name,BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(target);
    private static bool Valid(GodotObject? value)=>value is not null&&GodotObject.IsInstanceValid(value);
    private static bool Exact<T>(T? value)where T:GodotObject=>Valid(value)&&value!.GetType()==typeof(T);
    private void Require(bool value){if(!value){Binding.Failed=true;throw new InvalidOperationException("Unowned card offer.");}}
    private static bool Same(CardSelectionV1DeckCard a,CardSelectionV1DeckCard b)=>ReferenceEquals(a.ModelIdentity,b.ModelIdentity)&&a.StableKey==b.StableKey&&a.UpgradeLevel==b.UpgradeLevel&&CardSelectionV1Enchantment.Same(a.Enchantment,b.Enchantment);
    private void Domain() {
        Require(!_disposed&&!Binding.Failed&&!Binding.Closed&&GenericEventV7Hooks.Owns(Binding)&&Binding.ContextValid(false));
        if(Bundle)Require(DomainIdentity is IReadOnlyList<IReadOnlyList<CardModel>> list&&list.Count==Count&&_lists.Where((o,i)=>!ReferenceEquals(o,list[i])).Any()==false);
        if(!Bundle)Require(DomainIdentity is IReadOnlyList<CardModel> flat&&flat.Count==Count&&!flat.Where((c,i)=>!ReferenceEquals(c,_models[i][0])).Any());
        for(int i=0;i<Count;i++) {
            Require(_lists[i].Count==_models[i].Length);
            for(int j=0;j<_models[i].Length;j++) {
                var c=_models[i][j];Require(ReferenceEquals(_lists[i][j],c)&&ReferenceEquals(c.Owner,Binding.Player)&&ReferenceEquals(c.RunState,Binding.RunState)&&
                    GenericEventV7ItemState.ValidKey(c.Id.Entry)&&c.CurrentUpgradeLevel>=0&&Same(_cards[i][j],new(c,c.Id.Entry,c.CurrentUpgradeLevel,GenericEventV7Binding.CopyEnchantment(c))));
            }
        }
    }
    internal void EnterScreen(object domain,bool canSkip=false) {Domain();Require(!ScreenEntered&&Screen is null&&ReferenceEquals(domain,DomainIdentity)&&!canSkip);ScreenEntered=true;}
    internal void BindScreen(Control screen) {Domain();Require(ScreenEntered&&Screen is null&&Valid(screen)&&screen.GetType()==(Bundle?typeof(NChooseABundleSelectionScreen):typeof(NChooseACardSelectionScreen)));Screen=screen;}
    private void BindControls() {
        Require(Screen is not null&&Valid(Screen));
        if(Bundle) {
            Require(ReferenceEquals(Field(Screen!,"_bundles"),DomainIdentity));
            _row=Screen!.GetNodeOrNull<Control>("%BundleRow");_preview=Screen.GetNodeOrNull<Control>("%BundlePreviewContainer");
            _previewCards=Screen.GetNodeOrNull<Control>("%Cards");_confirm=Screen.GetNodeOrNull<NConfirmButton>("%Confirm");
            Require(Valid(_row)&&Valid(_preview)&&Valid(_previewCards)&&Exact(_confirm));
            _bundles=_row!.GetChildren().OfType<NCardBundle>().ToArray();Require(_row.GetChildren().Count==Count&&_bundles.Length==Count);
            _nodes=_bundles.Select(b=>b.CardNodes.ToArray()).ToArray();
            Require(Field(Screen,"_completionSource") is TaskCompletionSource<IEnumerable<IReadOnlyList<CardModel>>>);
            _selectorTask=((TaskCompletionSource<IEnumerable<IReadOnlyList<CardModel>>>)Field(Screen,"_completionSource")!).Task;
        }else {
            Require(ReferenceEquals(Field(Screen!,"_cards"),DomainIdentity)&&Field(Screen!,"_canSkip") is false);
            _row=Screen!.GetNodeOrNull<Control>("CardRow");Require(Valid(_row));
            _holders=_row!.GetChildren().OfType<NGridCardHolder>().ToArray();Require(_row.GetChildren().Count==Count&&_holders.Length==Count);
            _nodes=_holders.Select(h=>new[]{h.CardNode!}).ToArray();
            Require(Field(Screen,"_completionSource") is TaskCompletionSource<IEnumerable<CardModel>>);
            _selectorTask=((TaskCompletionSource<IEnumerable<CardModel>>)Field(Screen,"_completionSource")!).Task;
        }
        _hitboxes=Bundle?_bundles!.Select(b=>(GodotObject)b.Hitbox).ToArray():_holders!.Select(h=>(GodotObject)h.Hitbox).ToArray();
        Require(!_selectorTask!.IsCompleted);
    }
    private bool Controls() {
        Require(Screen is not null&&Valid(Screen)&&Screen.IsVisibleInTree());
        if(_selectorTask is null)BindControls();
        Require(Valid(_row)&&ReferenceEquals(Field(Screen!,Bundle?"_bundleRow":"_cardRow"),_row)&&ReferenceEquals(Screen!.GetNodeOrNull<Control>(Bundle?"%BundleRow":"CardRow"),_row));
        if(Bundle)Require(ReferenceEquals(Field(Screen!,"_bundles"),DomainIdentity)&&
            ReferenceEquals(Field(Screen!,"_bundlePreviewContainer"),_preview)&&ReferenceEquals(Field(Screen!,"_bundlePreviewCards"),_previewCards)&&ReferenceEquals(Field(Screen!,"_previewConfirmButton"),_confirm)&&
            Field(Screen!,"_completionSource") is TaskCompletionSource<IEnumerable<IReadOnlyList<CardModel>>> bt&&ReferenceEquals(bt.Task,_selectorTask)&&
            Valid(_preview)&&Valid(_previewCards)&&Exact(_confirm)&&ReferenceEquals(Screen!.GetNodeOrNull<Control>("%BundlePreviewContainer"),_preview)&&
            ReferenceEquals(Screen.GetNodeOrNull<Control>("%Cards"),_previewCards)&&ReferenceEquals(Screen.GetNodeOrNull<NConfirmButton>("%Confirm"),_confirm));
        else Require(ReferenceEquals(Field(Screen!,"_cards"),DomainIdentity)&&Field(Screen!,"_canSkip") is false&&
            Field(Screen!,"_completionSource") is TaskCompletionSource<IEnumerable<CardModel>> ct&&ReferenceEquals(ct.Task,_selectorTask));
        var rows=_row!.GetChildren();Require(rows.Count==Count);
        for(int i=0;i<Count;i++) {
            if(Bundle) {
                var b=_bundles![i];Require(Exact(b)&&ReferenceEquals(rows[i],b)&&ReferenceEquals(b.Bundle,_lists[i])&&_nodes![i].Length==_models[i].Length&&b.CardNodes.Count==_nodes[i].Length&&
                    b.CardNodes.Where((n,j)=>!ReferenceEquals(n,_nodes[i][j])).Any()==false&&Valid(b.Hitbox)&&ReferenceEquals(b.Hitbox,_hitboxes![i]));
                if(_selected is null&&(!b.IsVisibleInTree()||!b.Hitbox.IsVisibleInTree()||!b.Hitbox.IsEnabled))return false;
            }else {
                var h=_holders![i];Require(Exact(h)&&ReferenceEquals(rows[i],h)&&ReferenceEquals(h.CardModel,_models[i][0])&&ReferenceEquals(h.CardNode,_nodes![i][0])&&Valid(h.Hitbox)&&ReferenceEquals(h.Hitbox,_hitboxes![i]));
                if(typeof(NCardHolder).GetField("_isClickable",BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(h) is not true)return false;
                if(!h.IsVisibleInTree()||!h.Hitbox.IsVisibleInTree()||!h.Hitbox.IsEnabled)return false;
            }
            for(int j=0;j<_nodes![i].Length;j++)Require(Exact(_nodes[i][j])&&ReferenceEquals(_nodes[i][j].Model,_models[i][j]));
        }
        if(!Bundle) {Require(Field(Screen!,"_openedTicks") is ulong);ulong opened=(ulong)Field(Screen!,"_openedTicks")!;return Time.GetTicksMsec()>=opened&&Time.GetTicksMsec()-opened>350;}
        return true;
    }
    private bool Deck(bool complete) {
        var current=GenericEventV7Binding.CopyDeck(Binding.Player);var chosen=_selected is {} i?_cards[i]:Array.Empty<CardSelectionV1DeckCard>();
        int added=current.Length-_deck.Length;Require(added>=_added&&added>=0&&added<=chosen.Length&&(_selected is not null&&(!Bundle||_confirmed)||added==0));
        for(int j=0;j<_deck.Length;j++)Require(Same(current[j],_deck[j])&&current[j].ModelIdentity is CardModel model&&ReferenceEquals(model.Owner,Binding.Player)&&ReferenceEquals(model.RunState,Binding.RunState));
        for(int j=0;j<added;j++)Require(Same(current[_deck.Length+j],chosen[j]));_added=added;
        return !complete||added==chosen.Length;
    }
    private bool TaskFailed(Task? task)=>task?.IsFaulted==true||task?.IsCanceled==true;
    public GenericEventV7OfferCapture Capture() {
        try {
            Domain();Require(!TaskFailed(RequestTask)&&!TaskFailed(Binding.ChosenTask)&&!TaskFailed(_selectorTask));
            Deck(false);
            if(Screen is null){Require(RequestTask?.IsCompleted!=true);return new("waiting",Array.Empty<GenericEventV7Offer>());}
            bool submitting=_selected is not null&&(!Bundle||_confirmed);
            if(submitting) {
                Require(Binding.Overlays.ScreenCount==0||Binding.Overlays.ScreenCount==1&&ReferenceEquals(Binding.Overlays.Peek(),Screen));
                if(RequestTask?.IsCompletedSuccessfully!=true||Binding.ChosenTask?.IsCompletedSuccessfully!=true||_selectorTask?.IsCompletedSuccessfully!=true)return new("waiting",Array.Empty<GenericEventV7Offer>());
                var chosen=_models[_selected!.Value];
                if(Bundle) {
                    var result=((Task<IEnumerable<IReadOnlyList<CardModel>>>)_selectorTask).Result.Take(2).ToArray();Require(result.Length==1&&ReferenceEquals(result[0],_lists[_selected.Value]));
                    var request=((Task<IEnumerable<CardModel>>)RequestTask).Result.Take(9).ToArray();Require(request.SequenceEqual(chosen,ReferenceEqualityComparer.Instance));
                }else {
                    var result=((Task<IEnumerable<CardModel>>)_selectorTask).Result.Take(2).ToArray();Require(result.Length==1&&ReferenceEquals(result[0],chosen[0])&&ReferenceEquals(((Task<CardModel>)RequestTask).Result,chosen[0]));
                }
                Require(Binding.Overlays.ScreenCount==0&&Deck(true));return new("complete",Array.Empty<GenericEventV7Offer>());
            }
            Require(Binding.Overlays.ScreenCount==1&&ReferenceEquals(Binding.Overlays.Peek(),Screen)&&RequestTask?.IsCompleted!=true);
            if(!Controls())return new("waiting",Array.Empty<GenericEventV7Offer>());
            Require(_selectorTask?.IsCompleted==false);
            if(Bundle&&_selected is {} index) {
                if(!_preview!.Visible&&Field(Screen!,"_selectedBundle") is null&&_row!.Visible)return new("waiting",Array.Empty<GenericEventV7Offer>());
                Require(ReferenceEquals(Field(Screen,"_selectedBundle"),_bundles![index])&&_preview!.Visible&&!_row!.Visible);
                var nodes=_previewCards!.GetChildren();var holders=nodes.OfType<NPreviewCardHolder>().ToArray();Require(nodes.Count==holders.Length&&holders.Length<=_models[index].Length);
                for(int j=0;j<holders.Length;j++)Require(Exact(holders[j])&&ReferenceEquals(holders[j].CardNode,_nodes![index][j]));
                if(holders.Length<_models[index].Length)return new("waiting",Array.Empty<GenericEventV7Offer>());
                if(_previewHolders is not null)Require(_previewHolders.SequenceEqual(holders,ReferenceEqualityComparer.Instance));_previewHolders=holders;
                Require(ReferenceEquals(Screen!.GetNodeOrNull<NConfirmButton>("%Confirm"),_confirm)&&Exact(_confirm));
                if(!_confirm!.IsVisibleInTree()||!_confirm.IsEnabled)return new("waiting",Array.Empty<GenericEventV7Offer>());
                return new("preview",_public);
            }
            if(Bundle)Require(!_preview!.Visible&&_row!.Visible&&Field(Screen,"_selectedBundle") is null);
            return new("choose",_public);
        }catch{Binding.Failed=true;return new("unsupported",Array.Empty<GenericEventV7Offer>());}
    }
    public void Dispatch(string action) {
        var capture=Capture();
        if(action=="confirm") {Require(Bundle&&capture.Phase=="preview"&&!_confirmed&&_previewHolders is not null);_confirmed=true;_confirm!.ForceClick();return;}
        Require(capture.Phase=="choose"&&_selected is null&&action.Length==8&&action.StartsWith("choose:",StringComparison.Ordinal));
        int index=action[7]-'0';Require(index>=0&&index<Count);_selected=index;
        if(Bundle)Require(_bundles![index].EmitSignal(NCardBundle.SignalName.Clicked,_bundles[index])==Error.Ok);
        else Require(_holders![index].EmitSignal(NCardHolder.SignalName.Pressed,_holders[index])==Error.Ok);
    }
    public void Dispose(){_disposed=true;}
}
