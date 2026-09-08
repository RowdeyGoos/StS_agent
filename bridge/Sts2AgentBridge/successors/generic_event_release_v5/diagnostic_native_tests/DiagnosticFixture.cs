using System;
using System.Linq;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using Godot;
using Sts2AgentBridge.Successors.GenericEventV3;
using Sts2AgentBridge.Successors.GenericEventV3.Native;

internal sealed class DiagnosticFixture : IDisposable
{
    internal readonly Program.RewardFixture Inner;
    private Vector2 _originalGridSize;
    private NClickableControl[]? _derivedHitboxes;
    internal DiagnosticFixture(string nonce, string scenario)
    {
        if(scenario is not ("NORMAL" or "BINDING_WAIT" or "SELECTOR_WAIT" or "UNSUPPORTED" or "CANDIDATE_CARD_TYPE" or "DERIVED_HITBOX"))
            throw new ArgumentException("Unknown diagnostic fixture.");
        Inner=new Program.RewardFixture("DIAGNOSTIC_REWARD",2,2,8,delayedCreation:scenario=="BINDING_WAIT",nonce:nonce);
        Program.RetireBeforeChosen(Inner.Room.Layout);
        if(scenario=="SELECTOR_WAIT")Inner.BeforeReturn=()=>{_originalGridSize=Inner.Grid.Size;Inner.Grid.Size=new Vector2(1,1);};
        if(scenario=="CANDIDATE_CARD_TYPE")Inner.BeforeReturn=()=>{var holder=Inner.Grid.CurrentlyDisplayedCardHolders[0];holder.CardNode=new HiddenCard { Model=holder.CardNode.Model,CardHighlight=holder.CardNode.CardHighlight,Visible=true };};
        if(scenario=="DERIVED_HITBOX")Inner.BeforeReturn=()=>{_derivedHitboxes=Inner.Grid.CurrentlyDisplayedCardHolders.Select(holder=>{var hitbox=new HiddenHitbox();holder.Hitbox=hitbox;return (NClickableControl)hitbox;}).ToArray();};
        if(scenario=="UNSUPPORTED")Inner.BeforeCreate=()=>Inner.ResultEntries[0].ModifiedCard=Inner.OfferCards[1];
    }
    private sealed class HiddenHitbox : NClickableControl { }
    internal bool DerivedHitboxCompletionValid
    {
        get
        {
            if(_derivedHitboxes is null || _derivedHitboxes.Length!=8 || Inner.Grid.CurrentlyDisplayedCardHolders.Count!=8 ||
                Inner.Selected.Count!=2 || ReferenceEquals(Inner.Selected[0],Inner.Selected[1]) ||
                !Inner.Selected.All(c=>Inner.OfferCards.Any(offer=>ReferenceEquals(offer,c))) ||
                Inner.Player.Deck.Cards.Count!=5 || !Inner.Map.IsOpen || !Inner.Map.IsTravelEnabled) return false;
            for(int i=0;i<8;i++)
                if(!ReferenceEquals(Inner.Grid.CurrentlyDisplayedCardHolders[i].Hitbox,_derivedHitboxes[i]) ||
                    _derivedHitboxes[i].GetType()!=typeof(HiddenHitbox) || !GodotObject.IsInstanceValid(_derivedHitboxes[i])) return false;
            for(int i=0;i<3;i++)
                if(!ReferenceEquals(Inner.Player.Deck.Cards[i],Inner.BaselineCards[i]) ||
                    Inner.BaselineCards[i].Id.Entry!="Baseline_"+i || Inner.BaselineCards[i].CurrentUpgradeLevel!=0) return false;
            for(int i=0;i<2;i++)
                if(!ReferenceEquals(Inner.Player.Deck.Cards[i+3],Inner.Selected[i]) || Inner.Selected[i].CurrentUpgradeLevel!=0) return false;
            return true;
        }
    }
    private sealed class HiddenCard : MegaCrit.Sts2.Core.Nodes.Cards.NCard { }
    internal PinnedGenericEventV3NativeAdapter Adapter=>Inner.Adapter;
    internal GenericEventV3Session Session=>Inner.Session;
    internal int OptionCalls=>Inner.OptionCalls;
    internal int SelectCalls=>Inner.SelectCalls;
    internal int ConfirmCalls=>Inner.ConfirmCalls;
    internal void ReleaseCreation()=>Inner.CreationGate.TrySetResult();
    internal void RestoreGeometry()=>Inner.Grid.Size=_originalGridSize;
    internal void Advance() { }
    public void Dispose()=>Inner.Dispose();
}
