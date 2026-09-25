using ResumeDiagnostic = Sts2AgentBridge.Successors.GenericEventV7.GenericEventV7ResumeDiagnostic;
using System;
using System.Text;
using System.Text.Json;
using Sts2AgentBridge.Core.Public;
using Sts2AgentBridge.Core.Protocol;
using Sts2AgentBridge.Core.Identity;
using Sts2AgentBridge.Cards.Combat;

namespace Sts2AgentBridge.Unified;

// Original public services retain their native identity, legality and action budgets.
// The host adds cross-capability fencing around an accepted asynchronous action.
internal sealed class CoreBridgeModule : IDisposable
{
    private readonly string _correlation;
    private readonly IPublicScreenService _screen;
    private string? _pendingPath, _pendingDecision;
    internal const string EventCombatRoute="/probe/event-combat-v2/public/decision";
    internal const string ResumeItemRead="/probe/event-combat-v2/public/item-decision", ResumeItemAction="/probe/event-combat-v2/public/item-action";
    internal static bool IsResumeItem(BridgeRequest request)=>request.Path is ResumeItemRead or ResumeItemAction;
    internal bool CanServiceResumeItem()=>_combatResume is not null&&_potions?.Active!=true&&!_choice.IsActive&&_combatResume()=="item";
    private Func<bool>? _combatScope;
    private Func<string>? _combatResume;
    private Func<ResumeDiagnostic>? _resumeDiagnostic;
    private string? _eventNonce;
    private readonly Action? _beginCombat, _cleanupRewards;
    private AgentSession? _agent;
    private ICampaignNavigation? _campaign;
    private ICombatPotions? _potions;
    internal void BindPotions(ICombatPotions potions) => _potions = potions;
    private IPublicRewardActionService? _campaignRewardApply;
    private Action<bool>? _rewardMode;
    internal void BindCampaign(ICampaignNavigation navigation, IPublicRewardActionService rewards, Action<bool>? rewardMode=null) {_campaign=navigation;_campaignRewardApply=rewards;_rewardMode=rewardMode;}
    public object? ObservationSource => _campaign;
    internal bool HasPendingAction => _potions?.Active == true || _pendingPath is not null || _choice.IsActive || _combatScope is not null || _agent?.Active == true || _campaign?.Active == true;
    internal void BindAgent(IAgentPublicReader reader) => _agent = new(reader, HandleLegacy, _correlation);
    internal void BindCombatScope(Func<bool> scope,Func<string>? resume=null,string? eventNonce=null,Func<ResumeDiagnostic>? resumeDiagnostic=null) {
        if(HasPendingAction||!scope()||resume is not null&&(eventNonce is not {Length:32}||!System.Linq.Enumerable.All(eventNonce,c=>c is >= '0' and <= '9' or >= 'a' and <= 'f')))
            throw new InvalidOperationException("Invalid combat transfer.");
        _beginCombat?.Invoke();_combatScope=scope;_combatResume=resume;_eventNonce=eventNonce;_resumeDiagnostic=resumeDiagnostic;
    }
    internal void ReleaseEventCombat() {
        if(_combatResume is null||_choice.IsActive||_potions?.Active==true)throw new InvalidOperationException("Unresolved event combat chooser.");
        _pendingPath=_pendingDecision=null;_combatScope=null;_combatResume=null;_eventNonce=null;_resumeDiagnostic=null;
    }
    private ModuleReply ResumeRead(string status) => new(JsonSerializer.SerializeToUtf8Bytes(new {
        schema_version=1,protocol="event_combat_v2",session_nonce=_eventNonce,status
    }), EventResumed:status=="resumed");
    private readonly CombatCardChoiceService _choice;
    private readonly IPublicCombatDecisionService _combatRead;
    private readonly IPublicCombatActionService _combatApply;
    private readonly IPublicRewardDecisionService _rewardRead;
    private readonly IPublicRewardActionService _rewardApply;
    private readonly IPublicMapDecisionService _mapRead;
    private readonly IPublicMapActionService _mapApply;
    private readonly IPublicRoomDecisionService _roomRead;
    private readonly IPublicRoomActionService _roomApply;
    internal CoreBridgeModule(string correlation, IPublicScreenService screen,
        IPublicCombatDecisionService combatRead, IPublicCombatActionService combatApply,
        IPublicRewardDecisionService rewardRead, IPublicRewardActionService rewardApply,
        IPublicMapDecisionService mapRead, IPublicMapActionService mapApply,
        IPublicRoomDecisionService roomRead, IPublicRoomActionService roomApply,
        CombatCardChoiceService? choice = null, Action? beginCombat = null, Action? cleanupRewards = null)
    {
        _correlation = correlation; _screen = screen; _beginCombat=beginCombat; _cleanupRewards=cleanupRewards;
        _combatRead = combatRead; _combatApply = combatApply;
        _rewardRead = rewardRead; _rewardApply = rewardApply;
        _mapRead = mapRead; _mapApply = mapApply;
        _roomRead = roomRead; _roomApply = roomApply;
        _choice = choice ?? new CombatCardChoiceService(() => null, correlation);
    }
    internal static bool IsValidAction(BridgeRequest r) => r.Path switch
    {
        CombatPotionRoutes.Action => CombatPotionRoutes.IsAction(r.Decision, r.Action),
        CombatPotionRoutes.FullAction => CombatPotionRoutes.IsFullAction(r.Decision, r.Action),
        "/probe/v0/public/combat-action" => PublicCombatActionRequest.TryCreate(r.Decision!, r.Action!, out _),
        "/probe/v0/public/reward-action" or CampaignRoutes.RewardAction or CampaignRoutes.FullRewardAction => PublicRewardActionRequest.TryCreate(r.Decision!, r.Action!, out _),
        CampaignRoutes.FullAction => Sts2AgentBridge.Successors.ItemV1.ItemV1CanonicalEncoder.IsCanonicalDecisionId(r.Decision)&&r.Action is "proceed" or "open_chest" or "skip_relic" or "claim_relic",
        CampaignRoutes.Action => Sts2AgentBridge.Successors.ItemV1.ItemV1CanonicalEncoder.IsCanonicalDecisionId(r.Decision)&&r.Action is "proceed" or "open_chest" or "skip_relic",
        "/probe/v0/public/map-action" => PublicMapActionRequest.TryCreate(r.Decision!, r.Action!, out _),
        "/probe/v0/public/room-action" => PublicRoomActionRequest.TryCreate(r.Decision!, r.Action!, out _),
        ResumeItemAction => Sts2AgentBridge.Successors.ItemV1.ItemV1CanonicalEncoder.IsCanonicalDecisionId(r.Decision)&&
            (Sts2AgentBridge.Successors.ItemWireV1.ItemWireV1Protocol.IsCanonicalActionId(r.Action,out _)||r.Action=="skip_remaining"||r.Action is {Length:9}&&r.Action.StartsWith("discard:",StringComparison.Ordinal)&&r.Action[8] is >= '0' and <= '7'),
        CombatCardChoiceService.ActionRoute or CombatCardChoiceService.ActionRouteV2 or CombatCardChoiceService.ActionRouteV3 or CombatCardChoiceService.ActionRouteV4 => CombatCardChoiceService.IsAction(r.Decision, r.Action),
        AgentSession.ActionRoute => AgentSession.IsAction(r.Decision, r.Action),
        _ => false,
    };
    internal ModuleReply Handle(BridgeRequest r)
    {
        if(r.Path is CampaignRoutes.Decision or CampaignRoutes.Action or CampaignRoutes.FullDecision or CampaignRoutes.FullAction) {
            if(_potions?.Active==true||_campaign is null||_pendingPath is not null||_choice.IsActive||_combatScope is not null||_agent?.Active==true)return Busy();
            return _campaign.Handle(r);
        }
        if(_campaign?.Active==true&&!r.IsMetadata)return Busy();
        if (r.Path is AgentSession.DecisionRoute or AgentSession.ActionRoute)
        {
            if (_agent is null || _combatScope is not null || _potions?.Active==true) return Busy();
            if (!_agent.Active && (_pendingPath is not null || _choice.IsActive)) return Busy();
            return _agent.Handle(r);
        }
        if (!r.IsMetadata && _agent?.Active == true) return Busy();
        return HandleLegacy(r);
    }
    private ModuleReply HandleLegacy(BridgeRequest r)
    {
        if (r.Path == "/probe/v0/health") return new(CanonicalProbeEncoder.EncodeHealthBody(_correlation));
        if (r.Path == "/probe/v0/manifest")
        {
            byte[] old = CanonicalProbeEncoder.EncodeManifestBody(ProbeMode.Compatible);
            try { return new(Encoding.ASCII.GetBytes(Encoding.ASCII.GetString(old)
                .Replace("\"bridge_version\":\"0.8.0\"", "\"bridge_version\":\"1.0.0\"")
                .Replace("\"harmony_patches\":false", "\"harmony_patches\":true"))); }
            finally { Array.Clear(old); }
        }
        // An event fight may end inside a potion effect. Reconcile that exact
        // action before consulting or releasing its outer event continuation.
        if (_potions?.Active == true) {
            if (r.Path is CombatPotionRoutes.Decision or CombatPotionRoutes.FullDecision) {
                if (_choice.IsActive) return Busy();
                return Potion(r);
            }
            if (_potions is IFullPotions && r.Path is CombatCardChoiceService.DecisionRouteV4 or CombatCardChoiceService.ActionRouteV4) {
                if (_potions is not IFullPotions { ChoiceOwnerAlive: true }) return Fault();
                if (!_choice.IsActive && _potions is not IFullPotions { AllowsChoices: true })
                    return r.IsPost ? Busy() : new(JsonSerializer.SerializeToUtf8Bytes(new { status = "waiting" }));
                var choice = r.IsPost ? _choice.Apply(r.Decision!, r.Action!, 4) : _choice.Read(4);
                return new(choice.Body, Terminal: choice.Terminal);
            }
            if (r.Path == EventCombatRoute && _combatResume is not null) return ResumeRead("waiting");
            return Busy();
        }
        if(r.Path==EventCombatRoute) {
            if(_combatResume is null||r.IsPost)return Fault();
            string resumed=_combatResume();
            if(resumed is not ("combat" or "waiting" or "item" or "resumed")||(resumed is "resumed" or "item")&&_choice.IsActive)return ResumeFault();
            return ResumeRead(resumed);
        }
        if(_combatScope is not null) {
            if(_combatResume is not null) {
                string resumed=_combatResume();
                if(resumed is not ("combat" or "waiting" or "item" or "resumed"))return ResumeFault();
                if(resumed!="combat") {
                    if(r.Path=="/probe/v0/public/combat-decision")return new(CanonicalProbeEncoder.EncodePublicCombatDecisionBody(PublicCombatDecisionSnapshot.Waiting()));
                    if(r.Path is CombatCardChoiceService.DecisionRoute or CombatCardChoiceService.DecisionRouteV2 or CombatCardChoiceService.DecisionRouteV3 or CombatCardChoiceService.DecisionRouteV4) {var choice=_choice.Read(CombatCardChoiceService.Version(r.Path));return new(choice.Body,Terminal:choice.Terminal);}
                    // A combat-to-event switch can occur between a ready read and POST.
                    // This reply proves no command was queued; the host may observe resume.
                    if(r.IsPost&&r.Path=="/probe/v0/public/combat-action")return new(JsonSerializer.SerializeToUtf8Bytes(new {
                        schema_version=1,status="rejected",mutation_state="none",decision_id=r.Decision,action_id=r.Action,reason="stale_decision"
                    }),StaleWithoutMutation:true);
                    return Busy();
                }
            }
            if(!_combatScope())return Fault();
            if(r.Path is not (CombatPotionRoutes.Decision or CombatPotionRoutes.Action or CombatPotionRoutes.FullDecision or CombatPotionRoutes.FullAction or "/probe/v0/public/combat-decision" or "/probe/v0/public/combat-action" or CombatCardChoiceService.DecisionRoute or CombatCardChoiceService.ActionRoute or CombatCardChoiceService.DecisionRouteV2 or CombatCardChoiceService.DecisionRouteV3 or CombatCardChoiceService.DecisionRouteV4 or CombatCardChoiceService.ActionRouteV2 or CombatCardChoiceService.ActionRouteV3 or CombatCardChoiceService.ActionRouteV4))return Busy();
        }
        if (r.Path is CombatCardChoiceService.DecisionRoute or CombatCardChoiceService.ActionRoute or CombatCardChoiceService.DecisionRouteV2 or CombatCardChoiceService.DecisionRouteV3 or CombatCardChoiceService.DecisionRouteV4 or CombatCardChoiceService.ActionRouteV2 or CombatCardChoiceService.ActionRouteV3 or CombatCardChoiceService.ActionRouteV4)
        {
            if (_pendingPath is not null && _pendingPath != "/probe/v0/public/combat-decision")
                return Busy();
            int version = CombatCardChoiceService.Version(r.Path);
            var choice = r.IsPost ? _choice.Apply(r.Decision!, r.Action!, version) : _choice.Read(version);
            return new(choice.Body, Terminal: choice.Terminal);
        }
        if (_choice.IsActive || _pendingPath is not null && (r.IsPost || r.Path != _pendingPath))
            return Busy();
        if (r.Path is CombatPotionRoutes.Decision or CombatPotionRoutes.Action or CombatPotionRoutes.FullDecision or CombatPotionRoutes.FullAction) return Potion(r);
        byte[] body;
        switch (r.Path)
        {
            case "/probe/v0/public/screen":
                var screen = _screen.Read();
                if (!screen.IsSuccess) return Fault();
                body = CanonicalProbeEncoder.EncodePublicScreenBody(screen.Snapshot); break;
            case "/probe/v0/public/combat-decision":
                var combat = _combatRead.Read();
                if (!combat.IsSuccess) return Fault();
                body = CanonicalProbeEncoder.EncodePublicCombatDecisionBody(combat.Snapshot); break;
            case "/probe/v0/public/combat-action":
                if (!PublicCombatActionRequest.TryCreate(r.Decision!, r.Action!, out var combatAction)) return Fault();
                var combatResult = _combatApply.Apply(combatAction);
                if (combatResult.IsBackendFault) return Fault();
                body = CanonicalProbeEncoder.EncodePublicCombatActionBody(combatResult); break;
            case "/probe/v0/public/reward-decision":
            case CampaignRoutes.RewardDecision:
            case CampaignRoutes.FullRewardDecision:
                _rewardMode?.Invoke(r.Path==CampaignRoutes.FullRewardDecision);
                var reward = _rewardRead.Read();
                if (!reward.IsSuccess) return Fault();
                body = CanonicalProbeEncoder.EncodePublicRewardDecisionBody(reward.Snapshot,r.Path is CampaignRoutes.RewardDecision or CampaignRoutes.FullRewardDecision); break;
            case "/probe/v0/public/reward-action":
            case CampaignRoutes.RewardAction:
            case CampaignRoutes.FullRewardAction:
                _rewardMode?.Invoke(r.Path==CampaignRoutes.FullRewardAction);
                if (!PublicRewardActionRequest.TryCreate(r.Decision!, r.Action!, out var rewardAction)) return Fault();
                var service=r.Path is CampaignRoutes.RewardAction or CampaignRoutes.FullRewardAction?_campaignRewardApply:_rewardApply;
                if(service is null)return Fault();
                var rewardResult = service.Apply(rewardAction);
                if (rewardResult.IsBackendFault) return Fault();
                body = CanonicalProbeEncoder.EncodePublicRewardActionBody(rewardResult); break;
            case "/probe/v0/public/map-decision":
                var map = _mapRead.Read();
                if (!map.IsSuccess) return Fault();
                body = CanonicalProbeEncoder.EncodePublicMapDecisionBody(map.Snapshot); break;
            case "/probe/v0/public/map-action":
                if (!PublicMapActionRequest.TryCreate(r.Decision!, r.Action!, out var mapAction)) return Fault();
                var mapResult = _mapApply.Apply(mapAction);
                if (mapResult.IsBackendFault) return Fault();
                body = CanonicalProbeEncoder.EncodePublicMapActionBody(mapResult); break;
            case "/probe/v0/public/room-decision":
                var room = _roomRead.Read();
                if (!room.IsSuccess) return Fault();
                body = CanonicalProbeEncoder.EncodePublicRoomDecisionBody(room.Snapshot); break;
            case "/probe/v0/public/room-action":
                if (!PublicRoomActionRequest.TryCreate(r.Decision!, r.Action!, out var roomAction)) return Fault();
                var roomResult = _roomApply.Apply(roomAction);
                if (roomResult.IsBackendFault) return Fault();
                body = CanonicalProbeEncoder.EncodePublicRoomActionBody(roomResult); break;
            default: return Fault();
        }
        try
        {
            using var json = JsonDocument.Parse(body);
            var root = json.RootElement;
            if(!r.IsPost && r.Path=="/probe/v0/public/combat-decision" && root.GetProperty("status").GetString()=="complete"&&_combatResume is null)_combatScope=null;
            if (r.IsPost)
            {
                if (root.GetProperty("status").GetString() != "accepted")
                {
                    // Native adapters reject a stale observation before dispatch.
                    // Let the controller obtain a fresh decision. Only delivery
                    // of this known no-mutation receipt can release its reservation.
                    bool stale = root.GetProperty("status").GetString() == "rejected" &&
                        root.GetProperty("mutation_state").GetString() == "none" &&
                        root.GetProperty("reason").GetString() == "stale_decision";
                    return new(body, Terminal: !stale, StaleWithoutMutation: stale);
                }
                _pendingPath = r.Path==CampaignRoutes.FullRewardAction?CampaignRoutes.FullRewardDecision:r.Path==CampaignRoutes.RewardAction?CampaignRoutes.RewardDecision:r.Path.Replace("-action", "-decision");
                _pendingDecision = r.Decision;
            }
            else if (_pendingPath == r.Path)
            {
                string? status = root.GetProperty("status").GetString();
                if (status == "complete" || status == "ready" && root.GetProperty("decision_id").GetString() != _pendingDecision)
                    _pendingPath = _pendingDecision = null;
                else if (status != "ready" && status != "waiting") return new(body, Terminal: true);
            }
            return new(body);
        }
        catch { Array.Clear(body); throw; }
    }
    private ModuleReply Potion(BridgeRequest r) {
        if (_potions is null) return Fault();
        bool full = r.Path is CombatPotionRoutes.FullDecision or CombatPotionRoutes.FullAction;
        if (full && _potions is not IFullPotions) return Fault();
        var reply = full ? (r.IsPost ? ((IFullPotions)_potions).ApplyFull(r.Decision!, r.Action!) : ((IFullPotions)_potions).ReadFull())
            : r.IsPost ? _potions.Apply(r.Decision!, r.Action!) : _potions.Read();
        return new(reply.Body, Terminal: reply.Terminal, StaleWithoutMutation: reply.StaleWithoutMutation);
    }
    private ModuleReply ResumeFault() {
        ResumeDiagnostic diagnostic;
        try{diagnostic=_resumeDiagnostic?.Invoke()??ResumeDiagnostic.diagnostic_unavailable;}
        catch{diagnostic=ResumeDiagnostic.diagnostic_unavailable;}
        string code=Enum.IsDefined(typeof(ResumeDiagnostic),diagnostic)?diagnostic.ToString():"diagnostic_unavailable";
        return new(JsonSerializer.SerializeToUtf8Bytes(new {
            schema_version=1,code="backend_fault",retryable=false,mutation_state="none",
            correlation_id=_correlation,resume_diagnostic=code
        }),Terminal:true);
    }
    private ModuleReply Fault() => new(CanonicalProbeEncoder.EncodeErrorBody(ProbeErrorKind.BackendFault, _correlation), Terminal: true);
    private static ModuleReply Busy() => new("{\"schema_version\":1,\"kind\":\"error\",\"code\":\"capability_busy\"}"u8.ToArray());
    public void Dispose() { try { try { _potions?.Dispose(); } finally { _cleanupRewards?.Invoke(); } } finally { try { _choice.Dispose(); } finally { try{_agent?.Dispose();}finally{_campaign?.Dispose();} } } }
}
