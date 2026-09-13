"""Source-checked boss/card boundaries and restricted act completion."""

import json
from copy import deepcopy
from dataclasses import replace
from random import Random

import pytest

from game.cli.headless_play import play_slice
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import EndTurn, PlayCard
from game.headless.core.combat import CombatEngine
from game.headless.core.deck import Deck
from game.headless.core.player import Player
from game.headless.monsters.vantom import Vantom
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.run.actions import ClaimGold, ChooseRewardCard, LeaveRewards, ChooseNode, ClaimRelic
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.state import RunPhase, ActCompletion
from game.headless.map.graph import MapGraph, MapNode


def saved(engine):
    return json.loads(json.dumps(engine.snapshot()))


def restored(run):
    clone = RunEngine()
    clone.restore(saved(run))
    return clone


def reject_restore(run, mutate):
    before = saved(run)
    invalid = deepcopy(before)
    mutate(invalid)
    with pytest.raises(ValueError):
        run.restore(invalid)
    assert saved(run) == before


def combat_with(card_id, upgrade=0, other_cards=(), hp=80, enemy=None):
    cards = [DEFAULT_CARDS.create(card_id, upgrade_level=upgrade),
             *(DEFAULT_CARDS.create(c) for c in other_cards)]
    combat = CombatEngine(deck_factory=lambda: cards, player_max_hp=hp,
                          cards_per_turn=len(cards), enemy_factory=enemy or (lambda: SimpleEnemy(max_hp=1000)))
    combat.reset()
    return combat


def play(combat, card_id):
    card = next(c for c in combat.player.hand if c.definition.definition_id == card_id)
    return combat.apply(PlayCard(card.instance_id, 0 if card.spec.uses_target else None))


def won_boss():
    run = RunEngine(config=RunConfig(), card_ids=("strike",))
    run.start_combat(encounter_id="overgrowth_vantom")
    # Synthetic lethal boundary, distinct from ordinary route play.
    run.combat.enemies[0].statuses.decrement("slippery", 8)
    run.combat.player.gain_strength(200)
    run.apply(PlayCard(run.combat.player.hand[0].instance_id, 0))
    return run


def test_vantom_opening_cycles_wounds_strength_and_no_move_rng():
    enemy = Vantom(Random(7))
    player = Player(Deck([], Random(0)), max_hp=1000)
    assert enemy.hp == 173 and enemy.statuses.get("slippery") == 8
    rng = enemy.rng.getstate()
    expected = [("Ink Blot", 7), ("Inky Lance", 12), ("Dismember", 26), ("Prepare", 0),
                ("Ink Blot", 9), ("Inky Lance", 16), ("Dismember", 28), ("Prepare", 0)]
    for index, (name, damage) in enumerate(expected):
        assert enemy.intent.move_name == name
        before = player.hp
        enemy.execute_intent(player)
        assert before - player.hp == damage
        assert enemy.strength == ((index + 1) // 4) * 2
    wounds = player.deck.discard_pile
    assert len(wounds) == 6 and {c.definition.definition_id for c in wounds} == {"wound"}
    assert len({c.instance_id for c in wounds}) == 6
    assert enemy.rng.getstate() == rng and enemy.statuses.get("slippery") == 8


@pytest.mark.parametrize("is_attack", [True, False])
def test_slippery_applies_after_block_and_only_consumes_unblocked_hits(is_attack):
    enemy = Vantom(Random(0))
    enemy.gain_block(10)
    assert enemy.take_damage(9, is_attack=is_attack) == 0
    assert enemy.block == 1 and enemy.statuses.get("slippery") == 8
    assert enemy.take_damage(100, is_attack=is_attack) == 1
    assert enemy.block == 0 and enemy.statuses.get("slippery") == 7
    assert enemy.take_damage(0, is_attack=is_attack) == 0
    assert enemy.statuses.get("slippery") == 7
    for _ in range(7):
        assert enemy.take_damage(50, is_attack=is_attack) == 1
    assert enemy.take_damage(50, is_attack=is_attack) == 50
    assert enemy.hp == 115


def test_slippery_caps_modified_damage_and_lasts_across_turns():
    enemy = Vantom(Random(0))
    enemy.apply_status("vulnerable", 2)
    assert enemy.take_damage(9, attacker_strength=10) == 1
    player = Player(Deck([], Random(0)))
    enemy.execute_intent(player)
    assert enemy.statuses.get("slippery") == 7
    enemy.take_damage(1)
    assert enemy.statuses.get("slippery") == 6


def test_vantom_every_phase_restore_generated_ids_and_owned_rng():
    run = RunEngine(config=RunConfig(), max_hp=1000, card_ids=())
    run.start_combat(encounter_id="overgrowth_vantom", cards_per_turn=0)
    for _ in range(12):
        other = restored(run)
        assert other.combat.enemies[0].rng is other.combat.player.deck.rng
        run.apply(EndTurn())
        other.apply(EndTurn())
        assert saved(run) == saved(other)
    assert len(run.combat.player.deck.discard_pile) == 9


def test_lethal_dismember_stops_before_wound_generation_and_rewards():
    run = RunEngine(config=RunConfig(), hp=1, card_ids=())
    run.start_combat(encounter_id="overgrowth_vantom", cards_per_turn=0)
    combat = run.combat
    combat.enemies[0]._intent_index = 2
    run.apply(EndTurn())
    assert run.state.phase is RunPhase.DEFEAT and run.state.pending is None
    assert not combat.player.deck.discard_pile and combat.enemies[0]._intent_index == 2
    assert run.state.act_completion is None
    assert saved(restored(run)) == saved(run)


def test_wound_unplayable_unupgradable_but_can_be_exhausted():
    combat = combat_with("true_grit", 1, ("wound",))
    wound = next(c for c in combat.player.hand if c.name == "Wound")
    assert PlayCard(wound.instance_id) not in combat.legal_actions()
    before = saved(combat)
    with pytest.raises(ValueError):
        combat.player.play_card(combat.player.hand.index(wound), None)
    with pytest.raises(ValueError):
        wound.upgrade()
    assert saved(combat) == before
    play(combat, "true_grit")
    assert wound in combat.player.deck.exhaust_pile


@pytest.mark.parametrize("upgrade,block", [(0, 30), (1, 40)])
def test_impervious_block_cost_and_exhaust(upgrade, block):
    combat = combat_with("impervious", upgrade)
    play(combat, "impervious")
    assert combat.player.block == block and combat.player.energy == 1
    assert len(combat.player.deck.exhaust_pile) == 1


@pytest.mark.parametrize("upgrade,draws", [(0, 3), (1, 5)])
def test_offering_loses_hp_through_block_then_gains_energy_and_draws(upgrade, draws):
    combat = combat_with("offering", upgrade)
    for _ in range(7):
        combat.player.add_card_to_discard(DEFAULT_CARDS.create("strike"))
    combat.player.gain_block(20)
    play(combat, "offering")
    assert (combat.player.hp, combat.player.block, combat.player.energy) == (74, 20, 5)
    assert len(combat.player.hand) == draws
    assert [c.name for c in combat.player.deck.exhaust_pile] == ["Offering+" if upgrade else "Offering"]
    other = CombatEngine()
    other.restore(saved(combat))
    assert saved(other) == saved(combat)


@pytest.mark.parametrize("hp", [1, 6])
def test_lethal_offering_never_grants_energy_draws_or_victory(hp):
    combat = combat_with("offering", hp=hp)
    combat.player.add_card_to_discard(DEFAULT_CARDS.create("strike"))
    rng = combat.rng.getstate()
    result = play(combat, "offering")
    assert result.done and result.winner == "enemy"
    assert combat.player.energy == 3 and not combat.player.hand
    assert combat.rng.getstate() == rng
    assert len(combat.player.deck.exhaust_pile) == 1


@pytest.mark.parametrize("upgrade,damage", [(0, 21), (1, 30)])
def test_fiend_fire_captures_other_hand_cards_then_hits_and_exhausts_self(upgrade, damage):
    combat = combat_with("fiend_fire", upgrade, ("strike", "wound", "defend"))
    ids = {c.instance_id for c in combat.player.hand}
    play(combat, "fiend_fire")
    assert combat.enemies[0].hp == 1000 - damage and combat.player.energy == 1
    assert not combat.player.hand and not combat.player.deck.in_play
    assert {c.instance_id for c in combat.player.deck.exhaust_pile} == ids
    assert combat.player.deck.exhaust_pile[-1].definition.definition_id == "fiend_fire"


def test_fiend_fire_each_hit_consumes_slippery_and_remaining_hits_use_full_damage():
    combat = combat_with("fiend_fire", 0, ("wound",) * 4, enemy=lambda: Vantom(Random(0)))
    enemy = combat.enemies[0]
    enemy.statuses.decrement("slippery", 6)
    play(combat, "fiend_fire")
    assert enemy.hp == 173 - 1 - 1 - 7 - 7 and not enemy.statuses.get("slippery")


def test_fiend_fire_empty_hand_and_lethal_target_do_not_add_hits():
    combat = combat_with("fiend_fire")
    play(combat, "fiend_fire")
    assert combat.enemies[0].hp == 1000
    combat = combat_with("fiend_fire", other_cards=("wound",) * 3,
                          enemy=lambda: SimpleEnemy(max_hp=1))
    assert play(combat, "fiend_fire").winner == "player"
    assert len(combat.player.deck.exhaust_pile) == 4


def test_boss_rewards_distinct_pool_exact_gold_no_relic_and_completion_after_exit_only():
    run = won_boss()
    assert run.state.phase is RunPhase.REWARD and run.state.act_completion is None
    assert run.state.pending["gold"] == 100
    from game.headless.cards.pools import RARE_CARDS
    assert len(set(run.state.pending["offers"])) == 3
    assert set(run.state.pending["offers"]) <= set(RARE_CARDS)
    assert run.state.pending["relic"] is None and ClaimRelic() not in run.legal_actions()
    run.apply(ClaimGold())
    run.apply(ChooseRewardCard(run.state.pending["offers"][0]))
    other = restored(run)
    for engine in (run, other):
        engine.apply(LeaveRewards())
        assert engine.state.phase is RunPhase.ACT_COMPLETE
        assert engine.state.act_completion == ActCompletion(1, "overgrowth_vantom")
        assert engine.state.gold == 100 and engine.legal_actions() == ()
        with pytest.raises(ValueError):
            engine.apply(LeaveRewards())
        with pytest.raises(ValueError):
            engine.start_combat(encounter_id="overgrowth_nibbit")
    assert saved(run) == saved(other) == saved(restored(run))


def test_boss_rewards_can_be_forfeited_without_losing_completion():
    run = won_boss()
    rng = run.state.rng.snapshot()
    run.apply(LeaveRewards())
    assert run.state.gold == 0 and len(run.state.deck) == 1
    assert run.state.phase is RunPhase.ACT_COMPLETE and run.state.rng.snapshot() == rng


@pytest.mark.parametrize("record", [None, {"act": 2, "boss_encounter_id": "overgrowth_vantom"},
    {"act": True, "boss_encounter_id": "overgrowth_vantom"},
    {"act": 1, "boss_encounter_id": "overgrowth_byrdonis"},
    {"act": 1, "boss_encounter_id": "unknown"}])
def test_malformed_act_completion_restore_rejected_atomically(record):
    run = won_boss()
    run.apply(LeaveRewards())
    reject_restore(run, lambda s: s["state"].__setitem__("act_completion", record))


@pytest.mark.parametrize("field,value", [("gold", 99), ("offers", ["strike", "defend", "bash"]),
                                        ("relic", "pear"), ("encounter_id", "overgrowth_byrdonis")])
def test_forged_boss_reward_bundle_rejected(field, value):
    reject_restore(won_boss(), lambda s: s["state"]["pending"].__setitem__(field, value))


def test_act_completion_cannot_be_reached_through_a_map_terminal_node():
    graph = MapGraph((MapNode("fake", "act_complete", ()),), "fake")
    run = RunEngine(config=RunConfig(), graph=graph)
    before = saved(run)
    with pytest.raises(ValueError):
        run.apply(ChooseNode("fake"))
    assert saved(run) == before


def test_maze_elite_demo_replays_defeat_without_fabricating_act_completion(monkeypatch):
    from game.headless.run import scenarios
    graph = scenarios.overgrowth_act1_map()
    maze_route = MapGraph(tuple(replace(node, next_node_ids=tuple(
        target for target in node.next_node_ids if target != "aroma"))
        for node in graph.nodes if node.node_id != "aroma"), graph.start_id)
    monkeypatch.setattr(scenarios, "ROUTES", {**scenarios.ROUTES, "overgrowth-act1": lambda: maze_route})
    run, trace = play_slice(seed=2, route="overgrowth-act1", rest_choice="rest", path="right", verify_restore=True)
    assert run.state.phase is RunPhase.DEFEAT
    assert "vantom" in run.state.visited_nodes and run.state.act_completion is None
    assert any(t.get("node_id") == "boss_camp" for t in trace)
    assert all(c.definition.definition_id != "wound" for c in run.state.deck)


def test_boss_node_restore_and_reward_identity_survive_graph_continuation():
    graph = MapGraph((MapNode("vantom", "boss", (), "overgrowth_vantom"),), "vantom")
    run = RunEngine(config=RunConfig(), graph=graph)
    run.apply(ChooseNode("vantom"))
    assert saved(restored(run)) == saved(run)
    reject_restore(run, lambda s: s["state"].__setitem__("active_encounter_id", "overgrowth_nibbit"))
    reject_restore(run, lambda s: s.__setitem__("schema", "headless_run_state_v3"))
    reject_restore(run, lambda s: s["combat"]["enemies"][0]["state"].__setitem__("_intent_index", 4))
