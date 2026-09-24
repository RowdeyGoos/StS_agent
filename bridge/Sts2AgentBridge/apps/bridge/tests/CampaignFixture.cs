using System;
using System.Text.Json;
using Sts2AgentBridge.Unified;
internal sealed class CampaignFixture : ICampaignNavigation
{
    public bool Active {get;private set;}
    private int _phase;
    public ModuleReply Handle(BridgeRequest request) {
        if(request.IsPost) {
            if(_phase>=2||request.Action!=(_phase==0?"open_chest":"skip_relic")||request.Decision!=new string(_phase==0?'a':'b',64))throw new InvalidOperationException();
            _phase++;
            Active=true;
            return new(JsonSerializer.SerializeToUtf8Bytes(new{schema_version=1,protocol="campaign_v2",status="accepted",decision_id=request.Decision,action_id=request.Action}));
        }
        if(_phase==2)Active=false;
        return new(JsonSerializer.SerializeToUtf8Bytes(new{schema_version=1,protocol="campaign_v2",status=_phase==2?"complete":"ready",decision_id=_phase==2?null:new string(_phase==0?'a':'b',64),legal_actions=_phase==2?Array.Empty<string>():new[]{_phase==0?"open_chest":"skip_relic"}}));
    }
    public void Dispose(){if(Active)throw new InvalidOperationException();}
}
