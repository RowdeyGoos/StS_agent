"""Verified encounter rules and authored route progression toward Act 1."""

import json
from copy import deepcopy
from random import Random

import pytest

from game.cli.headless_play import choose_demo_action, main, play_slice
from game.headless.core.actions import EndTurn, PlayCard
from game.headless.core.combat import CombatEngine
from game.headless.core.deck import Deck
from game.headless.core.player import Player
from game.headless.encounters.catalog import ENCOUNTERS
from game.headless.encounters.overgrowth import build_overgrowth_nibbits_encounter
from game.headless.monsters.overgrowth import FuzzyWurmCrawler, Mawler, Nibbit
from game.headless.run.actions import ChooseNode
from game.headless.run.engine import RunEngine
from game.headless.run.state import RunPhase


def saved(engine):
    return json.loads(json.dumps(engine.snapshot()))


class Rolls(Random):
    def __init__(self, values):
        super().__init__(0)
        self.values = iter(values)
        self.calls = 0

    def random(self):
        self.calls += 1
        return next(self.values)


def test_fuzzy_hp_full_cycles_strength_and_no_move_rng():
    assert {FuzzyWurmCrawler(Random(seed)).hp for seed in range(100)} == {55, 56, 57}
    enemy = FuzzyWurmCrawler(Random(4))
    player = Player(Deck([], Random(0)), max_hp=1000)
    rng_before = enemy.rng.getstate()
    for damage, strength in [(4, 0), (0, 7), (11, 7), (11, 7), (0, 14), (18, 14), (18, 14)]:
        before = player.hp
        enemy.execute_intent(player)
        assert before - player.hp == damage
        assert enemy.strength == strength
    assert enemy.rng.getstate() == rng_before


@pytest.mark.parametrize("role,opening", [("solo", "Butt"), ("front", "Hesitant Slice"), ("back", "Hiss")])
def test_nibbit_role_changes_only_opening(role, opening):
    enemy = Nibbit(Random(2), role=role)
    assert enemy.intent.move_name == opening
    moves = []
    for _ in range(6):
        moves.append(enemy.intent.move_name)
        enemy.advance_intent()
    assert moves[:3] == moves[3:]
    assert set(moves) == {"Butt", "Hesitant Slice", "Hiss"}


def test_invalid_nibbit_role_rejects_before_rng_consumption():
    rng = Random(3)
    before = rng.getstate()
    with pytest.raises(ValueError):
        Nibbit(rng, role="unknown")
    assert rng.getstate() == before


def test_paired_nibbit_self_buffs_slot_order_and_survivor_keep_their_cycle():
    combat = CombatEngine(encounter_factory=build_overgrowth_nibbits_encounter, player_max_hp=1000, cards_per_turn=0)
    combat.reset()
    front, back = combat.enemies
    assert [e.intent.move_name for e in combat.enemies] == ["Hesitant Slice", "Hiss"]
    for damage, strengths in [(6, (0, 2)), (14, (2, 2)), (22, (2, 2))]:
        hp = combat.player.hp
        combat.apply(EndTurn())
        assert hp - combat.player.hp == damage
        assert (front.strength, back.strength) == strengths
    assert front.intent.move_name == "Hesitant Slice" and back.intent.move_name == "Hiss"
    front.hp = 0
    combat.resolve_external_effect()
    assert not combat.done and combat.enemies[1] is back
    combat.apply(EndTurn())
    assert back.strength == 4 and back.intent.move_name == "Butt"
    hp = combat.player.hp
    combat.apply(EndTurn())
    assert hp - combat.player.hp == 16


@pytest.mark.parametrize("roll,expected", [(0.0, "Rip and Tear"), (0.4999, "Rip and Tear"),
                                           (0.5, "Roar"), (0.9999, "Roar")])
def test_mawler_equal_first_branch_boundaries(roll, expected):
    rng = Rolls([roll])
    enemy = Mawler(rng)
    assert enemy.hp == 72 and enemy.intent.move_name == "Claw"
    enemy.advance_intent()
    assert enemy.intent.move_name == expected and rng.calls == 1


def test_mawler_roar_once_alternation_and_forced_rolls():
    rng = Rolls([0.9, 0.1, 0.99, 0.0, 0.5])
    enemy = Mawler(rng)
    moves = []
    for _ in range(5):
        moves.append(enemy.intent.move_name)
        enemy.advance_intent()
    assert moves == ["Claw", "Roar", "Rip and Tear", "Claw", "Rip and Tear"]
    assert rng.calls == 5  # Includes successors with exactly one eligible attack.
    assert enemy._roar_used


def test_mawler_roar_player_duration_and_followup_damage_restore():
    combat = CombatEngine(encounter_factory=ENCOUNTERS["overgrowth_mawler"], deck_factory=lambda: [], cards_per_turn=0)
    combat.reset(seed=0)
    # Own a chosen deterministic RNG state; seed0 first roll selects Roar.
    combat.apply(EndTurn())
    assert combat.player.hp == 72 and combat.enemies[0].intent.move_name == "Roar"
    combat.apply(EndTurn())
    assert combat.player.statuses.get("vulnerable") == 3
    assert combat.player.statuses._skip_next_tick == set()
    clone = CombatEngine()
    clone.restore(saved(combat))
    for engine in (combat, clone):
        move = engine.enemies[0].intent
        damage = move.attack_damage * 3 // 2 * move.attack_count
        hp = engine.player.hp
        engine.apply(EndTurn())
        assert hp - engine.player.hp == damage
        assert engine.player.statuses.get("vulnerable") == 2
    assert saved(combat) == saved(clone)


@pytest.mark.parametrize("encounter", ["overgrowth_fuzzy", "overgrowth_mawler", "overgrowth_nibbits"])
def test_encounter_cycles_restore_and_branch_rng_remains_owned(encounter):
    combat = CombatEngine(encounter_factory=ENCOUNTERS[encounter], player_max_hp=1000, cards_per_turn=0)
    combat.reset(seed=7)
    for _ in range(12):
        clone = CombatEngine()
        clone.restore(saved(combat))
        assert clone.rng is clone.player.deck.rng
        assert all(e.rng is clone.rng for e in clone.enemies)
        assert clone.rng is not combat.rng
        combat.apply(EndTurn())
        clone.apply(EndTurn())
        assert saved(combat) == saved(clone)


@pytest.mark.parametrize("first_branch", ["slimes", "fuzzy"])
@pytest.mark.parametrize("last_branch", ["mawler", "nibbits", "byrdonis"])
@pytest.mark.parametrize("rest_choice", ["rest", "smith"])
def test_every_authored_path_four_combats_rewards_and_restore(first_branch, last_branch, rest_choice):
    run = RunEngine.ironclad_slice(seed=2, route="overgrowth")
    for _ in range(200):
        actions = run.legal_actions()
        if not actions:
            break
        nodes = [a for a in actions if isinstance(a, ChooseNode)]
        action = next((a for a in nodes if a.node_id in (first_branch, last_branch)), None)
        action = action or choose_demo_action(run, rest_choice)
        clone = RunEngine()
        clone.restore(saved(run))
        assert clone.legal_actions() == actions
        run.apply(action)
        clone.apply(action)
        assert saved(run) == saved(clone)
    assert run.state.phase is RunPhase.SLICE_COMPLETE
    assert run.state.combats_completed == 4
    assert run.state.visited_nodes == ["fight_1", first_branch,
        "fuzzy_after_slimes" if first_branch == "slimes" else "slimes_after_fuzzy",
        "camp", last_branch, "slice_end"]
    assert len(run.state.deck) == 14
    low, high = (164, 204) if last_branch == "byrdonis" else (139, 179)
    assert low <= run.state.gold <= high
    assert len(run.state.relics) == (2 if last_branch == "byrdonis" else 1)
    assert sum(c.upgrade_level for c in run.state.deck) == (rest_choice == "smith")
    assert run.legal_actions() == ()


def test_sibling_branch_and_visited_node_cannot_be_entered_or_forged():
    run = RunEngine.ironclad_slice(seed=2, route="overgrowth")
    for _ in range(100):
        if ChooseNode("slimes") in run.legal_actions():
            break
        run.apply(choose_demo_action(run))
    run.apply(ChooseNode("slimes"))
    before = saved(run)
    for action in (ChooseNode("fuzzy"), ChooseNode("fight_1")):
        with pytest.raises(ValueError):
            run.apply(action)
        assert saved(run) == before
    invalid = deepcopy(before)
    invalid["state"]["visited_nodes"] = ["fight_1", "fuzzy", "slimes"]
    with pytest.raises(ValueError):
        run.restore(invalid)
    assert saved(run) == before


def test_mawler_invalid_move_history_restore_is_atomic():
    combat = CombatEngine(encounter_factory=ENCOUNTERS["overgrowth_mawler"])
    combat.reset()
    before = saved(combat)
    for change in ("used_roar", "unknown_move"):
        invalid = deepcopy(before)
        state = invalid["enemies"][0]["state"]
        if change == "used_roar":
            from dataclasses import asdict
            state["_current_intent"] = {"intent": asdict(Mawler.ROAR)}
            state["_roar_used"] = True
        else:
            state["_current_intent"]["intent"]["move_name"] = "unknown"
        with pytest.raises(ValueError):
            combat.restore(invalid)
        assert saved(combat) == before


def test_branching_cli_reports_real_scope_and_route(capsys):
    main(["--route", "overgrowth", "--path", "right", "--seed", "2", "--rest-choice", "rest", "--verify-restore"])
    result = json.loads(capsys.readouterr().out)
    assert result["scope"] == "restricted_ironclad_a0_overgrowth_route"
    assert result["route"] == "overgrowth" and result["path"] == "right"
    assert result["phase"] == "slice_complete" and result["combats_completed"] == 4
    assert result["restore_verified"]
    with pytest.raises(ValueError):
        play_slice(route="unknown")
    with pytest.raises(ValueError):
        play_slice(path="unknown")


def test_overgrowth_defeat_does_not_grant_rewards_or_slice_completion():
    run = RunEngine.ironclad_slice(route="overgrowth")
    run.state.hp = 1
    run.apply(ChooseNode("fight_1"))
    run.apply(EndTurn())
    assert run.state.phase is RunPhase.DEFEAT and run.state.hp == 0
    assert run.state.gold == 99 and len(run.state.deck) == 10
    assert run.state.pending is None and run.legal_actions() == ()
    clone = RunEngine()
    clone.restore(saved(run))
    assert saved(run) == saved(clone)
