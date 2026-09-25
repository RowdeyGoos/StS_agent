using System;
using System.Collections.Generic;
using System.Collections;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Rooms.Rest;

// One RewardsSet.Offer produced inside the retained Heal invocation. The shared
// reward reader owns collection effects; this owner certifies its native return
// and the separate nonterminal Skip/Proceed control.
internal sealed class RestRewardContinuation : IDisposable
{
    private readonly RewardsSet _set;
    private readonly Player _player;
    private readonly NOverlayStack _overlays;
    private readonly Func<bool> _context;
    private readonly RunManager _manager;
    private readonly object _run, _synchronizer;
    private NRewardsScreen? _screen;
    private Reward[]? _rewards;
    private NProceedButton? _proceed;
    private NCardRewardSelectionScreen? _menu;
    private CardReward? _menuReward;
    private PinnedPublicRewardDecisionReader? _reader;
    private PinnedPublicRewardActionApplier? _applier;
    private Task? _offer;
    private RestNativeState? _beforeDismiss;
    private PinnedPublicItemRewardClaim[] _unclaimed = Array.Empty<PinnedPublicItemRewardClaim>();
    private string? _pending, _settledAction;
    private int _pendingRevision;
    private bool _dismissed, _complete, _disposed, _failed;
    private readonly Func<PinnedPublicRewardParentTarget,NCardRewardSelectionScreen,IPinnedRewardAlternatives>? _alternatives;
    private readonly Func<Player,IPinnedRewardInventory>? _inventory;
    private readonly Func<Reward,IPinnedRelicRewardEffect?>? _relicEffect;
    private readonly bool _disallowSkipping;
    internal PinnedPublicRewardDecisionReader? Reader => _reader;
    internal bool Completed => _complete;
    internal RestRewardContinuation(RewardsSet set, Player player, NOverlayStack overlays, Func<bool> context,
        Func<PinnedPublicRewardParentTarget,NCardRewardSelectionScreen,IPinnedRewardAlternatives>? alternatives=null,
        Func<Player,IPinnedRewardInventory>? inventory=null,
        Func<Reward,IPinnedRelicRewardEffect?>? relicEffect=null)
    {
        _alternatives=alternatives;_inventory=inventory;_relicEffect=relicEffect;_disallowSkipping=set.DisallowSkipping;
        _set = set; _player = player; _overlays = overlays; _context = context;
        _manager = RunManager.Instance ?? throw new InvalidOperationException("rest_reward_manager");
        _run = player.RunState; _synchronizer = _manager.RewardsSetSynchronizer;
        Require(context() && ReferenceEquals(set.Player, player) && (!set.DisallowSkipping || relicEffect is not null) &&
            RewardsSet.testSelector is null && overlays.ScreenCount == 0 && OwnerBound() && Stack().Count == 0);
    }
    internal void Offering(Task task) { Require(_offer is null && task is not null); _offer = task; }
    internal void ScreenEntering(RewardsSet set, bool terminal, object run)
    {
        Require(_context() && OwnerBound() && OwnsStackTop() && _screen is null && _overlays.ScreenCount == 0 && ReferenceEquals(set, _set) &&
            !terminal && ReferenceEquals(run, _player.RunState));
    }
    internal void ScreenEntered(NRewardsScreen screen)
    {
        Require(_screen is null && _context() && Top(screen, 1) && _set.Rewards.Count is >= 1 and <= 8);
        _screen = screen; _rewards = _set.Rewards.ToArray();
        Require(OwnerBound());
        Require(_rewards.Distinct(ReferenceEqualityComparer.Instance).Count() == _rewards.Length &&
            _rewards.All(r => ReferenceEquals(r.Player, _player) && r.ParentRewardSet is null &&
                (r.GetType() == typeof(CardReward) || r.GetType() == typeof(PotionReward) || _relicEffect is not null && (r.GetType()==typeof(GoldReward)||r.GetType()==typeof(RelicReward)||r.GetType()==typeof(SpecialCardReward))) && r.IsPopulated && !r.SuccessfullySelected));
        _reader = new(screen, Scope, Closed, overlayDepth: 1);
        _reader.AlternativesFactory=_alternatives;
        _reader.InventoryFactory=_inventory;
        _reader.RelicEffectFactory=_relicEffect;
        _applier = new(_reader);
    }
    private bool Top(Control screen, int depth) => GodotObject.IsInstanceValid(screen) && _overlays.ScreenCount == depth &&
        ReferenceEquals(_overlays.Peek(), screen) && ReferenceEquals(ActiveScreenContext.Instance.GetCurrentScreen(), screen);
    private bool Closed() => _offer?.IsCompletedSuccessfully == true && _overlays.ScreenCount == 0;
    private static object? Field(object value, string name) => value.GetType().GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)?.GetValue(value);
    private IList Stack()
    {
        var state = _synchronizer.GetType().GetMethod("GetRewardStateForPlayer", BindingFlags.Instance | BindingFlags.NonPublic)!.Invoke(_synchronizer, new object[] { _player })!;
        return (IList)Field(state, "rewardsStack")!;
    }
    private bool OwnsStackTop() { var stack = Stack(); return stack.Count == 1 && ReferenceEquals(Field(stack[0]!, "set"), _set); }
    private bool OwnerBound() => ReferenceEquals(RunManager.Instance, _manager) && ReferenceEquals(_manager.DebugOnlyGetState(), _run) &&
        ReferenceEquals(_player.RunState, _run) && ReferenceEquals(_manager.RewardsSetSynchronizer, _synchronizer) && ReferenceEquals(Field(_set, "_synchronizer"), _synchronizer) &&
        (_screen is null || ReferenceEquals(Field(_screen, "_rewardsSet"), _set) && ReferenceEquals(Field(_screen, "_runState"), _run) && Field(_screen, "_isTerminal") is false);
    private bool Scope() => !_failed && !_disposed && _context() && OwnerBound() && ReferenceEquals(_set.Player, _player) &&
        _set.DisallowSkipping==_disallowSkipping && RewardsSet.testSelector is null && _offer?.IsFaulted != true && _offer?.IsCanceled != true &&
        (_rewards is null || _set.Rewards.SequenceEqual(_rewards)) &&
        (Closed() || _screen is not null && (Top(_screen, 1) || _overlays.Peek() is NCardRewardSelectionScreen menu && MenuScope(menu)));
    private bool MenuScope(NCardRewardSelectionScreen menu)
    {
        if (_reader?.InteractionSession.ActiveCardReward?.Reward is not CardReward reward || !Top(menu, 2) ||
            !ReferenceEquals(Field(reward, "_currentlyShownScreen"), menu) ||
            _menu is not null && (!ReferenceEquals(_menu, menu) || !ReferenceEquals(_menuReward, reward))) return false;
        _menu = menu; _menuReward = reward; return true;
    }
    internal PublicRewardDecisionSnapshot Read()
    {
        Require(!_disposed && !_failed && _context() && OwnerBound() && _offer?.IsFaulted != true && _offer?.IsCanceled != true);
        if (_screen is null)
        {
            if (Closed()) { Require(_set.Rewards.Count == 0); _complete = true; }
            return PublicRewardDecisionSnapshot.Waiting();
        }
        Require(Scope());
        if (_offer?.IsCompletedSuccessfully == true && !Closed()) return PublicRewardDecisionSnapshot.Waiting();
        if (_dismissed)
        {
            Require(_beforeDismiss!.Equals(new RestNativeState(_player)) && _unclaimed.All(p => p.Unclaimed));
            if (Closed()) _complete = true;
            return PublicRewardDecisionSnapshot.Waiting();
        }
        var view = _reader!.Read();
        Require(view.Status != PublicDecisionStatus.Unsupported);
        if (view.Status == PublicDecisionStatus.Complete)
        {
            string? settled=_pending??_settledAction;
            Require(_complete || settled is not null && (settled.StartsWith("choose:", StringComparison.Ordinal) || settled.StartsWith("collect:", StringComparison.Ordinal) || settled.StartsWith("claim:", StringComparison.Ordinal) || settled.StartsWith("take:", StringComparison.Ordinal) || settled=="sacrifice") && Closed() &&
                _rewards!.All(r => r.SuccessfullySelected));
            _pending = null; _complete = true;
        }
        if (view.Status == PublicDecisionStatus.Ready && _pending is not null)
        { Require(view.DecisionRevision > _pendingRevision && _reader.InteractionSession.Pending is null); _settledAction=_pending; _pending = null; }
        if (view.Status == PublicDecisionStatus.Ready && view.ScreenKind == "rewards")
        {
            _menu = null; _menuReward = null;
            var proceed = _screen.GetNodeOrNull<NProceedButton>("ProceedButton");
            Require(proceed is not null && GodotObject.IsInstanceValid(proceed));
            _proceed ??= proceed; Require(ReferenceEquals(_proceed, proceed));
        }
        return view;
    }
    internal bool CanDismiss(PublicRewardDecisionSnapshot view) => !_disallowSkipping && !_dismissed && !_complete &&
        view.Status == PublicDecisionStatus.Ready && view.ScreenKind == "rewards" &&
        _reader!.InteractionSession.Pending is null && OwnsStackTop() && Top(_screen!, 1) &&
        _proceed is not null && GodotObject.IsInstanceValid(_proceed) && _proceed.IsVisibleInTree() && _proceed.IsEnabled;
    internal void Apply(string decision, string action)
    {
        var view = Read();
        Require(view.Status == PublicDecisionStatus.Ready && view.DecisionId == decision && OwnerBound() && OwnsStackTop());
        if (action == "dismiss")
        {
            Require(CanDismiss(view));
            _unclaimed = _rewards!.OfType<PotionReward>().Where(r => !r.SuccessfullySelected).Select(r => new PinnedPublicItemRewardClaim(r)).ToArray();
            Require(_unclaimed.All(p => p.Unclaimed));
            _beforeDismiss = new(_player); _dismissed = true;
            _proceed!.ForceClick();
        }
        else
        {
            Require(view.LegalActions.Contains(action) && PublicRewardActionRequest.TryCreate(decision, action, out _));
            PublicRewardActionRequest.TryCreate(decision, action, out var request);
            Require(_pending is null); _pending = action; _pendingRevision = view.DecisionRevision;
            Require(_applier!.Apply(request).Outcome == PublicRewardActionApplyOutcome.Accepted);
        }
    }
    private void Require(bool condition) { if (!condition) { _failed = true; throw new InvalidOperationException("rest_reward_boundary"); } }
    public void Dispose()
    {
        if (_disposed) { Require(_complete && !_failed); return; }
        try { _reader?.Dispose(); Require(_complete && !_failed); }
        catch { _failed=true; throw; }
        finally { _disposed=true; }
    }
}
