using System;
using Godot;
using Sts2AgentBridge.Successors.GenericEventV3;
using Sts2AgentBridge.Successors.GenericEventV3.Native;

internal sealed class DiagnosticFixture : IDisposable
{
    internal readonly Program.RewardFixture Inner;
    private Vector2 _originalGridSize;
    internal DiagnosticFixture(string nonce, string scenario)
    {
        if(scenario is not ("NORMAL" or "BINDING_WAIT" or "SELECTOR_WAIT" or "UNSUPPORTED" or "CANDIDATE_CARD_TYPE"))
            throw new ArgumentException("Unknown diagnostic fixture.");
        Inner=new Program.RewardFixture("DIAGNOSTIC_REWARD",2,2,8,delayedCreation:scenario=="BINDING_WAIT",nonce:nonce);
        Program.RetireBeforeChosen(Inner.Room.Layout);
        if(scenario=="SELECTOR_WAIT")Inner.BeforeReturn=()=>{_originalGridSize=Inner.Grid.Size;Inner.Grid.Size=new Vector2(1,1);};
        if(scenario=="CANDIDATE_CARD_TYPE")Inner.BeforeReturn=()=>{var holder=Inner.Grid.CurrentlyDisplayedCardHolders[0];holder.CardNode=new HiddenCard { Model=holder.CardNode.Model,CardHighlight=holder.CardNode.CardHighlight,Visible=true };};
        if(scenario=="UNSUPPORTED")Inner.BeforeCreate=()=>Inner.ResultEntries[0].ModifiedCard=Inner.OfferCards[1];
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
