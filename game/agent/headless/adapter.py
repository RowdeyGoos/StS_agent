"""Synchronous owner of a RunEngine's public decision/command boundary."""
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json

from game.agent import contracts as c
from game.headless.run.state import RunPhase
from .errors import AdapterFault
from .identity import Identities
from .projection import Projection
from .combat_summary import summarize, with_enemy_health


@dataclass(frozen=True, slots=True)
class DecisionFrame:
    """The policy receives decision only; binding stays with the caller.

    Binding is an opaque in-process capability, deliberately unserializable by
    the public codec. It is not a hash, observation feature or replay identity.
    """
    decision: c.PublicDecision
    binding: object
    prepared: object = field(default=None, repr=False, compare=False)


class HeadlessAdapter:
    """Attach with partial history; reset explicitly starts a new attachment.

    Own the engine exclusively until reset. No adapter checkpoint API is exposed
    in this milestone: restoring an engine requires a fresh attachment, without
    claiming that engine snapshots preserve public history or identities.
    """

    def __init__(self, engine, *, decision_profile='combat_reward_map_v1'):
        if decision_profile not in ('combat_reward_map_v1', 'full_run_v2'):
            raise ValueError('Unknown public decision profile')
        self.decision_profile = decision_profile
        self.reset(engine)

    def reset(self, engine):
        self._engine = engine
        self._ids = Identities()
        self._history = []
        self._power_cards = {}
        self._epoch = 0
        self._opened = False
        self._abandoned = False
        self._surfaces = []
        self._surface_epoch = 0
        self._frame = None
        self._commands = {}
        self._stamp = None
        self._faulted = False
        self._roots = self._owned_roots()
        self._combat_summary = (summarize(engine.combat, self._epoch)
                                if engine.combat and self.decision_profile == 'full_run_v2' else None)
        self._combat_health_summary = with_enemy_health(self._combat_summary, engine.combat)
        self._combat_completion = None

    @property
    def combat_summary(self):
        """Public facts from attachment or the latest reconciled v2 transition.

        Completed facts survive disposal of the combat owner. Rejected actions
        do not refresh them. No snapshot, private identity or resolution details
        are exposed. This controller API does not change either wire schema.
        """
        if self.decision_profile != 'full_run_v2':
            raise ValueError('Combat summaries require full_run_v2')
        if self._faulted:
            raise AdapterFault('Adapter stopped after an execution failure.')
        return self._combat_summary

    @property
    def combat_health_summary(self):
        """Optional enemy HP facts from the same reconciled combat boundary."""
        self.combat_summary  # Apply the same profile and fault checks.
        return self._combat_health_summary

    @property
    def combat_completion(self):
        """Latest settled public inventory/HUD, frozen at verified cleanup."""
        self.combat_summary  # Apply the same profile and stopped-owner checks.
        return self._combat_completion

    def _project_completion(self, summary):
        from game.agent.contracts.planning import CombatEnd, validate_end
        from .full_projection import FullProjection
        owner = FullProjection(self._engine, self._ids, self._history, self._power_cards,
                               'attachment', self._epoch, False)
        return validate_end(CombatEnd(summary.outcome, owner.run()))

    @property
    def run_outcome(self):
        """Actual run endpoint, independent of any consumer's task boundary."""
        if self._faulted:
            raise AdapterFault('Adapter stopped after an execution failure.')
        return self._outcome()

    def _owned_roots(self):
        combat = self._engine.combat
        # An identical engine restore still replaces owned roots. A hash alone
        # would wrongly keep its old dispatch capability alive.
        return (self._engine.state, combat, combat.player if combat else None)

    def _same_roots(self):
        # Retain references as well as testing identity, so repeated external
        # restores cannot recycle an old root's Python id into a valid binding.
        return all(current is saved for current, saved in zip(self._owned_roots(), self._roots))

    def prepared_for(self, decision):
        """Reuse public conversion only for this attachment's current frame.

        This grants no dispatch authority; step() still checks the private
        state guard. Consuming/resetting the frame also releases this owner.
        """
        if self._frame is not None and self._frame.decision is decision:
            return self._frame.prepared
        return None

    def _guard(self):
        # Private control guard ONLY. Projection reads explicit owned fields; it
        # neither subtracts fields from this snapshot nor exposes this digest.
        data = json.dumps(self._engine.snapshot(), sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(data.encode()).digest()

    def _outcome(self):
        phase = self._engine.state.phase
        if phase in (RunPhase.VICTORY, RunPhase.DEFEAT):
            return c.RunOutcome('sts_run_outcome_v1', 'abandoned' if self._abandoned else phase.value, 'none')
        if phase is RunPhase.SLICE_COMPLETE:
            return c.RunOutcome('sts_run_outcome_v1', 'truncated', 'slice_complete')
        if phase is RunPhase.ACT_COMPLETE and not self._engine.legal_actions():
            return c.RunOutcome('sts_run_outcome_v1', 'truncated', 'act_complete')
        return None

    def observe(self):
        """Return a ready DecisionFrame or a genuine terminal RunOutcome.

        UnsupportedProfile is an explicit capability gap, not an empty legal
        set or game loss. Observation never advances engine state or RNG.
        """
        if self._faulted:
            raise AdapterFault('Adapter stopped after an execution failure; explicitly reset to attach again.')
        if not self._same_roots():
            self.reset(self._engine)
        outcome = self._outcome()
        if outcome is not None:
            self._frame = None
            self._commands = {}
            return outcome
        stamp = self._guard()
        if self._frame is not None and stamp == self._stamp:
            return self._frame
        self._frame = None
        self._commands = {}
        # An unsupported projection must not consume identity allocation or
        # partially replace a valid decision's metadata.
        identities = deepcopy(self._ids)
        projector = Projection
        if self.decision_profile == 'full_run_v2':
            from .full_projection import FullProjection
            projector = FullProjection
        owner = None
        generation = self._surface_epoch
        new_surface = False
        kwargs = {}
        if self.decision_profile == 'full_run_v2':
            state = self._engine.state
            if state.relic_work:
                owner = state.relic_work[0]
            elif self._engine.combat is not None:
                owner = self._engine.combat
            elif state.pending:
                data = state.pending.get('data', {})
                if state.pending.get('kind') == 'scripted_event':
                    # Event transactions copy their active dictionaries even
                    # for a toggle/pick within the same visible child. Private
                    # cursor values identify ownership only; their numbers are
                    # never projected or used as public reference ordinals.
                    owner = ('event', state.pending['event_instance_id'],
                             state.pending['stage'], data.get('cursor'),
                             len(data.get('pages', ())))
                else:
                    owner = state.pending
            # A pickup child suspends its parent; returning must recover that
            # parent's public identities and reroll ownership. Retained owners
            # also prevent private object-address reuse after disposal.
            for previous, previous_generation in self._surfaces:
                same = owner == previous if isinstance(owner, tuple) and isinstance(previous, tuple) else owner is previous
                if same:
                    generation = previous_generation
                    break
            else:
                generation, new_surface = self._surface_epoch + 1, True
            kwargs['generation'] = generation
        projection = projector(self._engine, identities, self._history, self._power_cards,
                               'attachment', self._epoch, self._opened, **kwargs)
        decision = projection.decision()
        if new_surface:
            self._surfaces.append((owner, generation))
            self._surface_epoch = generation
        self._ids = identities
        self._commands = projection.commands
        self._stamp = stamp
        self._frame = DecisionFrame(decision, object(), getattr(projection, 'prepared', None))
        return self._frame

    def step(self, binding, candidate_ref):
        """Dispatch exactly one advertised candidate against its original state."""
        def rejected(reason):
            return c.ExecutionReport('sts_execution_report_v1', 'rejected', 'none', reason)
        if self._faulted:
            raise AdapterFault('Adapter stopped after an execution failure.')
        if (self._frame is None or binding is not self._frame.binding or
                not self._same_roots() or self._guard() != self._stamp):
            return rejected('stale_decision')
        if not isinstance(candidate_ref, str) or candidate_ref not in self._commands:
            return rejected('invalid_action')
        action = next(a for a in self._frame.decision.candidates if a.ref == candidate_ref)
        command = self._commands[candidate_ref]
        if self.decision_profile == 'full_run_v2':
            return self._step_full(action, command)
        combat_before = self._engine.combat
        context = self._frame.decision.context
        played_card = (next(card for pile in context.piles if pile.kind == 'hand' for card in pile.cards.value
                            if card.ref == action.subject) if action.kind == 'play_card' else None)
        skipped = (tuple(r.ref for r in context.entries if not r.resolved)
                   if action.kind == 'leave_rewards' else ())
        acquired_ref, acquired_kind = action.target, 'card'
        if action.kind == 'claim_reward':
            reward = next(r for r in self._frame.decision.context.entries if r.ref == action.subject)
            acquired_kind = reward.kind
            if acquired_kind in ('potion', 'relic'):
                acquired_ref = getattr(reward, acquired_kind).value.ref
        # Consume the capability before execution, including a presentation-only
        # open. Exceptions may follow mutation; no automatic retry is permitted.
        self._frame = None
        self._commands = {}
        try:
            if action.kind == 'open_card_reward':
                self._opened = True
            else:
                result = self._engine.apply(command)
                if (played_card is not None and self._engine.combat is combat_before and
                        any(card.instance_id == command.instance_id for card in combat_before.player.deck.powers)):
                    self._power_cards[self._epoch, command.instance_id] = played_card
                if action.kind in ('choose_reward_card', 'claim_reward') and acquired_ref is not None and result is not None:
                    key = ('deck' if acquired_kind == 'card' else 'owned', result.instance_id)
                    self._ids.refs[acquired_kind, key] = acquired_ref
                if action.kind in ('choose_reward_card', 'skip_reward', 'leave_rewards'):
                    self._opened = False
        except Exception as error:
            self._faulted = True
            raise AdapterFault('Headless command failed; mutation is uncertain and the adapter is stopped.') from error
        event = {'play_card': 'card_played', 'end_turn': 'end_turn', 'select_card': 'card_selected',
                 'deselect_card': 'card_selected', 'confirm_selection': 'selection_confirmed',
                 'open_card_reward': 'reward_opened', 'claim_reward': 'reward_claimed',
                 'choose_reward_card': 'reward_claimed', 'skip_reward': 'reward_skipped',
                 'leave_rewards': 'reward_skipped', 'choose_map_node': 'map_selected'}[action.kind]
        values = (c.Counter('selected', int(action.kind == 'select_card')),) if action.kind in ('select_card', 'deselect_card') else ()
        if action.kind == 'leave_rewards':
            self._history.extend(c.HistoryEvent('reward_skipped', c.known(ref), c.not_applicable(), ()) for ref in skipped)
        else:
            self._history.append(c.HistoryEvent(event, c.known(action.subject) if action.subject else c.not_applicable(),
                                                c.known(action.target) if action.target else c.not_applicable(), values))
        if combat_before is not None and self._engine.combat is None:
            self._history.append(c.HistoryEvent('combat_ended', c.not_applicable(), c.not_applicable(), ()))
        if self._engine.combat is not combat_before:
            if self._engine.combat is not None:
                self._epoch += 1
            self._ids.draw_groups = ()
            self._power_cards = {}
        self._roots = self._owned_roots()
        return c.ExecutionReport('sts_execution_report_v1', 'reconciled', 'applied', 'none')

    def _step_full(self, action, command):
        from game.agent.contracts.full import walk
        from game.headless.core.combat import CombatEngine
        combat_before = self._engine.combat
        combat_epoch = self._epoch
        entities = {n.ref: n for root in (self._frame.decision.run, self._frame.decision.context)
                    for n in walk(root) if n.ref is not None}
        played = entities.get(action.subject) if action.kind == 'play_card' else None
        def inventory():
            state = self._engine.state
            return {'card': state.deck, 'relic': state.relics,
                    'potion': [p for p in state.potions if p is not None]}
        before_ids = {kind: {item.instance_id for item in items} for kind, items in inventory().items()}
        # One command, one consumed capability. Interrupts also latch the host:
        # a caller cannot retry after an uncertain native/rules interruption.
        self._frame, self._commands = None, {}
        try:
            if action.kind in ('open_reward', 'close_reward'):
                self._opened = action.subject if action.kind == 'open_reward' else False
                result = None
            else:
                result = self._engine.apply(command)
                if action.kind != 'reroll_card_reward':
                    self._opened = False
            # apply() has completed all synchronous cleanup/hooks. Retain the
            # old owner to read its authoritative result, but take final HUD
            # values from the run (e.g. Burning Blood heals after disposal).
            completed = (summarize(combat_before, combat_epoch, completed_state=self._engine.state)
                         if combat_before is not None and self._engine.combat is not combat_before
                         else None)
            # Room/event entry may create and dispose a fight synchronously.
            # Both entry paths return that owner; its post-hook public result
            # must survive even though no ongoing fight was ever projected.
            instant = (combat_before is None and self._engine.combat is None and
                       isinstance(result, CombatEngine) and result.done)
            if instant:
                self._epoch += 1
                completed = summarize(result, self._epoch, completed_state=self._engine.state)
            if (played is not None and self._engine.combat is combat_before and
                    any(card.instance_id == command.instance_id for card in combat_before.player.deck.powers)):
                self._power_cards[self._epoch, command.instance_id] = played
            # Some engine commands return no item (event picks), or a compound
            # result (bundles). Preserve only the correspondence established by
            # this chosen visible offer and the newly acquired public inventory.
            acquires = action.kind in ('choose_reward_card', 'choose_extra_reward', 'claim_potion',
                                       'claim_relic', 'claim_treasure_relic', 'choose_ancient_relic',
                                       'choose_relic_reward', 'buy_shop_item', 'choose_event_option')
            offered = entities.get(action.target or action.subject) if acquires else None
            desired = [n for n in walk(offered) if n.kind in before_ids and n.ref] if offered else []
            for kind, items in inventory().items():
                fresh = [item for item in items if item.instance_id not in before_ids[kind]]
                for definition in dict.fromkeys(n.definition_id for n in desired if n.kind == kind):
                    views = [n for n in desired if n.kind == kind and n.definition_id == definition]
                    matches = [item for item in fresh if (item.definition.definition_id if kind == 'card' else item.definition_id) == definition]
                    if len(matches) == len(views):
                        for view, item in zip(views, matches):
                            key = ('deck' if kind == 'card' else 'owned', item.instance_id)
                            self._ids.refs[kind, key] = view.ref
            self._abandoned = action.kind == 'abandon_run'
            self._history.append(action)
            if self._engine.combat is not combat_before:
                if self._engine.combat is not None:
                    self._epoch += 1
                self._ids.draw_groups = ()
                self._power_cards = {}
            self._roots = self._owned_roots()
            self._combat_summary = completed or (
                summarize(self._engine.combat, self._epoch) if self._engine.combat else None)
            health_owner = (result if instant else combat_before) if completed else self._engine.combat
            self._combat_health_summary = with_enemy_health(self._combat_summary, health_owner)
            if completed:
                self._combat_completion = self._project_completion(completed)
            elif self._engine.combat is not combat_before:
                self._combat_completion = None
        except BaseException as error:
            self._faulted = True
            if not isinstance(error, Exception):
                raise
            raise AdapterFault('Headless command failed; mutation is uncertain and the adapter is stopped.') from error
        return c.ExecutionReport('sts_execution_report_v1', 'reconciled', 'applied', 'none')
