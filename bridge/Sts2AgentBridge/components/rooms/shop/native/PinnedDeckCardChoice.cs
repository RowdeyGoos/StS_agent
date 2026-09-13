using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.ControllerInput;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using Sts2AgentBridge.Successors.CardSelectionV1.Native;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

// Exact original models, allocated controls and native preview confirmation.
// This helper supplies input; its caller retains task and effect authority.
internal sealed class PinnedDeckCardChoice {
    private readonly Control _screen;
    private readonly NOverlayStack _overlays;
    private readonly CardModel[] _domain,_targets;
    private readonly Func<bool> _context;
    private readonly EnchantmentModel? _enchantment;
    private readonly int _amount,_maximum;
    private readonly Task<IEnumerable<CardModel>> _selection;
    private NCardGrid? _grid;
    private NGridCardHolder[]? _holders;
    private NCard[]? _cardNodes;
    private GodotObject[]? _hitboxes;
    private Control? _container,_preview;
    private NConfirmButton? _confirm,_openPreview;
    private bool _previewRequested;
    private object[]? _previewBindings;
    private int _selected;
    private bool _confirmed,_failed;
    internal bool Completed=>!_failed&&_confirmed&&SelectedExactly();
    internal bool OwnsForeground=>!_failed&&Valid(_screen)&&_overlays.ScreenCount==1&&ReferenceEquals(_overlays.Peek(),_screen);
    internal PinnedDeckCardChoice(Control screen,NOverlayStack overlays,IReadOnlyList<CardModel> domain,CardModel[] targets,Func<bool> context,EnchantmentModel? enchantment,int amount,int maximum) {
        _screen=screen;_overlays=overlays;_domain=domain.ToArray();_targets=targets.ToArray();_context=context;_enchantment=enchantment;_amount=amount;_maximum=maximum;
        Require(screen.GetType()==(enchantment is null?typeof(NDeckCardSelectScreen):typeof(NDeckEnchantSelectScreen)));
        _selection=(Task<IEnumerable<CardModel>>)screen.GetType().GetMethod("CardsSelected",Type.EmptyTypes)!.Invoke(screen,null)!;
        Require(!_selection.IsCompleted&&_domain.Length is >=1 and <=64&&_domain.Distinct(ReferenceEqualityComparer.Instance).Count()==_domain.Length&&_targets.All(t=>_domain.Contains(t)));
    }
    private string Container=>_enchantment is null?"%PreviewContainer":_maximum==1?"%EnchantSinglePreviewContainer":"%EnchantMultiPreviewContainer";
    private string Preview=>_enchantment is not null&&_maximum==1?"EnchantPreview":_enchantment is null?"%Cards":"Cards";
    private string Confirm=>_enchantment is null?"%PreviewConfirm":"Confirm";
    internal void Advance() {
        Require(!_failed&&!_selection.IsFaulted&&!_selection.IsCanceled);
        if(_selection.IsCompleted){Require(Completed);return;}
        Require(OwnsForeground&&_context());
        if(!_screen.IsVisibleInTree())return;
        var grid=_screen.GetNodeOrNull<NCardGrid>("%CardGrid");Require(Valid(grid));
        if(grid!.IsAnimatingOut)return;
        var holders=grid.CurrentlyDisplayedCardHolders.ToArray();
        if(_holders is null) {
            if(holders.Length!=_domain.Length)return;
            Require(holders.Distinct(ReferenceEqualityComparer.Instance).Count()==holders.Length&&holders.All(h=>Valid(h)&&h.CardModel is {} c&&_domain.Contains(c))&&holders.Select(h=>h.CardModel).Distinct(ReferenceEqualityComparer.Instance).Count()==_domain.Length);
            _grid=grid;_holders=holders;Require(holders.All(h=>Valid(h.CardNode)&&Valid(h.Hitbox)));
            _cardNodes=holders.Select(h=>h.CardNode!).ToArray();_hitboxes=holders.Select(h=>(GodotObject)h.Hitbox!).ToArray();
            _container=_screen.GetNodeOrNull<Control>(Container);Require(Valid(_container));
            _preview=_container!.GetNodeOrNull<Control>(Preview);_confirm=_container.GetNodeOrNull<NConfirmButton>(Confirm);Require(Valid(_preview)&&Valid(_confirm));
            Require(!_container.Visible);
            if(_enchantment is not null&&_maximum>1){_openPreview=_screen.GetNodeOrNull<NConfirmButton>("%Confirm");Require(Valid(_openPreview));}
        }
        Require(ReferenceEquals(grid,_grid)&&holders.Length==_holders!.Length&&holders.Select((h,i)=>ReferenceEquals(h,_holders[i])).All(x=>x)&&
            ReferenceEquals(_screen.GetNodeOrNull<Control>(Container),_container)&&ReferenceEquals(_container!.GetNodeOrNull<Control>(Preview),_preview)&&ReferenceEquals(_container.GetNodeOrNull<NConfirmButton>(Confirm),_confirm));
        for(int i=0;i<holders.Length;i++){var h=holders[i];Require(Valid(h)&&Valid(h.CardNode)&&Valid(h.Hitbox)&&ReferenceEquals(h.CardNode,_cardNodes![i])&&ReferenceEquals(h.Hitbox,_hitboxes![i])&&ReferenceEquals(h.CardNode!.Model,h.CardModel)&&_domain.Contains(h.CardModel!));}
        if(_selected<_targets.Length) {
            foreach(var h in holders) {
                Require(h.CardNode!.CardHighlight?.Material is ShaderMaterial);
                var endpoint=CardSelectionV1NativeRules.ClassifyHighlight(((ShaderMaterial)h.CardNode!.CardHighlight.Material).GetShaderParameter("width").AsSingle());
                if(endpoint==CardSelectionV1HighlightEndpoint.Transient)return;
                bool selected=_targets.Take(_selected).Contains(h.CardModel!);
                Require(endpoint==(selected?CardSelectionV1HighlightEndpoint.Selected:CardSelectionV1HighlightEndpoint.Unselected));
            }
            var holder=holders.Single(h=>ReferenceEquals(h.CardModel,_targets[_selected]));
            Require(holder.IsVisibleInTree()&&holder.CardNode!.IsVisibleInTree()&&holder.Hitbox.IsVisibleInTree()&&holder.Hitbox.IsEnabled&&
                typeof(NCardHolder).GetField("_isClickable",BindingFlags.Instance|BindingFlags.NonPublic|BindingFlags.DeclaredOnly)?.GetValue(holder) is true&&_context());
            _selected++;using var input=new InputEventAction{Action=MegaInput.select,Pressed=true};holder._GuiInput(input);Require(_context());return;
        }
        if(_confirmed)return;
        if(!_container!.Visible||!_container.IsVisibleInTree()) {
            if(_openPreview is not null&&_targets.Length<_maximum&&!_previewRequested) {
                Require(ReferenceEquals(_screen.GetNodeOrNull<NConfirmButton>("%Confirm"),_openPreview)&&Valid(_openPreview)&&_context());
                foreach(var holder in holders) {
                    Require(holder.CardNode!.CardHighlight?.Material is ShaderMaterial);
                    var endpoint=CardSelectionV1NativeRules.ClassifyHighlight(((ShaderMaterial)holder.CardNode.CardHighlight.Material).GetShaderParameter("width").AsSingle());
                    if(endpoint==CardSelectionV1HighlightEndpoint.Transient)return;
                    Require(endpoint==(_targets.Contains(holder.CardModel!)?CardSelectionV1HighlightEndpoint.Selected:CardSelectionV1HighlightEndpoint.Unselected));
                }
                if(!_openPreview.IsVisibleInTree()||!_openPreview.IsEnabled)return;
                _previewRequested=true;_openPreview.ForceClick();Require(_context());
            }
            return;
        }
        var bindings=new List<object>();
        if(_enchantment is not null&&_maximum==1) {
            var before=Field(_preview!,"_before") as Control;var after=Field(_preview!,"_after") as Control;Require(Valid(before)&&Valid(after));
            var originals=before!.GetChildren().ToArray();var previews=after!.GetChildren().ToArray();Require(originals.Length==1&&previews.Length==1);
            var original=CheckHolder(originals[0],bindings);var clone=CheckHolder(previews[0],bindings);
            Require(ReferenceEquals(original,_targets.Single())&&!ReferenceEquals(clone,original)&&clone.IsEnchantmentPreview&&
                ReferenceEquals(clone.Owner,original.Owner)&&ReferenceEquals(clone.RunState,original.RunState)&&clone.Id.Entry==original.Id.Entry&&clone.CurrentUpgradeLevel==original.CurrentUpgradeLevel&&
                clone.Enchantment is {} e&&ReferenceEquals(e.Card,clone)&&e.Id.Entry==_enchantment.Id.Entry&&e.Amount==_amount);
            bindings.Add(before);bindings.Add(after);bindings.Add(clone.Enchantment!);
        } else {
            var nodes=_preview!.GetChildren().ToArray();Require(nodes.Length==_targets.Length);
            var originals=nodes.Select(n=>CheckHolder(n,bindings)).ToArray();Require(originals.Distinct(ReferenceEqualityComparer.Instance).Count()==originals.Length&&originals.All(c=>_targets.Contains(c)));
        }
        _previewBindings??=bindings.ToArray();Require(bindings.Count==_previewBindings.Length&&bindings.Select((b,i)=>ReferenceEquals(b,_previewBindings[i])).All(x=>x));
        if(!_confirm!.IsVisibleInTree()||!_confirm.IsEnabled)return;
        Require(_context());_confirmed=true;_confirm.ForceClick();Require(_context());
    }
    private CardModel CheckHolder(Node node,List<object> bindings) {
        Require(node is NPreviewCardHolder);var holder=(NPreviewCardHolder)node;
        Require(Valid(holder)&&Valid(holder.CardNode)&&holder.CardModel is not null&&ReferenceEquals(holder.CardNode!.Model,holder.CardModel)&&holder.IsVisibleInTree()&&holder.CardNode.IsVisibleInTree());
        bindings.Add(holder);bindings.Add(holder.CardNode!);bindings.Add(holder.CardModel!);return holder.CardModel!;
    }
    private bool SelectedExactly(){if(!_selection.IsCompletedSuccessfully)return false;var result=_selection.Result.Take(4).ToArray();return result.Length==_targets.Length&&result.Distinct(ReferenceEqualityComparer.Instance).Count()==result.Length&&result.All(c=>_targets.Contains(c));}
    private static object? Field(object value,string name)=>value.GetType().GetField(name,BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(value);
    private static bool Valid([System.Diagnostics.CodeAnalysis.NotNullWhen(true)] GodotObject? value)=>value is not null&&GodotObject.IsInstanceValid(value);
    private void Require([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool ok,[System.Runtime.CompilerServices.CallerLineNumber] int boundary=0){if(!ok){_failed=true;throw new InvalidOperationException("Owned pickup selection changed at boundary "+boundary+".");}}
}
