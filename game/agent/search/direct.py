"""Direct conditional draw sampling, with particles for other hidden state.

Inputs are the same public declaration/observations used by the replay model.
The engine maintains known placements while an unobserved remaining permutation
is integrated out. Draws and opening HP use guided proposals with likelihood
weights; other outcomes still require a complete public match. This is a finite
particle approximation, not an exact posterior over every hidden game variable.
"""
from copy import deepcopy
import time

from game.agent.input_views import DETACHED_HISTORY as VIEW, planning_view, PlanningViewPolicy
from game.agent.contracts.planning import CombatEnd, validate_start
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.draw_knowledge import DrawKnowledge, HPKnowledge, InconsistentKnowledge
from game.headless.planning import UnsupportedSearch
from game.headless.run.construction import declared_combat, materialize_combat_draw
from .belief import CombatBelief, _key
from .public_keys import action_key
from .world import SimulationWorld

MODEL = 'direct_belief_v1'

# Capability guards for the conditional-observation grammar, not card rules.
# No innate/enchantments, autoplay, random insertion, hidden card mutation,
# retention or generated/moved cards entering hand between public boundaries.
CARDS = frozenset('''strike defend bash headbutt pommel_strike shrug_it_off
    burning_pact true_grit hemokinesis twin_strike iron_wave thunderclap
    bludgeon body_slam uppercut impervious inflame barricade flame_barrier
    wound dazed slimed burn'''.split())
RELICS = frozenset(('burning_blood', 'nunchaku', 'anchor', 'bag_of_preparation'))
POTIONS = frozenset(('fire_potion', 'block_potion', 'strength_potion', 'dexterity_potion',
                     'energy_potion', 'swift_potion', 'blood_potion', 'explosive_ampoule'))
ENCOUNTERS = frozenset(('overgrowth_nibbit', 'overgrowth_slimes', 'overgrowth_bygone_effigy',
    'overgrowth_vantom', 'underdocks_corpse_slugs_weak', 'underdocks_living_fog',
    'underdocks_skulking_colony', 'underdocks_lagavulin_matriarch'))


def _hand(decision):
    return next(n.children for n in decision.context.children if n.kind == 'pile' and n.definition_id == 'hand')


def _kinds(cards):
    return [(n.definition_id, n.get('upgrade_level')) for n in cards]


def observed_draws(before, action, after):
    if isinstance(after, CombatEnd):
        # No final hand is observed. Let the engine sample any unobserved draws,
        # and condition only on the public settled outcome/inventory.
        return None
    if action.kind == 'end_turn':
        return _kinds(_hand(after))
    old = {n.ref for n in _hand(before)}
    return _kinds(n for n in _hand(after) if n.ref not in old)


class DirectWorld(SimulationWorld):
    def __init__(self, run, knowledge):
        super().__init__(run)
        self.knowledge = knowledge
        self.log_weight = 0.
        run.combat.player.deck.rng.draw_knowledge = knowledge

    def _project_view(self, decision):
        return planning_view(super()._project_view(decision))

    def fork(self, seed=None):
        world = super().fork(seed)
        world.knowledge = deepcopy(self.knowledge)
        # Separate proposal randomness from both the real RNG and future engine
        # streams. A fork with no new seed preserves the already sampled world.
        world.knowledge.condition(None, 0 if seed is None else seed ^ 0x44524157)
        deck = world._run.combat.player.deck
        deck.rng.draw_knowledge = world.knowledge
        if seed is not None:
            materialize_combat_draw(world._run, world.knowledge)
        world.log_weight = 0.
        return world


class DirectCombatBelief(CombatBelief):
    def __init__(self, setup, opening, **kwargs):
        setup = validate_start(setup)
        if (setup.card_catalog != DEFAULT_CARDS.snapshot_fingerprint() or
                kwargs.get('cards', DEFAULT_CARDS).snapshot_fingerprint() != setup.card_catalog):
            raise UnsupportedSearch('direct_catalog_unsupported')
        if (setup.encounter_id not in ENCOUNTERS or any(c.definition_id not in CARDS for c in setup.deck)
                or any(r.definition_id not in RELICS for r in setup.relics)
                or any(p is not None and p not in POTIONS for p in setup.potions)):
            raise UnsupportedSearch('direct_setup_unsupported')
        super().__init__(setup, opening, **kwargs)

    def _key(self, value):
        return _key(planning_view(value))

    def _fresh(self):
        setup = self.setup
        knowledge = DrawKnowledge()
        knowledge.condition(_kinds(_hand(self.opening)), self._seed())
        enemies = next(n.children for n in self.opening.context.children if n.kind == 'enemies')
        hp = HPKnowledge(tuple(n.get('max_hp') for n in enemies))
        try:
            run = declared_combat(deck=[(v.definition_id, v.upgrade_level) for v in setup.deck],
                relics=[(v.definition_id, v.counter) for v in setup.relics], potions=setup.potions,
                hp=setup.hp, max_hp=setup.max_hp, gold=setup.gold,
                encounter_id=setup.encounter_id, seed=self._seed(), cards=self._cards,
                draw_knowledge=knowledge, hp_knowledge=hp)
            knowledge.finish()
        except InconsistentKnowledge:
            return None, False
        except (ValueError, KeyError) as error:
            raise UnsupportedSearch('belief_setup_unsupported') from error
        world = DirectWorld(run, knowledge)
        world.log_weight = knowledge.log_likelihood + hp.log_likelihood
        return world, self._key(world.project()) == self._opening_key

    def _log_weight(self, world):
        return world.log_weight

    def _advance(self, parent, before, action, successor):
        world = parent.fork(self._seed())
        world.knowledge.condition(observed_draws(before, action, successor), self._seed())
        try:
            after = world.step(world.project(), action_key(before, action))
            world.knowledge.finish()
        except InconsistentKnowledge:
            return world, False
        world.log_weight = world.knowledge.log_likelihood
        return world, self._key(world.completion if after is None else after) == self._key(successor)

    def _replay(self, work):
        def propose():
            work.replays += 1
            world, matches = self._fresh()
            if not matches:
                return world, False
            log_weight = world.log_weight
            for before, action, successor in self.transitions:
                if not work.available() or work.steps >= self.budget.replay_steps:
                    return world, False
                work.steps += 1
                world, matches = self._advance(world, before, action, successor)
                if not matches:
                    return world, False
                log_weight += world.log_weight
            world.log_weight = log_weight
            return world, True
        self._condition(propose, self.budget.replay_proposals, work,
                        ready=lambda: not self.transitions or work.steps < self.budget.replay_steps)
