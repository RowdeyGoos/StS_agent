"""Gameplay-first regression cases: no projection, protocol, RL or bridge setup."""

import ast
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from game.headless.cards.base import CardDefinition, CardSpec
from game.headless.cards.catalog import CardCatalog, DEFAULT_CARDS
from game.headless.cards.effects import DealDamage
from game.headless.core.actions import EndTurn, PlayCard
from game.headless.core.combat import CombatEngine
from game.headless.encounters.overgrowth import (
    build_overgrowth_slimes_encounter, build_overgrowth_nibbits_encounter,
    build_overgrowth_mawler_encounter, build_overgrowth_shrinker_fuzzy_encounter,
)
from game.headless.map.graph import MapGraph, MapNode
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.run import rewards, rooms
from game.headless.run.engine import RunEngine
from game.headless.run.state import RunPhase


def _play(combat, name):
    card = next(card for card in combat.player.hand if card.name == name)
    return next(action for action in combat.legal_actions() if isinstance(action, PlayCard) and action.instance_id == card.instance_id)


def _json_copy(value):
    return json.loads(json.dumps(value))


def test_gameplay_package_has_no_adapter_dependencies():
    root = Path("game/headless")
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert not node.level, f"Use reviewable absolute core imports: {path}"
                names = [node.module or ""]
            else:
                continue
            assert all(not name.startswith("game.") or name.startswith("game.headless.") for name in names), (path, names)
    result = subprocess.run([sys.executable, "-c", "from game.headless.run.engine import RunEngine; import sys; RunEngine().start_combat(); assert not any(n.startswith(('game.simulation', 'game.contracts', 'game.backends', 'game.agents', 'torch', 'gymnasium', 'numpy')) for n in sys.modules)"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_new_card_family_and_upgrade_need_only_authored_game_definitions():
    # Not registered in any legacy name map, projection, encoder or profile.
    definition = CardDefinition("test.new_attack", (
        CardSpec("New attack", 2, "attack", base_damage=4),
        CardSpec("New attack+", 0, "attack", base_damage=11),
        CardSpec("New attack++", 0, "attack", base_damage=13),
    ), (DealDamage(),))
    cards = CardCatalog((*DEFAULT_CARDS.definitions, definition))
    run = RunEngine(seed=7, cards=cards, card_ids=(definition.definition_id,) * 2)
    target = run.state.deck[0].instance_id
    original = _json_copy(run.snapshot())
    assert run.preview_upgrade(target).base_damage == 11
    assert _json_copy(run.snapshot()) == original
    run.upgrade_card(target)
    assert run.state.deck[0].instance_id == target
    assert run.state.deck[1].upgrade_level == 0
    assert run.state.rng.snapshot() == original["state"]["rng"]
    for _ in range(2):
        combat = run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=15))
        combat.apply(_play(combat, "New attack"))
        assert combat.enemies[0].hp == 11
        assert combat.player.energy == 1
        snapshot = _json_copy(run.snapshot())
        copy = RunEngine(cards=cards)
        copy.restore(snapshot)
        action = _play(combat, "New attack+")
        assert combat.apply(action) == copy.combat.apply(action)
        assert _json_copy(run.snapshot()) == _json_copy(copy.snapshot())
        assert combat.winner == "player" and combat.player.energy == 1
        run.finish_combat()
        assert run.state.deck[0].upgrade_level == 1
        assert run.state.deck[0].instance_id == target
    assert run.state.combats_completed == 2
    run.upgrade_card(target)
    assert run.state.deck[0].spec.base_damage == 13
    before = _json_copy(run.snapshot())
    with pytest.raises(ValueError, match="Unsupported upgrade"):
        run.upgrade_card(target)
    assert _json_copy(run.snapshot()) == before


def test_strike_upgrade_matches_retained_source_values_and_duplicate_identity():
    run = RunEngine(seed=43, card_ids=("strike", "strike", "defend"))
    target = run.state.deck[0].instance_id
    run.upgrade_card(target)
    combat = run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=14))
    combat.apply(_play(combat, "Strike"))
    assert combat.enemies[0].hp == 8
    combat.apply(_play(combat, "Strike+"))
    assert combat.winner == "player" and combat.player.energy == 1
    run.finish_combat()
    combat = run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=14))
    assert next(c for c in combat.player.hand if c.instance_id == target).spec.base_damage == 9
    with pytest.raises(ValueError, match="between rooms"):
        run.upgrade_card(target)


@pytest.mark.parametrize("factory", (build_overgrowth_slimes_encounter, build_overgrowth_nibbits_encounter, build_overgrowth_mawler_encounter, build_overgrowth_shrinker_fuzzy_encounter))
@pytest.mark.parametrize("seed", (0, 43))
def test_exact_snapshot_continuation_preserves_rng_aliases_piles_intents_and_generated_ids(factory, seed):
    run = RunEngine(seed=seed)
    run.upgrade_card(run.state.deck[0].instance_id)
    combat = run.start_combat(encounter_factory=factory)
    for _ in range(35):
        if combat.done:
            break
        saved = _json_copy(combat.snapshot())
        restored = CombatEngine()
        restored.restore(saved)
        assert restored.player.deck.rng is restored.rng
        assert all(enemy.rng is restored.rng for enemy in restored.enemies)
        assert restored.legal_actions() == combat.legal_actions()
        play = next((a for a in combat.legal_actions() if isinstance(a, PlayCard)), EndTurn())
        assert restored.apply(play) == combat.apply(play)
        assert _json_copy(restored.snapshot()) == _json_copy(combat.snapshot())
        cards = [card for pile in (combat.player.deck.draw_pile, combat.player.deck.discard_pile, combat.player.deck.exhaust_pile, combat.player.hand) for card in pile]
        assert len({card.instance_id for card in cards}) == len(cards)


def test_discard_reshuffle_and_branch_mutation_preserve_ownership():
    run = RunEngine(card_ids=("strike", "strike"))
    target = run.state.deck[0].instance_id
    combat = run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=100))
    selected = next(c for c in combat.player.hand if c.instance_id == target)
    combat.apply(PlayCard(target, 0))
    assert selected in combat.player.deck.discard_pile
    combat.apply(EndTurn())
    assert selected in combat.player.hand
    branch = CombatEngine()
    branch.restore(_json_copy(combat.snapshot()))
    next(c for c in branch.player.hand if c.instance_id == target).upgrade()
    assert selected.upgrade_level == run.state.deck[0].upgrade_level == 0


def test_large_game_state_is_not_limited_by_encoder_capacities():
    combat = CombatEngine(deck_factory=lambda: [DEFAULT_CARDS.create("strike") for _ in range(14)],
                          encounter_factory=lambda rng: [SimpleEnemy(max_hp=20) for _ in range(5)], cards_per_turn=14)
    combat.reset()
    assert len(combat.player.hand) == 14
    assert len(combat.legal_actions()) == 1 + 14 * 5
    combat.apply(PlayCard(combat.player.hand[13].instance_id, 4))
    assert combat.enemies[4].hp == 14
    assert all(enemy.hp == 20 for enemy in combat.enemies[:4])


def test_invalid_actions_restores_and_failed_launch_are_atomic():
    run = RunEngine(card_ids=("strike", "defend"))
    original = _json_copy(run.snapshot())
    with pytest.raises(ValueError, match="at least one"):
        run.start_combat(encounter_factory=lambda rng: [])
    assert _json_copy(run.snapshot()) == original
    combat = run.start_combat()
    before = _json_copy(combat.snapshot())
    for action in (PlayCard("missing", 0), PlayCard(combat.player.hand[0].instance_id, 99)):
        with pytest.raises(ValueError, match="Illegal action"):
            combat.apply(action)
        assert _json_copy(combat.snapshot()) == before
    damaged = deepcopy(before)
    damaged["deck"]["piles"]["hand"].append(damaged["deck"]["piles"]["hand"][0])
    with pytest.raises(ValueError, match="Duplicate"):
        combat.restore(damaged)
    assert _json_copy(combat.snapshot()) == before
    with pytest.raises(ValueError, match="Target slot"):
        PlayCard("some_card", True)
    unknown = deepcopy(before)
    unknown["enemies"][0]["type"] = "unregistered.module.Class"
    with pytest.raises(ValueError):
        combat.restore(unknown)
    assert _json_copy(combat.snapshot()) == before


def test_snapshot_rejects_changed_card_values_without_a_new_profile():
    run = RunEngine(card_ids=("strike",))
    saved = run.snapshot()
    strike = DEFAULT_CARDS.definition("strike")
    changed = replace(strike, levels=(replace(strike.levels[0], base_damage=999), *strike.levels[1:]))
    cards = CardCatalog(changed if d.definition_id == "strike" else d for d in DEFAULT_CARDS.definitions)
    other = RunEngine(cards=cards)
    before = other.snapshot()
    with pytest.raises(ValueError, match="card definitions"):
        other.restore(saved)
    assert other.snapshot() == before


def test_run_rewards_rooms_navigation_and_continuation_are_game_rules():
    graph = MapGraph((MapNode("fight", "combat", ("rest", "event")),
                      MapNode("rest", "rest", ("finish",)),
                      MapNode("event", "event", ("finish",)),
                      MapNode("finish", "terminal", ())), "fight")
    run = RunEngine(seed=8, hp=50, card_ids=("strike",), graph=graph)
    assert run.available_nodes() == ("fight",)
    run.choose_node("fight")
    with pytest.raises(ValueError):
        run.choose_node("rest")
    combat = run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=6))
    combat.apply(_play(combat, "Strike"))
    run.finish_combat()
    rewards.begin_reward(run.state, run.cards, gold=25, card_ids=("strike", "defend", "bash"))
    copy = RunEngine()
    copy.restore(_json_copy(run.snapshot()))
    for engine in (run, copy):
        assert rewards.claim_gold(engine.state) == 25
        rewards.choose_card(engine.state, engine.cards, "bash")
        rewards.finish_reward(engine.state)
        engine.choose_node("rest")
        rooms.begin_room(engine.state, kind="rest", options={"rest": ("heal", 15)})
        assert rooms.choose_option(engine.state, "rest") == 15
        rooms.finish_room(engine.state)
        engine.choose_node("finish")
        assert engine.state.phase is RunPhase.VICTORY
    assert _json_copy(run.snapshot()) == _json_copy(copy.snapshot())
    assert run.state.hp == 65 and run.state.gold == 25
    assert [card.definition.definition_id for card in run.state.deck] == ["strike", "bash"]


def test_monster_snapshot_cannot_replace_methods_or_omit_owned_state():
    combat = CombatEngine()
    combat.reset()
    before = _json_copy(combat.snapshot())
    for attribute, value in (("execute_intent", 0), ("_intent_index", "invalid"), ("block", -1)):
        malformed = deepcopy(before)
        malformed["enemies"][0]["state"][attribute] = value
        with pytest.raises(ValueError, match="Monster|monster"):
            combat.restore(malformed)
        assert _json_copy(combat.snapshot()) == before
    malformed = deepcopy(before)
    del malformed["enemies"][0]["state"]["_intent_index"]
    with pytest.raises(ValueError, match="fields"):
        combat.restore(malformed)
    assert _json_copy(combat.snapshot()) == before


def test_independent_engines_own_factory_cards_and_duplicate_objects_reject():
    card = DEFAULT_CARDS.create("strike")
    duplicate = CombatEngine(deck_factory=lambda: [card, card])
    with pytest.raises(ValueError, match="same mutable card"):
        duplicate.reset()
    assert card.instance_id is None
    one = CombatEngine(deck_factory=lambda: [card])
    two = CombatEngine(deck_factory=lambda: [card])
    one.reset()
    two.reset()
    one.player.hand[0].upgrade()
    assert card.upgrade_level == two.player.hand[0].upgrade_level == 0


def test_zero_energy_and_zero_draw_are_valid_roundtrip_states():
    combat = CombatEngine(energy_per_turn=0, cards_per_turn=0)
    combat.reset()
    assert combat.legal_actions() == (EndTurn(),)
    restored = CombatEngine()
    restored.restore(_json_copy(combat.snapshot()))
    assert combat.apply(EndTurn()) == restored.apply(EndTurn())
    assert _json_copy(combat.snapshot()) == _json_copy(restored.snapshot())
    for values in ({"energy_per_turn": -1}, {"cards_per_turn": True}, {"player_max_hp": 0}):
        with pytest.raises(ValueError):
            CombatEngine(**values)


def test_dead_run_is_terminal_and_nonterminal_dead_snapshot_rejects_atomically():
    run = RunEngine(hp=0)
    assert run.state.phase is RunPhase.DEFEAT
    saved = _json_copy(run.snapshot())
    copy = RunEngine()
    copy.restore(saved)
    assert copy.state.phase is RunPhase.DEFEAT
    saved["state"]["phase"] = "route"
    before = _json_copy(copy.snapshot())
    with pytest.raises(ValueError, match="defeat phase"):
        copy.restore(saved)
    assert _json_copy(copy.snapshot()) == before
