using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.ControllerInput;
using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Native;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

// A precommitted removal owns one wrapper task and the selector created inside
// that invocation. It never adopts an already-open selector or retries input.
internal sealed class PinnedShopRemovalDispatch : IShopV1RemovalDispatch
{
    [ThreadStatic] private static PinnedShopRemovalDispatch? Active;
    private readonly int _owner=System.Environment.CurrentManagedThreadId;
    private readonly MerchantCardRemovalEntry _entry;
    private readonly MerchantInventory _inventory;
    private readonly Player _player;
    private readonly NOverlayStack _overlays;
    private readonly IShopV1NativeDispatch _purchase;
    private readonly Func<bool> _context;
    private readonly Func<int> _counter;
    private CardModel? _target;
    private NDeckCardSelectScreen? _screen;
    private Task<bool>? _wrapper;
    private Task<IEnumerable<CardModel>>? _selection;
    private CardModel[] _domain=Array.Empty<CardModel>();
    private (CardModel Model,string Key,int Level,bool Removable)[] _deck=Array.Empty<(CardModel,string,int,bool)>();
    private (PotionModel? Model,string? Key)[] _potions=Array.Empty<(PotionModel?,string?)>();
    private (RelicModel Model,string Key)[] _relics=Array.Empty<(RelicModel,string)>();
    private NCardGrid? _grid;
    private NGridCardHolder[]? _holders;
    private NCard[]? _cardNodes;
    private GodotObject[]? _hitboxes;
    private Control? _previewContainer,_previewCards;
    private NConfirmButton? _confirm;
    private bool _invoked,_insideWrapper,_wrapperSeen,_screenSeen,_selected,_confirmed,_failed,_disposed;
    private int _gold,_used,_potionCapacity;
    private bool _cleanupFailed;
    private readonly int _price;
    internal PinnedShopRemovalDispatch(MerchantCardRemovalEntry entry,MerchantInventory inventory,Player player,
        NOverlayStack overlays,IShopV1NativeDispatch purchase,Func<bool> context,Func<int> counter)
    { _entry=entry;_inventory=inventory;_player=player;_overlays=overlays;_purchase=purchase;_context=context;_counter=counter;_price=entry.Cost; }
    public void SelectTarget(ShopV1DeckCardBinding card)
    {
        Require(!_invoked&&!_disposed&&_target is null&&card.ModelIdentity is CardModel);
        _target=(CardModel)card.ModelIdentity;
        Require(_target.Id.Entry==card.StableKey&&_target.CurrentUpgradeLevel==card.UpgradeLevel&&card.Removable&&_target.IsRemovable);
    }
    public void Invoke()
    {
        Require(!_invoked&&!_disposed&&Active is null&&_target is not null&&Context()&&_overlays.ScreenCount==0&&_entry.IsStocked&&!_entry.Used&&_entry.Cost==_price&&_player.Gold>=_price);
        _invoked=true;_potionCapacity=_player.MaxPotionCount;_gold=_player.Gold;_used=_counter();Require(_used>=0&&_used<int.MaxValue);
        _deck=_player.Deck.Cards.Select(c=>(c,c.Id.Entry,c.CurrentUpgradeLevel,c.IsRemovable)).ToArray();
        _potions=_player.PotionSlots.Select(p=>(p,p?.Id.Entry)).ToArray();
        _relics=_player.Relics.Select(r=>(r,r.Id.Entry)).ToArray();
        _domain=_deck.Where(c=>c.Removable).Select(c=>c.Model).ToArray();
        Require(_domain.Length is >=1 and <=64&&_domain.Count(c=>ReferenceEquals(c,_target))==1&&BeforeEffect());
        var wrapper=typeof(MerchantCardRemovalEntry).GetMethod("OnTryPurchaseWrapper",new[]{typeof(MerchantInventory),typeof(bool),typeof(bool)})!;
        var create=typeof(NDeckCardSelectScreen).GetMethod("Create",new[]{typeof(IReadOnlyList<CardModel>),typeof(CardSelectorPrefs)})!;
        var harmony=new Harmony("sts.bridge.shop.removal."+Guid.NewGuid().ToString("N"));
        try {
            harmony.Patch(wrapper,prefix:new HarmonyMethod(typeof(PinnedShopRemovalDispatch),nameof(WrapperPrefix)),postfix:new HarmonyMethod(typeof(PinnedShopRemovalDispatch),nameof(WrapperPostfix)));
            harmony.Patch(create,prefix:new HarmonyMethod(typeof(PinnedShopRemovalDispatch),nameof(ScreenPrefix)),postfix:new HarmonyMethod(typeof(PinnedShopRemovalDispatch),nameof(ScreenPostfix)));
            Active=this;_purchase.Invoke();
        }
        finally {
            Active=null;harmony.UnpatchAll(harmony.Id);
            Require(Harmony.GetPatchInfo(wrapper)?.Owners.Contains(harmony.Id)!=true&&Harmony.GetPatchInfo(create)?.Owners.Contains(harmony.Id)!=true);
        }
        Require(!_failed&&_wrapperSeen&&_screenSeen&&_wrapper is not null&&Valid(_screen)&&_overlays.ScreenCount==1&&ReferenceEquals(_overlays.Peek(),_screen));
        _selection=_screen!.CardsSelected();Require(_selection is not null&&!_selection.IsCompleted);
    }
    private static void WrapperPrefix(MerchantCardRemovalEntry __instance,MerchantInventory __0,bool __1,bool __2,out PinnedShopRemovalDispatch? __state)
    {
        __state=Active;if(__state is not {} s)return;
        try {s.Require(!s._wrapperSeen&&!s._insideWrapper&&ReferenceEquals(__instance,s._entry)&&ReferenceEquals(__0,s._inventory)&&!__1&&__2&&s.BeforeEffect());s._wrapperSeen=true;s._insideWrapper=true;}
        catch{s._failed=true;throw;}
    }
    private static void WrapperPostfix(Task<bool> __result,PinnedShopRemovalDispatch? __state)
    {if(__state is {} s){s._insideWrapper=false;s._wrapper=__result;}}
    private static void ScreenPrefix(IReadOnlyList<CardModel> __0,CardSelectorPrefs __1,out PinnedShopRemovalDispatch? __state)
    {
        __state=Active;if(__state is not {} s)return;
        s.Require(s._insideWrapper&&!s._screenSeen&&__1.MinSelect==1&&__1.MaxSelect==1&&__1.Cancelable&&__1.RequireManualConfirmation&&s.BeforeEffect());
        s.Require(__0.Count==s._domain.Length&&__0.Distinct(ReferenceEqualityComparer.Instance).Count()==__0.Count&&
            __0.All(c=>s._domain.Any(d=>ReferenceEquals(d,c))&&c.IsRemovable&&ReferenceEquals(c.Owner,s._player)&&ReferenceEquals(c.RunState,s._player.RunState)));
        s._screenSeen=true;
    }
    private static void ScreenPostfix(NDeckCardSelectScreen __result,PinnedShopRemovalDispatch? __state)
    {if(__state is {} s){s.Require(s._screenSeen&&s._screen is null&&__result?.GetType()==typeof(NDeckCardSelectScreen));s._screen=__result;}}
    internal bool OwnsForeground => _invoked&&!_failed&&Valid(_screen)&&_overlays.ScreenCount==1&&ReferenceEquals(_overlays.Peek(),_screen);
    internal void Advance()
    {
        Require(_invoked&&!_disposed&&!_failed&&Context()&&_wrapper is not null&&_selection is not null);
        Require(!_wrapper!.IsFaulted&&!_wrapper.IsCanceled&&(!_wrapper.IsCompleted||_wrapper.Result));
        Require(!_selection!.IsFaulted&&!_selection.IsCanceled);
        if(_confirmed) {
            // CardsSelected creates a separate async waiter for each caller.
            // Native effects and the purchase wrapper may finish before ours.
            // After confirmation only observe; never re-enter selector input.
            if(_selection.IsCompleted)Require(SelectedExactly());
            Require(_overlays.ScreenCount==0||OwnsForeground);return;
        }
        Require(!_selection.IsCompleted&&!_wrapper.IsCompleted&&OwnsForeground&&BeforeEffect());
        if(!_screen!.IsVisibleInTree())return;
        var grid=_screen.GetNodeOrNull<NCardGrid>("%CardGrid");Require(Valid(grid));
        if(grid!.IsAnimatingOut)return;
        var holders=grid.CurrentlyDisplayedCardHolders.ToArray();
        if(_holders is null) {
            if(holders.Length!=_domain.Length)return; // Native grid allocation may still be settling.
            Require(holders.Distinct(ReferenceEqualityComparer.Instance).Count()==holders.Length&&holders.All(h=>Valid(h)&&h.CardModel is {} c&&_domain.Any(d=>ReferenceEquals(d,c))));
            Require(holders.Select(h=>h.CardModel).Distinct(ReferenceEqualityComparer.Instance).Count()==_domain.Length);
            _grid=grid;_holders=holders;
            Require(holders.All(h=>Valid(h.CardNode)&&Valid(h.Hitbox)));
            _cardNodes=holders.Select(h=>h.CardNode!).ToArray();_hitboxes=holders.Select(h=>(GodotObject)h.Hitbox!).ToArray();
            _previewContainer=_screen.GetNodeOrNull<Control>("%PreviewContainer");Require(Valid(_previewContainer));
            _previewCards=_previewContainer!.GetNodeOrNull<Control>("%Cards");_confirm=_previewContainer!.GetNodeOrNull<NConfirmButton>("%PreviewConfirm");Require(Valid(_previewCards)&&Valid(_confirm));
        }
        Require(ReferenceEquals(grid,_grid)&&holders.Length==_holders!.Length&&holders.Where((h,i)=>!ReferenceEquals(h,_holders[i])).Any()==false&&
            ReferenceEquals(_screen.GetNodeOrNull<Control>("%PreviewContainer"),_previewContainer)&&ReferenceEquals(_previewContainer!.GetNodeOrNull<Control>("%Cards"),_previewCards)&&
            ReferenceEquals(_previewContainer!.GetNodeOrNull<NConfirmButton>("%PreviewConfirm"),_confirm));
        for(int i=0;i<holders.Length;i++){var h=holders[i];Require(Valid(h)&&Valid(h.CardNode)&&Valid(h.Hitbox)&&ReferenceEquals(h.CardNode,_cardNodes![i])&&ReferenceEquals(h.Hitbox,_hitboxes![i])&&ReferenceEquals(h.CardNode!.Model,h.CardModel)&&_domain.Any(c=>ReferenceEquals(c,h.CardModel)));}
        if(!_selected) {
            Require(!_previewContainer!.Visible);
            foreach(var h in holders) {
                Require(h.CardNode!.CardHighlight?.Material is ShaderMaterial);
                var endpoint=CardSelectionV1NativeRules.ClassifyHighlight(((ShaderMaterial)h.CardNode!.CardHighlight.Material).GetShaderParameter("width").AsSingle());
                if(endpoint==CardSelectionV1HighlightEndpoint.Transient)return;
                Require(endpoint==CardSelectionV1HighlightEndpoint.Unselected);
            }
            var holder=holders.Single(h=>ReferenceEquals(h.CardModel,_target));
            Require(Valid(holder.Hitbox)&&holder.IsVisibleInTree()&&holder.CardNode!.IsVisibleInTree()&&holder.Hitbox.IsVisibleInTree()&&holder.Hitbox.IsEnabled&&
                typeof(NCardHolder).GetField("_isClickable",BindingFlags.Instance|BindingFlags.NonPublic|BindingFlags.DeclaredOnly)?.GetValue(holder) is true&&_target!.IsRemovable);
            _selected=true;using var input=new InputEventAction {Action=MegaInput.select,Pressed=true};holder._GuiInput(input);Require(Context());return;
        }
        if(!_previewContainer!.Visible||!_previewContainer!.IsVisibleInTree())return;
        var preview=_previewCards!.GetChildren().ToArray();
        Require(preview.Length==1&&preview[0] is NPreviewCardHolder);
        var selected=(NPreviewCardHolder)preview[0];Require(Valid(selected)&&Valid(selected.CardNode)&&ReferenceEquals(selected.CardModel,_target)&&ReferenceEquals(selected.CardNode!.Model,_target)&&selected.IsVisibleInTree()&&selected.CardNode!.IsVisibleInTree());
        if(!_confirm!.IsVisibleInTree()||!_confirm.IsEnabled)return;
        Require(BeforeEffect()&&_target!.IsRemovable);_confirmed=true;_confirm.ForceClick();Require(Context());
    }
    public ShopV1Completion Completion => _disposed?ShopV1Completion.Invalid:ReadCompletion();
    private ShopV1Completion ReadCompletion()
    {
            if(_failed)return ShopV1Completion.Invalid;
            if(_wrapper?.IsCanceled==true||_wrapper?.IsFaulted==true||_wrapper?.IsCompletedSuccessfully==true&&!_wrapper.Result)return ShopV1Completion.Invalid;
            if(_selection?.IsCanceled==true||_selection?.IsFaulted==true||_selection?.IsCompletedSuccessfully==true&&(!_confirmed||!SelectedExactly()))return ShopV1Completion.Invalid;
            if(_purchase.Completion is ShopV1Completion.Invalid or ShopV1Completion.Failed)return ShopV1Completion.Invalid;
            if(_purchase.Completion!=ShopV1Completion.Succeeded)return ShopV1Completion.Pending;
            if(!Context()||!_confirmed||_entry.IsStocked||!_entry.Used||_counter()!=_used+1)return ShopV1Completion.Invalid;
            if(_selection?.IsCompletedSuccessfully!=true||_wrapper?.IsCompletedSuccessfully!=true||!_wrapper.Result||_overlays.ScreenCount!=0)return ShopV1Completion.Pending;
            return ShopV1Completion.Succeeded;
    }
    private bool SelectedExactly()
    {
        if(_selection?.IsCompletedSuccessfully!=true)return false;
        var selected=_selection.Result?.Take(2).ToArray();
        return selected?.Length==1&&ReferenceEquals(selected[0],_target);
    }
    public void Dispose()
    {
        if(_disposed){if(_cleanupFailed)throw new InvalidOperationException("Removal cleanup remains uncertain.");return;}
        _disposed=true;_cleanupFailed=_invoked;
        try{if(_invoked)_cleanupFailed=ReadCompletion()!=ShopV1Completion.Succeeded;}catch{_cleanupFailed=true;}
        try{_purchase.Dispose();}catch{_cleanupFailed=true;throw;}
        if(_cleanupFailed)throw new InvalidOperationException("Native removal has not completed; cleanup is uncertain.");
    }
    private static bool ForegroundClear()
    {
        var modal=NModalContainer.Instance;
        var capstone=MegaCrit.Sts2.Core.Nodes.Screens.Capstones.NCapstoneContainer.Instance;
        return (modal is null || Valid(modal)&&modal.OpenModal is null) &&
            (capstone is null || Valid(capstone)&&!capstone.InUse&&capstone.CurrentCapstoneScreen is null);
    }
    private bool Context()=>System.Environment.CurrentManagedThreadId==_owner&&ForegroundClear()&&CardSelectCmd.Selector is null&&_context()&&ReferenceEquals(_inventory.Player,_player)&&ShopPotionOwnership.LocalEntry(_entry,_player);
    private bool BeforeEffect()=>Context()&&_player.MaxPotionCount==_potionCapacity&&_player.Gold==_gold&&_counter()==_used&&_entry.Cost==_price&&_entry.IsStocked&&!_entry.Used&&
        _player.Deck.Cards.Count==_deck.Length&&_deck.Where((c,i)=>!ReferenceEquals(c.Model,_player.Deck.Cards[i])||c.Model.Id.Entry!=c.Key||c.Model.CurrentUpgradeLevel!=c.Level||c.Model.IsRemovable!=c.Removable||!ReferenceEquals(c.Model.Owner,_player)).Any()==false&&
        _player.PotionSlots.Count==_potions.Length&&_potions.Where((p,i)=>!ReferenceEquals(p.Model,_player.PotionSlots[i])||p.Model?.Id.Entry!=p.Key||p.Model is not null&&!ReferenceEquals(p.Model.Owner,_player)).Any()==false&&
        _player.Relics.Count==_relics.Length&&_relics.Where((r,i)=>!ReferenceEquals(r.Model,_player.Relics[i])||r.Model.Id.Entry!=r.Key||!ReferenceEquals(r.Model.Owner,_player)).Any()==false;
    private static bool Valid([System.Diagnostics.CodeAnalysis.NotNullWhen(true)] GodotObject? value)=>value is not null&&GodotObject.IsInstanceValid(value);
    private void Require([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool value){if(!value){_failed=true;throw new InvalidOperationException("Owned shop removal changed or failed.");}}
}
