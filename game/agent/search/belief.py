"""Public-prefix particle filtering and bounded replay through the real rules.

Parents are sampled by posterior weight; normal-engine proposals are accepted
only on a complete public match. Accepted particles therefore have equal weights
(no second likelihood factor). Replay from the declared anchor recovers latent
orders absent from an empirical population. It never rewrites a draw pile to fit
an observation. Guided importance proposals are a later optimization.
"""
from dataclasses import dataclass
import math
from random import Random
import time

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.contracts.planning import CombatEnd, validate_start, validate_end
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.run.construction import declared_combat, declared_combat_region
from game.headless.planning import UnsupportedSearch
from .public_keys import action_key, public_key, end_key
from .world import SimulationWorld

MODEL = 'public_belief_v1'


@dataclass(frozen=True, slots=True)
class BeliefBudget:
    particles: int = 4
    max_proposals: int = 1024
    seconds: float = 5.
    replay_proposals: int = 2048
    replay_steps: int = 16384
    history_limit: int = 512

    def __post_init__(self):
        if (type(self.particles) is not int or not 1 <= self.particles <= 256 or
                type(self.max_proposals) is not int or not self.particles <= self.max_proposals <= 65536 or
                type(self.seconds) not in (int, float) or not math.isfinite(self.seconds) or self.seconds <= 0 or
                type(self.replay_proposals) is not int or not 0 <= self.replay_proposals <= 65536 or
                type(self.replay_steps) is not int or not 0 <= self.replay_steps <= 1048576 or
                type(self.history_limit) is not int or not 1 <= self.history_limit <= 512):
            raise ValueError('Invalid belief budget')


@dataclass(frozen=True, slots=True)
class BeliefUpdate:
    proposals: int
    survivors: int
    elapsed: float
    reason: str | None
    replay_proposals: int = 0
    replay_steps: int = 0
    recovered: bool = False


def _boundary(decision):
    if not isinstance(decision, f.PublicDecision) or decision.context.kind != 'combat':
        raise UnsupportedSearch('belief_boundary_unsupported')
    f.require_ready(decision)
    keys = [action_key(decision, a) for a in decision.candidates]
    if len(set(keys)) != len(keys):
        raise UnsupportedSearch('belief_ambiguous_actions')


def _key(value):
    return end_key(value) if isinstance(value, CombatEnd) else public_key(value)


class _Work:
    def __init__(self, seconds):
        self.started = time.perf_counter()
        self.deadline = self.started + seconds
        self.proposals = self.replays = self.steps = 0

    def available(self):
        return time.perf_counter() < self.deadline


class CombatBelief:
    """One declared fight, a bounded public journal and hypothetical worlds.

    ``belief_budget`` is recoverable: verified public progress keeps being
    recorded, and recovery replays the entire prefix. Invalid receipts, missing
    progress or unsupported boundaries invalidate coverage until a new anchor.
    No actual engine, private snapshot or gameplay seed is accepted.
    """

    def __init__(self, setup, opening, *, seed=0, budget=BeliefBudget(), cards=DEFAULT_CARDS,
                 initialize=True):
        self.setup = validate_start(setup)
        _boundary(opening)
        opening = f.from_dict(f.to_dict(opening))
        try:
            declared_combat_region(self.setup.encounter_id)
        except ValueError as error:
            raise UnsupportedSearch('belief_encounter_unsupported') from error
        if (opening.context.get('round') != 1 or
                any(n.children for n in opening.run.children if n.kind == 'history')):
            raise UnsupportedSearch('belief_start_unsupported')
        if self.setup.card_catalog != cards.snapshot_fingerprint():
            raise UnsupportedSearch('belief_catalog_mismatch')
        if type(seed) is not int or type(budget) is not BeliefBudget:
            raise ValueError('A planner seed and belief budget are required')
        self.budget, self._rng, self._cards = budget, Random(seed), cards
        self.opening = self.current = opening
        self.transitions, self._constraints = [], []
        self._opening_key = self._key(opening)
        self._worlds, self.weights = [], ()
        self.reason = 'belief_budget'
        self.last_update = BeliefUpdate(0, 0, 0., self.reason)
        self.updates = []
        if initialize:
            work = _Work(budget.seconds)
            self._condition(self._fresh, budget.max_proposals, work)
            self._finish(work)
            if self.reason:
                raise UnsupportedSearch(self.reason)

    def _seed(self):
        return self._rng.getrandbits(63)

    def _key(self, value):
        return _key(value)

    def _fresh(self):
        setup = self.setup
        try:
            run = declared_combat(deck=[(v.definition_id, v.upgrade_level) for v in setup.deck],
                                  relics=[(v.definition_id, v.counter) for v in setup.relics],
                                  potions=setup.potions, hp=setup.hp, max_hp=setup.max_hp, gold=setup.gold,
                                  encounter_id=setup.encounter_id, seed=self._seed(), cards=self._cards)
        except (ValueError, KeyError) as error:
            raise UnsupportedSearch('belief_setup_unsupported') from error
        world = SimulationWorld(run)
        return world, self._key(world.project()) == self._opening_key

    def _invalidate(self, reason):
        self.reason, self._worlds, self.weights = reason, [], ()

    def _condition(self, propose, limit, work, *, ready=lambda: True):
        accepted = []
        for _ in range(limit):
            if not work.available() or not ready():
                break
            work.proposals += 1
            world, matches = propose()
            if matches:
                accepted.append(world)
                if len(accepted) == self.budget.particles:
                    self._worlds = accepted
                    logs = [self._log_weight(w) for w in accepted]
                    maximum = max(logs)
                    weights = [math.exp(v - maximum) for v in logs]
                    self.weights = tuple(w / sum(weights) for w in weights)
                    self.reason = None
                    return
        # Partial acceptance does not certify a completed fixed-population update.
        # No stale or incomplete posterior may silently continue serving search.
        self._invalidate('belief_budget')

    def _log_weight(self, world):
        # Ordinary full-observation rejection has unit likelihood on accepted
        # proposals. Guided subclasses provide their importance correction.
        return 0.

    def _advance(self, parent, before, action, successor):
        world = parent.fork(self._seed())
        after = world.step(world.project(), action_key(before, action))
        return world, self._key(world.completion if after is None else after) == self._key(successor)

    def _replay(self, work):
        def propose():
            work.replays += 1
            world, matches = self._fresh()
            if not matches:
                return world, False
            for key, expected in self._constraints:
                if not work.available() or work.steps >= self.budget.replay_steps:
                    return world, False
                work.steps += 1
                world = world.fork(self._seed())
                after = world.step(world.project(), key)
                actual = world.completion if after is None else after
                if self._key(actual) != expected:
                    return world, False
            return world, True
        self._condition(propose, self.budget.replay_proposals, work,
                        ready=lambda: not self._constraints or work.steps < self.budget.replay_steps)

    def _finish(self, work, *, recovered=False):
        self.last_update = BeliefUpdate(work.proposals, len(self._worlds),
            time.perf_counter() - work.started, self.reason, work.replays, work.steps,
            recovered and self.reason is None)
        self.updates.append(self.last_update)
        # Diagnostics are bounded independently of how often a controller asks
        # for recovery at the same public decision.
        self.updates[:] = self.updates[-self.budget.history_limit:]
        return self.last_update

    def recover(self, *, seconds=None):
        """Rebuild from public setup/history, with one shared replay deadline."""
        if seconds is not None and (type(seconds) not in (float, int) or not math.isfinite(seconds) or seconds < 0):
            raise ValueError('Invalid recovery deadline')
        if self.reason not in (None, 'belief_budget'):
            raise UnsupportedSearch(self.reason)
        work = _Work(min(self.budget.seconds, seconds) if seconds is not None else self.budget.seconds)
        self._invalidate('belief_budget')
        try:
            if self._constraints:
                self._replay(work)
            else:
                self._condition(self._fresh, self.budget.max_proposals, work)
        except Exception:
            self._invalidate('belief_transition_unsupported')
            raise
        return self._finish(work, recovered=bool(self._constraints))

    def _parent(self, rng):
        if (len(self.weights) != len(self._worlds) or not self.weights or
                any(not math.isfinite(w) or w < 0 for w in self.weights) or sum(self.weights) <= 0):
            raise UnsupportedSearch('belief_invalid_weights')
        return rng.choices(self._worlds, weights=self.weights, k=1)[0]

    def sample(self, seed):
        if self.reason:
            raise UnsupportedSearch(self.reason)
        if isinstance(self.current, CombatEnd):
            raise UnsupportedSearch('combat_complete')
        if type(seed) is not int:
            raise ValueError('A simulation seed is required')
        rng = Random(seed)
        world = self._parent(rng).fork(rng.getrandbits(63))
        projected = world.project()
        if self._key(projected) != self._key(self.current):
            raise UnsupportedSearch('belief_sample_mismatch')
        return world, projected

    def observe_transition(self, before, action, execution, successor, *, seconds=None):
        # Synchronous command reconciliation can expose a still-pending card or
        # potion selector. It does not claim that the parent effect has finished.
        # Native asynchronous acceptance/completion is deliberately not inferred.
        if self.reason not in (None, 'belief_budget'):
            raise UnsupportedSearch(self.reason)
        if seconds is not None and (type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0):
            raise ValueError('Invalid conditioning deadline')
        try:
            c.to_dict(execution)
        except (ValueError, TypeError, AttributeError):
            self._invalidate('belief_invalid_execution')
            raise UnsupportedSearch(self.reason)
        if (not isinstance(before, f.PublicDecision) or before != self.current
                or action not in before.candidates):
            self._invalidate('belief_history_mismatch')
            raise UnsupportedSearch(self.reason)
        if execution.status == 'rejected' and execution.mutation == 'none':
            return BeliefUpdate(0, len(self._worlds), 0., 'rejected_no_mutation')
        if execution.status != 'reconciled':
            self._invalidate('belief_unreconciled')
            raise UnsupportedSearch(self.reason)
        try:
            if isinstance(successor, CombatEnd):
                successor = validate_end(successor)
            else:
                _boundary(successor)
                successor = f.from_dict(f.to_dict(successor))
            expected = self._key(successor)
        except (ValueError, TypeError, AttributeError):
            self._invalidate('belief_boundary_unsupported')
            raise UnsupportedSearch(self.reason)
        if len(self.transitions) >= self.budget.history_limit:
            self._invalidate('belief_history_budget')
            raise UnsupportedSearch(self.reason)
        key = action_key(before, action)
        self.transitions.append((before, action, successor))
        self._constraints.append((key, expected))
        self.current = successor
        work = _Work(min(self.budget.seconds, seconds) if seconds is not None else self.budget.seconds)

        def propose():
            return self._advance(self._parent(self._rng), before, action, successor)

        recovered = False
        try:
            if self.reason is None:
                self._condition(propose, self.budget.max_proposals, work)
            if self.reason == 'belief_budget' and work.available():
                recovered = True
                self._replay(work)
        except Exception:
            self._invalidate('belief_transition_unsupported')
            raise
        return self._finish(work, recovered=recovered)
