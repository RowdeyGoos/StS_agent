"""Native A0 elite rules and restricted authored reward continuation."""

import json
from copy import deepcopy
from random import Random

import pytest

from game.cli.headless_play import play_slice
from game.headless.core.actions import EndTurn, PlayCard
from game.headless.core.combat import CombatEngine
from game.headless.core.deck import Deck
from game.headless.core.player import Player
from game.headless.encounters.catalog import ENCOUNTERS
from game.headless.map.graph import MapGraph, MapNode
from game.headless.monsters.byrdonis import Byrdonis
from game.headless.run.actions import ClaimGold, ClaimRelic, ChooseRewardCard, LeaveRewards, ChooseNode
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_relic, remove_relic
from game.headless.run.state import RunPhase


def saved(engine):
    return json.loads(json.dumps(engine.snapshot()))


def clone(run):
    other = RunEngine()
    other.restore(saved(run))
    return other


def elite_run(seed=0, **kwargs):
    run = RunEngine(seed=seed, config=RunConfig(), card_ids=("strike",), **kwargs)
    run.start_combat(encounter_id="overgrowth_byrdonis")
    return run


def won_elite(seed=0):
    run = elite_run(seed)
    # Synthetic reward boundary; route tests below win through ordinary actions.
    run.combat.player.gain_strength(100)
    run.apply(PlayCard(run.combat.player.hand[0].instance_id, 0))
    assert run.state.phase is RunPhase.REWARD
    return run


def reject_restore(run, corrupt):
    before = saved(run)
    invalid = deepcopy(before)
    corrupt(invalid)
    with pytest.raises(ValueError):
        run.restore(invalid)
    assert saved(run) == before


def test_byrdonis_native_hp_opening_cycles_and_territorial_without_rng():
    assert {Byrdonis(Random(seed)).hp for seed in range(100)} == {81, 82, 83, 84}
    enemy = Byrdonis(Random(0))
    player = Player(Deck([], Random(0)), max_hp=1000)
    rng = enemy.rng.getstate()
    for turn, (move, damage) in enumerate([
        ("Swoop", 17), ("Peck", 12), ("Swoop", 19), ("Peck", 18),
    ], 1):
        assert enemy.intent.move_name == move
        hp = player.hp
        enemy.execute_intent(player)
        assert hp - player.hp == damage
        assert enemy.strength == turn and enemy.statuses.get("territorial") == 1
    assert enemy.rng.getstate() == rng


def test_territorial_owner_side_stacks_once_for_each_living_owner():
    combat = CombatEngine(encounter_factory=lambda rng: [Byrdonis(rng), Byrdonis(rng)],
                          player_max_hp=1000, cards_per_turn=0)
    combat.reset()
    first, second = combat.enemies
    first.statuses.add("territorial", 1)
    combat.player.statuses.add("territorial", 3)
    combat.apply(EndTurn())
    assert combat.player.hp == 966  # No enemy Strength at player-side end.
    assert [e.strength for e in combat.enemies] == [2, 1]
    assert combat.player.strength == 3  # Once, on the player's own side only.
    first.hp = 0
    combat.resolve_external_effect()
    combat.apply(EndTurn())
    assert [e.strength for e in combat.enemies] == [2, 2]
    second.statuses.decrement("territorial")
    combat.apply(EndTurn())
    assert second.strength == 2


def test_peck_weak_vulnerable_rounding_and_side_end_restore():
    run = elite_run(max_hp=1000)
    run.apply(EndTurn())
    enemy = run.combat.enemies[0]
    enemy.apply_status("weak", 1)
    run.combat.player.apply_status("vulnerable", 1)
    assert enemy.intent.attack_damage == 3 and enemy.intent.attack_count == 3
    other = clone(run)
    for engine in (run, other):
        hp = engine.combat.player.hp
        engine.apply(EndTurn())
        assert hp - engine.combat.player.hp == 12  # floor(4 * .75 * 1.5) per hit.
        assert engine.combat.enemies[0].strength == 2
        assert engine.combat.enemies[0].statuses.get("weak") == 0
    assert saved(run) == saved(other)


def test_elite_move_boundaries_restore_owned_rng_and_power_without_reapplication():
    run = elite_run(max_hp=1000)
    for _ in range(8):
        other = clone(run)
        assert other.combat.rng is other.combat.player.deck.rng
        assert other.combat.enemies[0].rng is other.combat.rng
        assert other.combat.enemies[0].statuses.get("territorial") == 1
        before = saved(run)
        run.legal_actions()
        run.combat.enemies[0].to_observation()
        assert saved(run) == before
        run.apply(EndTurn())
        other.apply(EndTurn())
        assert saved(run) == saved(other)


@pytest.mark.parametrize("seed", range(8))
def test_elite_reward_amounts_guaranteed_relic_and_no_rerolls(seed):
    run = won_elite(seed)
    reward = run.state.pending
    assert 35 <= reward["gold"] <= 45
    assert len(reward["offers"]) == 3
    assert reward["relic"] in ("strawberry", "pear", "mango")
    assert reward["encounter_id"] == "overgrowth_byrdonis"
    assert ClaimRelic() in run.legal_actions()
    assert run.state.rng.request_count("reward_relic") == 1
    rng = run.state.rng.snapshot()
    other = clone(run)
    other.legal_actions()
    other.apply(ClaimRelic())
    assert other.state.rng.snapshot() == rng


@pytest.mark.parametrize("relic,amount", [("strawberry", 7), ("pear", 10), ("mango", 14)])
def test_relic_pickup_heals_exact_max_hp_gain_once_and_survives_removal(relic, amount):
    run = RunEngine(hp=30)
    item = add_relic(run.state, relic)
    assert (run.state.hp, run.state.max_hp) == (30 + amount, 80 + amount)
    before = saved(run)
    with pytest.raises(ValueError):
        add_relic(run.state, relic)
    assert saved(run) == before
    other = clone(run)
    assert (other.state.hp, other.state.max_hp) == (30 + amount, 80 + amount)
    remove_relic(other.state, item.instance_id)
    assert (other.state.hp, other.state.max_hp) == (30 + amount, 80 + amount)
    other.start_combat(encounter_id="overgrowth_nibbit")
    assert (other.combat.player.hp, other.combat.player.max_hp) == (30 + amount, 80 + amount)


@pytest.mark.parametrize("hp", [30, 80])
def test_claim_relic_can_precede_other_rewards_and_restore_keeps_gain_once(hp):
    run = won_elite()
    run.state.hp = hp
    relic = run.state.pending["relic"]
    amount = {"strawberry": 7, "pear": 10, "mango": 14}[relic]
    run.apply(ClaimRelic())
    assert (run.state.hp, run.state.max_hp) == (hp + amount, 80 + amount)
    other = clone(run)
    before = saved(other)
    with pytest.raises(ValueError):
        other.apply(ClaimRelic())
    assert saved(other) == before
    other.apply(ChooseRewardCard(None))
    other.apply(ClaimGold())
    other.apply(LeaveRewards())
    other.start_combat(encounter_id="overgrowth_nibbit")
    assert other.combat.player.max_hp == 80 + amount


def test_forfeit_relic_and_hallway_have_no_pickup_or_relic_rng():
    run = won_elite()
    run.apply(LeaveRewards())
    assert run.state.relics == [] and run.state.max_hp == 80
    run.start_combat(encounter_id="overgrowth_nibbit")
    run.combat.player.gain_strength(100)
    run.apply(PlayCard(run.combat.player.hand[0].instance_id, 0))
    assert 10 <= run.state.pending["gold"] <= 20
    assert run.state.pending["relic"] is None
    assert ClaimRelic() not in run.legal_actions()
    assert run.state.rng.request_count("reward_relic") == 1  # Earlier elite only.


def test_owned_relics_excluded_and_empty_pool_rejects_entry_atomically():
    graph = MapGraph((MapNode("elite", "elite", (), "overgrowth_byrdonis"),), "elite")
    run = RunEngine(config=RunConfig(), graph=graph, card_ids=("strike",))
    add_relic(run.state, "strawberry")
    add_relic(run.state, "mango")
    run.apply(ChooseNode("elite"))
    run.combat.player.gain_strength(100)
    run.apply(PlayCard(run.combat.player.hand[0].instance_id, 0))
    assert run.state.pending["relic"] == "pear"
    run.apply(ClaimRelic())
    run.apply(LeaveRewards())
    before = saved(run)
    with pytest.raises(ValueError, match="pool"):
        run.start_combat(encounter_id="overgrowth_byrdonis")
    assert saved(run) == before
    # Route selection itself must also roll back when its pool is depleted.
    fresh = RunEngine(config=RunConfig(), graph=graph)
    for relic in ("strawberry", "pear", "mango"):
        add_relic(fresh.state, relic)
    before = saved(fresh)
    with pytest.raises(ValueError, match="pool"):
        fresh.apply(ChooseNode("elite"))
    assert saved(fresh) == before


@pytest.mark.parametrize("raw", [False, True])
def test_registered_encounter_factory_preserves_elite_identity(raw):
    run = RunEngine(config=RunConfig())
    definition = ENCOUNTERS["overgrowth_byrdonis"]
    run.start_combat(encounter_factory=definition.factory if raw else definition)
    assert run.state.active_encounter_id == "overgrowth_byrdonis"


def test_unsupported_mid_combat_pickup_and_defeat_are_atomic_without_rewards():
    run = elite_run(hp=1)
    before = saved(run)
    with pytest.raises(ValueError):
        add_relic(run.state, "mango")
    assert saved(run) == before
    run.apply(EndTurn())
    assert run.state.phase is RunPhase.DEFEAT
    assert run.state.pending is None and run.state.active_encounter_id is None
    assert run.state.relics == [] and run.state.rng.request_count("reward_relic") == 0
    assert saved(clone(run)) == saved(run)


@pytest.mark.parametrize("field,value", [
    ("relic", None), ("relic", "burning_blood"), ("relic", "unknown"),
    ("relic_claimed", True), ("relic_claimed", 1), ("gold", 20), ("gold", 46),
    ("encounter_id", "unknown"), ("encounter_id", "overgrowth_nibbit"),
])
def test_malformed_elite_reward_restore_rejects_atomically(field, value):
    reject_restore(won_elite(), lambda s: s["state"]["pending"].__setitem__(field, value))


def test_claimed_relic_forgery_and_old_schema_rejected():
    run = won_elite()
    run.apply(ClaimRelic())
    reject_restore(run, lambda s: s["state"]["pending"].__setitem__("relic_claimed", False))
    reject_restore(run, lambda s: s.__setitem__("schema", "headless_run_state_v2"))


@pytest.mark.parametrize("value", [[], "unknown", ""])
def test_malformed_active_encounter_rejected(value):
    reject_restore(elite_run(), lambda s: s["state"].__setitem__("active_encounter_id", value))


def test_encounter_graph_kind_and_active_identity_must_match():
    graph = MapGraph((MapNode("elite", "elite", (), "overgrowth_byrdonis"),), "elite")
    run = RunEngine(config=RunConfig(), graph=graph)
    run.apply(ChooseNode("elite"))
    reject_restore(run, lambda s: s["state"].__setitem__("active_encounter_id", "overgrowth_nibbit"))
    reject_restore(run, lambda s: s["graph"]["nodes"][0].__setitem__("kind", "combat"))


@pytest.mark.parametrize("rest_choice", ["rest", "smith"])
def test_authored_elite_route_natural_victory_every_command_restores(rest_choice):
    run, trace = play_slice(seed=2, route="overgrowth", path="right",
                            rest_choice=rest_choice, verify_restore=True)
    assert run.state.phase is RunPhase.SLICE_COMPLETE and run.state.combats_completed == 4
    assert "byrdonis" in run.state.visited_nodes
    assert len(run.state.relics) == 2 and run.state.max_hp > 80
    assert 164 <= run.state.gold <= 204
    assert sum(t["action"] == "ClaimRelic" for t in trace) == 1


@pytest.mark.parametrize("missing_config", [False, True])
def test_active_elite_restore_rejects_unusable_reward_pool(missing_config):
    run = RunEngine(config=RunConfig())
    add_relic(run.state, "strawberry")
    run.start_combat(encounter_id="overgrowth_byrdonis")
    def corrupt(snapshot):
        if missing_config:
            snapshot["state"]["config"] = None
        else:
            snapshot["state"]["config"]["reward_relics"] = ["strawberry"]
    reject_restore(run, corrupt)
