"""Combat belief conditioned on public intermediate reveals and a public prefix.

This producer capability currently admits verified fresh Ironclad A0 Vantom
inventories. Later-turn attachment requires the recovered public prefix; no
actual engine or continuation snapshot is accepted by the belief.
"""
from copy import deepcopy
from dataclasses import replace
from random import Random
import math

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.contracts.planning import CombatEnd
from game.agent.headless.identity import Identities
from game.agent.headless.full_relics import WRAPPED
from game.agent.input_views import planning_view
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.draw_knowledge import DrawKnowledge, InconsistentKnowledge
from game.headless.planning import UnsupportedSearch
from game.headless.reveals import CombatReveals, combat_reveals, validate_reveals
from game.headless.run.construction import inventory_combat
from .belief import BeliefUpdate, _boundary, _Work
from .direct import DirectCombatBelief, DirectWorld, _hand, _kinds
from .public_keys import action_key, public_key

MODEL = 'revealed_belief_v1'
ANCHOR = 'sts_observed_combat_anchor_v1'


def inventory(decision):
    """Translate a verified pre-combat public inventory to domain templates."""
    if decision.run.get('character') != 'ironclad' or decision.run.get('ascension') != 0:
        raise UnsupportedSearch('observed_inventory_character')
    groups = {n.kind: n for n in decision.run.children}
    deck = []
    for card in groups['deck'].children:
        if card.get('permanent_damage', 0) or card.get('permanent_block', 0):
            raise UnsupportedSearch('observed_inventory_permanent_modifier')
        enchantment = next((n for n in card.children if n.kind == 'enchantment'), None)
        deck.append((card.definition_id, card.get('upgrade_level'),
                     None if enchantment is None else {v.key: v.value for v in enchantment.fields}))
    relics = []
    for relic in groups['relics'].children:
        name = relic.definition_id
        if relic.get('wax') or relic.get('melted') or relic.children:
            raise UnsupportedSearch('observed_inventory_relic_data')
        if name in WRAPPED or name in ('girya', 'joss_paper', 'sword_of_stone', 'pumpkin_candle'):
            counter = relic.get('display_counter')
            if type(counter) is not int:
                raise UnsupportedSearch('observed_inventory_counter')
        elif name in ('maw_bank', 'lizard_tail', 'lava_rock', 'silken_tress'):
            counter = int(relic.get('status') == 'disabled')
        elif name in ('venerable_tea_set', 'fake_venerable_tea_set'):
            counter = int(relic.get('status') == 'active')
        else:
            # The producer's fresh-inventory certificate must verify this
            # explicit zero-counter declaration against the source inventory.
            counter = 0
        relics.append((name, counter))
    potions = [None if not slot.children else slot.children[0].definition_id
               for slot in groups['potions'].children]
    return dict(deck=deck, relics=relics, potions=potions,
                hp=decision.run.get('hp'), max_hp=decision.run.get('max_hp'), gold=decision.run.get('gold'),
                encounter_id='overgrowth_vantom')


def validate_anchor(anchor):
    if (not isinstance(anchor, dict) or set(anchor) != {'schema', 'initial', 'opening', 'opening_reveals', 'transitions'}
            or anchor['schema'] != ANCHOR or not isinstance(anchor['transitions'], list)
            or len(anchor['transitions']) > 512):
        raise ValueError('Invalid observed combat anchor')
    initial, opening = f.from_dict(anchor['initial']), f.from_dict(anchor['opening'])
    inventory(initial)
    validate_reveals(anchor['opening_reveals'])
    _boundary(opening)
    enemies = next(n for n in opening.context.children if n.kind == 'enemies').children
    if (opening.context.get('round') != 1 or len(enemies) != 1 or enemies[0].definition_id != 'Vantom'
            or any(n.children for n in opening.run.children if n.kind == 'history')):
        raise UnsupportedSearch('observed_anchor_scope')
    current = opening
    for row in anchor['transitions']:
        if not isinstance(row, dict) or set(row) != {'action_ref', 'successor', 'reveals'}:
            raise ValueError('Invalid observed combat prefix')
        if row['action_ref'] not in {a.ref for a in current.candidates}:
            raise ValueError('Prefix action is not advertised')
        validate_reveals(row['reveals'])
        current = f.from_dict(row['successor'])
        _boundary(current)
    return deepcopy(anchor)


class ObservedWorld(DirectWorld):
    def __init__(self, run, knowledge, opening):
        super().__init__(run, knowledge)
        self.public_root = opening

    def _overlay(self, value):
        root = self.public_root.run
        dynamic = {n.kind: n for n in value.children}
        return replace(root, children=tuple(dynamic.get(n.kind, n) if n.kind != 'map' else n for n in root.children),
                       fields=tuple(f.Field(v.key, value.get(v.key)) if v.key in ('hp', 'max_hp', 'gold') else v
                                    for v in root.fields))

    def _project_view(self, decision):
        value = super()._project_view(decision)
        return planning_view(replace(value, run=self._overlay(value.run)))

    def step(self, decision, key):
        value = super().step(decision, key)
        if value is None:
            self.completion = replace(self.completion, run=self._overlay(self.completion.run))
        return value

    def attach(self, root):
        self._ids, self._history, self._powers = Identities(), [], {}
        self._commands = {}
        self.public_root = root


class ObservedCombatBelief(DirectCombatBelief):
    def __init__(self, anchor, current, *, seed, budget):
        self.anchor = validate_anchor(anchor)
        _boundary(current)
        self.initial = f.from_dict(anchor['initial'])
        self.opening = f.from_dict(anchor['opening'])
        self.current = current
        self.budget, self._rng, self._cards = budget, Random(seed), DEFAULT_CARDS
        self.transitions, self._constraints, self.reveal_history = [], [], []
        self._opening_key = self._key(self.opening)
        self._worlds, self.weights = [], ()
        self.reason = 'belief_budget'
        self.last_update = BeliefUpdate(0, 0, 0., self.reason)
        self.updates = []
        self._attachment = current
        self._pending_reveals = None
        self._anchor_progress = 0
        self._anchor_parents, self._anchor_weights = [], ()
        self._anchor_ready = False

    def _fresh_opening(self):
        knowledge = DrawKnowledge()
        events = self.anchor['opening_reveals']
        journal = CombatReveals(events, seed=self._seed())
        knowledge.condition([tuple(e['value']) for e in events if e['kind'] in ('draw', 'autoplay_top')], self._seed())
        try:
            run = inventory_combat(**inventory(self.initial), seed=self._seed(), draw_knowledge=knowledge,
                                   reveal_journal=journal)
            knowledge.finish()
            journal.finish()
            world = ObservedWorld(run, knowledge, self.opening)
            if self._key(world.project()) != self._opening_key:
                return world, False
            world.log_weight = knowledge.log_likelihood + journal.log_likelihood
            return world, True
        except InconsistentKnowledge:
            return None, False

    def _prepare_anchor(self, work):
        """Filter each recovered public boundary once, with one total deadline.

        Accepted anchor particles are immutable parents. A later episode may
        reuse this public-derived preparation; future orders/RNG are resampled.
        No low-probability full-prefix rejection is needed on every attachment.
        """
        if self._anchor_ready:
            return True
        self._worlds, self.weights = self._anchor_parents, self._anchor_weights
        if not self._worlds:
            self._condition(self._fresh_opening, self.budget.max_proposals, work)
            if self.reason:
                return False
            self._anchor_parents, self._anchor_weights = self._worlds, self.weights
        while self._anchor_progress < len(self.anchor['transitions']):
            index = self._anchor_progress
            row = self.anchor['transitions'][index]
            before = self.opening if index == 0 else f.from_dict(self.anchor['transitions'][index-1]['successor'])
            action = next(a for a in before.candidates if a.ref == row['action_ref'])
            after = f.from_dict(row['successor'])
            self._worlds, self.weights = self._anchor_parents, self._anchor_weights
            self.reason = None
            def propose():
                work.steps += 1
                return self._with_reveals(self._parent(self._rng), before, action, after, row['reveals'])
            self._condition(propose, self.budget.max_proposals, work,
                            ready=lambda: work.steps < self.budget.replay_steps)
            if self.reason:
                return False
            self._anchor_parents, self._anchor_weights = self._worlds, self.weights
            self._anchor_progress += 1
        # Rebase only projection ownership/history, retaining inferred rule state
        # and order constraints from the verified source prefix.
        rebased = []
        for parent in self._anchor_parents:
            world = parent.fork()
            world.attach(self._attachment)
            if self._key(world.project()) != self._key(self._attachment):
                self._invalidate('observed_attachment_mismatch')
                raise UnsupportedSearch(self.reason)
            rebased.append(world)
        self._anchor_parents = rebased
        self._anchor_ready = True
        self._worlds, self.weights, self.reason = rebased, self._anchor_weights, None
        return True

    def _fresh(self):
        if not self._anchor_ready:
            raise UnsupportedSearch('missing_prepared_anchor')
        parent = self._rng.choices(self._anchor_parents, weights=self._anchor_weights, k=1)[0]
        world = parent.fork(self._seed())
        world.log_weight = 0.  # The parent was already sampled by posterior weight.
        return world, True

    def _replay(self, work):
        if self._prepare_anchor(work):
            super()._replay(work)

    def recover(self, *, seconds=None):
        if self.reason not in (None, 'belief_budget'):
            raise UnsupportedSearch(self.reason)
        if seconds is not None and (type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0):
            raise ValueError('Invalid recovery deadline')
        work = _Work(min(self.budget.seconds, seconds) if seconds is not None else self.budget.seconds)
        try:
            if self._prepare_anchor(work):
                if self.transitions:
                    super()._replay(work)
                else:
                    self._worlds, self.weights = self._anchor_parents, self._anchor_weights
                    self.reason = None
        except Exception:
            self._invalidate('belief_recovery_unsupported')
            raise
        return self._finish(work, recovered=bool(self.transitions or self.anchor['transitions']))

    def _with_reveals(self, parent, before, action, successor, events):
        world = parent.fork(self._seed())
        journal = CombatReveals(events, seed=self._seed())
        draws = [tuple(e['value']) for e in events if e['kind'] in ('draw', 'autoplay_top')]
        world.knowledge.condition(draws, self._seed())
        try:
            with combat_reveals(world._run.combat, journal):
                after = world.step(world.project(), action_key(before, action))
            world.knowledge.finish()
            journal.finish()
        except InconsistentKnowledge:
            return world, False
        world.log_weight = world.knowledge.log_likelihood + journal.log_likelihood
        return world, self._key(world.completion if after is None else after) == self._key(successor)

    def _advance(self, parent, before, action, successor):
        # _advance is called by ordinary conditioning and prefix recovery.
        index = next(i for i, (b, a, s) in enumerate(self.transitions)
                     if b is before and a is action and s is successor)
        return self._with_reveals(parent, before, action, successor, self.reveal_history[index])

    def receive_reveals(self, events):
        if self._pending_reveals is not None:
            raise ValueError('Unconsumed combat reveal receipt')
        self._pending_reveals = validate_reveals(events)

    def observe_transition(self, before, action, execution, successor, *, seconds=None):
        events, self._pending_reveals = self._pending_reveals, None
        if events is None:
            self._invalidate('missing_combat_reveals')
            raise UnsupportedSearch(self.reason)
        count = len(self.transitions)
        self.reveal_history.append(events)
        try:
            return super().observe_transition(before, action, execution, successor, seconds=seconds)
        finally:
            if len(self.transitions) == count:
                self.reveal_history.pop()

    def sample(self, seed):
        world, observation = super().sample(seed)
        # Complete determinizations execute the unconditioned normal engine.
        stream = world._run.combat.player.deck.rng
        if hasattr(stream, 'draw_knowledge'):
            del stream.draw_knowledge
        return world, observation
