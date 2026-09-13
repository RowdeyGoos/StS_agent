"""Native single-player inventory and cross-card rule/continuation regressions."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.cards.pools import IRONCLAD_CARDS, REWARD_CARDS, RARE_CARDS
from game.headless.core.actions import PlayCard, ChooseCombatCard, EndTurn
from game.headless.core.combat import CombatEngine
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.powers.ironclad import apply_power
from game.headless.run.engine import RunEngine


def saved(engine):
    return json.loads(json.dumps(engine.snapshot()))


def fight(*hand, draw=(), discard=(), exhaust=(), level=0, hp=1000):
    ids = (*hand, *draw, *discard, *exhaust)
    combat = CombatEngine(
        deck_factory=lambda: [
            DEFAULT_CARDS.create(c, upgrade_level=level if i == 0 else 0, instance_id=f"card.{i}")
            for i, c in enumerate(ids)
        ],
        cards_per_turn=0,
        enemy_factory=lambda: SimpleEnemy(max_hp=hp),
    )
    combat.reset()
    deck = combat.player.deck
    cards = {c.instance_id: c for c in deck.all_cards()}
    deck.draw_pile.clear()
    deck.hand.clear()
    offset = 0
    for names, pile in (
        (hand, deck.hand),
        (draw, deck.draw_pile),
        (discard, deck.discard_pile),
        (exhaust, deck.exhaust_pile),
    ):
        pile.extend(cards[f"card.{i}"] for i in range(offset, offset + len(names)))
        offset += len(names)
    combat.player.energy = 20
    return combat


def play(c, identity):
    card = next(x for x in c.player.hand if x.instance_id == identity)
    return c.apply(PlayCard(identity, 0 if card.spec.uses_target else None))


def settle(c):
    for _ in range(30):
        if c.player.pending_play is None:
            return
        snapshot = saved(c)
        clone = CombatEngine()
        clone.restore(snapshot)
        assert saved(clone) == snapshot
        action = c.legal_actions()[0]
        c.apply(action)
        clone.apply(action)
        assert saved(c) == saved(clone)
    pytest.fail("Choice continuation did not terminate")


def test_complete_single_player_pool_matches_native_constructor_inventory():
    source = json.loads(
        Path(__file__).with_name("fixtures").joinpath("ironclad_native_inventory.json").read_text()
    )
    excluded = set(source["excluded_multiplayer"])
    rows = [r for r in source["cards"] if r["definition_id"] not in excluded]
    assert len(rows) == len(IRONCLAD_CARDS) == 85
    assert set(IRONCLAD_CARDS) == {r["definition_id"] for r in rows}
    for row in rows:
        d = DEFAULT_CARDS.definition(row["definition_id"])
        sp = d.levels[0]
        assert len(d.levels) == 2
        assert (sp.cost, "skill" if sp.kind == "block" else sp.kind, sp.uses_target, d.rarity) == (
            row["cost"],
            row["kind"],
            row["uses_target"],
            row["rarity"],
        )
    assert len(REWARD_CARDS) == 80
    assert not set(REWARD_CARDS) & {"strike", "defend", "bash", "break", "corruption", "shockwave", *excluded}
    from game.headless.run.config import RunConfig
    from game.headless.events.transformation import TRANSFORM_POOL
    from game.headless.shops.catalog import SLOTS

    assert RunConfig().reward_cards == REWARD_CARDS == TRANSFORM_POOL
    assert RunConfig().boss_reward_cards == RARE_CARDS
    assert {i for slot in SLOTS if slot.kind == "card" and slot.sale_eligible for i, _ in slot.items} == set(REWARD_CARDS)


@pytest.mark.parametrize("identity", IRONCLAD_CARDS)
@pytest.mark.parametrize("level", [0, 1])
def test_every_card_and_upgrade_plays_and_roundtrips_through_turn_boundaries(identity, level):
    c = fight(
        identity,
        "strike",
        "defend",
        "strike",
        draw=("strike", "defend", "strike"),
        discard=("defend", "strike"),
        exhaust=("dazed", "slimed", "wound"),
        level=level,
    )
    play(c, "card.0")
    settle(c)
    for _ in range(2):
        snapshot = saved(c)
        clone = CombatEngine()
        clone.restore(snapshot)
        assert saved(clone) == snapshot
        assert c.player.deck.in_play == [] and c.player.rules.tasks == []
        if c.done:
            break
        c.apply(EndTurn())
        clone.apply(EndTurn())
        assert saved(c) == saved(clone)
        settle(c)
    assert len({x.instance_id for x in c.player.deck.all_cards()}) == len(c.player.deck.all_cards())


def test_havoc_nested_choice_resumes_parent_without_extra_energy_or_exhaust():
    c = fight("havoc", "strike", "defend", draw=("strike", "burning_pact"))
    play(c, "card.0")
    assert len(c.player.deck.in_play) == 2
    assert c.player.energy == 19
    settle(c)
    assert {x.definition.definition_id for x in c.player.deck.exhaust_pile} >= {"burning_pact"}
    assert [x.definition.definition_id for x in c.player.deck.discard_pile] == ["havoc"]


def test_cascade_resolves_result_pile_before_nested_corruption_and_skips_unplayable():
    c = fight("cascade", draw=("anger", "corruption", "wound"))
    c.player.energy = 3
    play(c, "card.0")
    assert c.player.rules.powers["corruption"] == 1
    assert c.enemies[0].hp == 994
    assert [x.definition.definition_id for x in c.player.deck.discard_pile] == [
        "wound",
        "anger",
        "anger",
        "cascade",
    ]
    assert c.player.energy == 0 and c.player.cards_played_this_turn == 3
    c = fight("havoc", draw=("wound",))
    apply_power(c.player, "feel_no_pain", 3)
    play(c, "card.0")
    assert c.player.block == 3 and c.player.cards_played_this_turn == 1
    assert [x.definition.definition_id for x in c.player.deck.exhaust_pile] == ["wound"]


def test_replay_has_one_payment_two_choices_and_per_play_free_attack_hooks():
    c = fight("headbutt", "strike", discard=("defend", "bash", "anger"))
    apply_power(c.player, "one_two_punch", 1)
    apply_power(c.player, "free_attack", 2)
    play(c, "card.0")
    assert c.player.pending_play is not None
    settle(c)
    assert c.enemies[0].hp == 982 and c.player.energy == 20
    assert c.player.rules.powers["free_attack"] == 0
    assert len(c.player.deck.draw_pile) == 2
    assert len(c.player.deck.discard_pile) == 2


@pytest.mark.parametrize("level,damage,gain", [(0, 10, 3), (1, 12, 4)])
def test_feed_fatal_increases_run_max_hp_and_survives_active_snapshot(level, damage, gain):
    run = RunEngine(card_ids=("feed", "defend"))
    if level:
        run.upgrade_card("run.card.0")
    c = run.start_combat(cards_per_turn=2)
    # A fatal first target while a second enemy keeps combat active.
    second = SimpleEnemy()
    second.combat_player = c.player
    c.enemies.append(second)
    c.enemies[0].hp = damage
    run.apply(PlayCard("run.card.0", 0))
    assert c.player.max_hp == 80 + gain and run.state.max_hp == 80
    clone = RunEngine()
    clone.restore(saved(run))
    assert saved(clone) == saved(run)
    second.hp = 0
    c.resolve_external_effect()
    run.finish_combat()
    assert run.state.max_hp == 80 + gain
    assert run.start_combat().player.max_hp == 80 + gain


def test_feed_does_not_farm_minions():
    c = fight("feed", hp=10)
    c.enemies[0].statuses.add("minion", 1)
    play(c, "card.0")
    assert c.player.max_hp == 80


def test_second_wind_exhausts_original_hand_only_and_orders_draws_and_blocks():
    c = fight("second_wind", "defend", "wound", "strike", draw=("defend", "defend"))
    apply_power(c.player, "dark_embrace", 1)
    apply_power(c.player, "feel_no_pain", 3)
    play(c, "card.0")
    assert c.player.block == 16
    assert len(c.player.hand) == 3
    assert [x.instance_id for x in c.player.deck.exhaust_pile] == ["card.1", "card.2"]


@pytest.mark.parametrize("draw_allowed", [False, True])
def test_ethereal_draw_respects_no_draw_listener_insertion_order(draw_allowed):
    c = fight("dazed", draw=("strike",))
    powers = ("no_draw", "dark_embrace") if draw_allowed else ("dark_embrace", "no_draw")
    for power in powers:
        apply_power(c.player, power, 1)
    c.player.end_turn()
    assert len(c.player.hand) == int(draw_allowed)
    assert "no_draw" not in c.player.rules.powers


def test_unmovable_groups_blocks_within_play_but_not_replayed_card():
    c = fight("second_wind", "defend", "wound")
    apply_power(c.player, "unmovable", 1)
    play(c, "card.0")
    assert c.player.block == 20
    c = fight("iron_wave")
    apply_power(c.player, "unmovable", 1)
    apply_power(c.player, "one_two_punch", 1)
    play(c, "card.0")
    assert c.player.block == 15
    c = fight("defend")
    apply_power(c.player, "unmovable", 1)
    c.player.gain_block(3)
    play(c, "card.0")
    assert c.player.block == 13


def test_rupture_strength_waits_for_hemokinesis_damage_then_applies():
    c = fight("hemokinesis")
    apply_power(c.player, "rupture", 2)
    apply_power(c.player, "inferno", 6)
    play(c, "card.0")
    assert c.player.hp == 78 and c.player.strength == 2
    assert c.enemies[0].hp == 980
    assert c.player.rules.hp_loss_events == 1


def test_runtime_damage_growth_and_clones_are_owned_and_reset_for_run():
    c = fight("rampage", "anger", "thrash", "bludgeon")
    play(c, "card.0")
    assert c.player.deck.discard_pile[0].combat_state.extra_damage == 5
    play(c, "card.1")
    assert len([x for x in c.player.deck.discard_pile if x.definition.definition_id == "anger"]) == 2
    play(c, "card.2")
    thrash = next(x for x in c.player.deck.discard_pile if x.definition.definition_id == "thrash")
    assert thrash.combat_state.extra_damage == 32
    clone = CombatEngine()
    clone.restore(saved(c))
    assert saved(c) == saved(clone)


def test_stoke_generated_upgrades_exclusions_and_rng_replay():
    for level in (0, 1):
        c = fight("stoke", "strike", "defend", "wound", level=level)
        before_shuffle = c.player.deck.rng.getstate()
        clone = CombatEngine()
        clone.restore(saved(c))
        play(c, "card.0")
        play(clone, "card.0")
        assert saved(c) == saved(clone)
        assert len(c.player.hand) == len(c.player.deck.exhaust_pile) == 3
        assert all(x.upgrade_level == level and x.definition.generate_in_combat for x in c.player.hand)
        assert all(x.definition.rarity in ("common", "uncommon", "rare") for x in c.player.hand)
        assert c.player.deck.rng.getstate() == before_shuffle


def test_primal_force_replaces_only_hand_attacks_with_fresh_rocks():
    c = fight("primal_force", "strike", "defend", "anger", level=1)
    play(c, "card.0")
    assert [x.definition.definition_id for x in c.player.hand] == ["giant_rock", "defend", "giant_rock"]
    assert [x.upgrade_level for x in c.player.hand] == [1, 0, 1]
    assert not {"card.1", "card.3"} & {x.instance_id for x in c.player.deck.all_cards()}


def test_howl_autoplays_only_from_exhaust_and_returns_to_discard():
    c = fight("howl_from_beyond", exhaust=("howl_from_beyond",))
    c.apply(EndTurn())
    assert c.enemies[0].hp == 984
    assert not c.player.deck.exhaust_pile
    assert len(c.player.deck.discard_pile) == 2


def test_stampede_headbutt_choice_resumes_enemy_phase_exactly_once():
    c = fight("headbutt", discard=("defend", "strike"))
    apply_power(c.player, "stampede", 1)
    c.apply(EndTurn())
    assert c.turn == 1 and c.player.rules.turn_ending and c.player.pending_play
    settle(c)
    assert c.turn == 2 and c.player.hp == 74 and c.enemies[0].hp == 991


def test_vicious_hellraiser_nested_draw_occurs_before_next_enemy_vulnerable():
    c = fight("shockwave", "defend", "strike", draw=("defend", "armaments", "pommel_strike"))
    second = SimpleEnemy(1000)
    second.combat_player = c.player
    c.enemies.append(second)
    apply_power(c.player, "vicious", 1)
    apply_power(c.player, "hellraiser", 1)
    play(c, "card.0")
    settle(c)
    assert c.player.cards_played_this_turn == 2
    assert all(e.statuses.get("vulnerable") == 3 for e in c.enemies)


@pytest.mark.parametrize(
    "alter",
    [
        lambda s: s["player"]["rules"]["tasks"].append(["finish", "card.0"]),
        lambda s: s["player"]["rules"]["tasks"].clear(),
        lambda s: s["player"]["rules"]["tasks"].insert(0, ["exhaust", "card.0"]),
        lambda s: s["player"]["rules"]["tasks"][0].__setitem__(1, "missing"),
        lambda s: s["player"]["rules"]["plays"]["card.0"].__setitem__("remaining", 0),
        lambda s: s["player"]["rules"]["plays"]["card.0"].__setitem__("destination", "powers"),
        lambda s: s["player"]["rules"]["powers"].__setitem__("fake_power", 1),
        lambda s: s["player"]["rules"]["plays"]["card.0"].__setitem__("effect_index", 1),
    ],
)
def test_corrupt_continuation_restore_is_atomic(alter):
    c = fight("burning_pact", "strike", "defend")
    play(c, "card.0")
    before = saved(c)
    bad = deepcopy(before)
    alter(bad)
    with pytest.raises(ValueError):
        c.restore(bad)
    assert saved(c) == before


def test_full_reward_pool_can_acquire_every_card_with_normal_three_card_offers():
    from game.headless.run.config import RunConfig
    from game.headless.run.rewards import begin_combat_rewards
    from game.headless.run.actions import ChooseRewardCard

    unseen = set(REWARD_CARDS)
    for seed in range(300):
        run = RunEngine(seed=seed, config=RunConfig())
        begin_combat_rewards(run.state, run.cards)
        for identity in set(run.state.pending["offers"]) & unseen:
            clone = RunEngine()
            clone.restore(saved(run))
            card = clone.apply(ChooseRewardCard(identity))
            assert card.definition.definition_id == identity and card.instance_id == "run.card.10"
            unseen.remove(identity)
        if not unseen:
            break
    assert not unseen


def test_barricade_pyre_and_demon_form_persist_while_temporary_powers_expire():
    c = fight("setup_strike")
    for name, amount in (("barricade", 1), ("pyre", 2), ("demon_form", 3), ("rage", 3)):
        apply_power(c.player, name, amount)
    play(c, "card.0")
    assert c.player.block == 3 and c.player.strength == 2
    c.player.block = 20
    c.apply(EndTurn())
    assert c.player.block == 14 and c.player.energy == 5 and c.player.strength == 3
    assert "rage" not in c.player.rules.powers and "setup_strike" not in c.player.rules.powers


def test_stomp_reduces_in_hand_and_discard_then_resets():
    c = fight("anger", "twin_strike", "stomp", discard=("stomp",))
    apply_power(c.player, "one_two_punch", 1)
    play(c, "card.0")
    play(c, "card.1")
    stomps = [x for x in c.player.deck.all_cards() if x.definition.definition_id == "stomp"]
    assert all(c.player.card_cost(x) == 0 for x in stomps)
    c.apply(EndTurn())
    assert all(c.player.card_cost(x) == 3 for x in stomps)


def test_juggling_counts_attacks_before_acquisition_and_only_clones_third():
    c = fight("strike", "juggling", "anger", "rampage")
    play(c, "card.0")
    play(c, "card.1")
    play(c, "card.2")
    play(c, "card.3")
    assert len(c.player.hand) == 1
    clone = c.player.hand[0]
    assert clone.definition.definition_id == "rampage" and clone.combat_state.extra_damage == 5
    play(c, clone.instance_id)
    assert c.player.hand == []


def test_flame_barrier_interrupts_dead_attackers_multi_hit_and_mangle_expires():
    from game.headless.monsters.base import Intent

    c = fight("flame_barrier")
    enemy = c.enemies[0]
    enemy.hp = 4
    enemy.INTENT_CYCLE = (Intent(kind="attack", value=9, attack_damage=3, attack_count=3),)
    play(c, "card.0")
    c.apply(EndTurn())
    assert c.done and c.player.block == 9 and c.player.hp == 80
    c = fight("mangle")
    play(c, "card.0")
    c.apply(EndTurn())
    assert c.player.hp == 80 and c.enemies[0].statuses.get("mangle") == 0


def test_colossus_and_cruelty_compose_with_vulnerable_before_rounding():
    c = fight("strike")
    c.enemies[0].apply_status("vulnerable", 2)
    apply_power(c.player, "colossus", 1)
    apply_power(c.player, "cruelty", 25)
    play(c, "card.0")
    assert c.enemies[0].hp == 990  # floor(6 * 1.75)
    c.apply(EndTurn())
    assert c.player.hp == 77 and c.player.rules.powers["colossus"] == 0


def test_vicious_only_positive_successful_vulnerability_applications_draw():
    c = fight("thunderclap", draw=("defend", "defend"))
    apply_power(c.player, "vicious", 2)
    c.enemies[0].statuses.add("artifact", 1)
    play(c, "card.0")
    assert not c.player.hand
    c.enemies[0].apply_status("vulnerable", 0, source=c.player)
    assert not c.player.hand
    c.enemies[0].apply_status("vulnerable", 4, source=c.player)
    assert len(c.player.hand) == 2


def test_battle_trance_blocks_card_draw_but_next_turn_hand_draw_is_normal():
    c = fight("battle_trance", "pommel_strike", draw=("defend",) * 5)
    play(c, "card.0")
    assert len(c.player.hand) == 4
    play(c, "card.1")
    assert len(c.player.hand) == 3 and len(c.player.deck.draw_pile) == 2
    c.cards_per_turn = 5
    c.apply(EndTurn())
    assert len(c.player.hand) == 5


def test_infernal_blade_free_x_attack_uses_energy_without_spending_it():
    c = fight("whirlwind", level=1)
    c.player.hand[0].combat_state.free_this_turn = True
    c.player.energy = 3
    play(c, "card.0")
    assert c.enemies[0].hp == 976 and c.player.energy == 3


def test_combat_clone_owns_rule_state_generated_card_values_and_rng():
    from game.analysis.bruteforce import (
        clone_combat_env,
        _combat_state_key,
        _RngStateRegistry,
        _CardStateRegistry,
    )
    from game.simulation.core import CombatEnv

    env = CombatEnv()
    env.reset()
    apply_power(env.player, "pyre", 1)
    clone = clone_combat_env(env)
    clone.player.rules.powers["pyre"] = 9
    clone.player.deck.hand[0].combat_state.extra_damage = 8
    assert env.player.rules.powers["pyre"] == 1
    assert env.player.deck.hand[0].combat_state.extra_damage == 0
    assert clone.player.deck.owner is clone.player
    rngs, cards = _RngStateRegistry(), _CardStateRegistry()
    before = _combat_state_key(env, rngs, cards)
    clone.player.deck.generation_rng.random()
    assert _combat_state_key(env, rngs, cards) == before
    env.player.deck.generation_rng.random()
    assert _combat_state_key(env, rngs, cards) != before


def test_lethal_damage_does_not_trigger_flame_barrier_retaliation():
    c = fight("defend", hp=4)
    c.player.hp = 1
    apply_power(c.player, "flame_barrier", 4)
    c.apply(EndTurn())
    assert c.winner == "enemy" and c.enemies[0].hp == 4


def test_search_key_preserves_power_hook_order():
    from game.analysis.bruteforce import _combat_state_key, _RngStateRegistry, _CardStateRegistry
    from game.simulation.core import CombatEnv

    env = CombatEnv()
    env.reset()
    apply_power(env.player, "no_draw", 1)
    apply_power(env.player, "dark_embrace", 1)
    rngs, cards = _RngStateRegistry(), _CardStateRegistry()
    first = _combat_state_key(env, rngs, cards)
    env.player.rules.powers = dict(reversed(tuple(env.player.rules.powers.items())))
    assert _combat_state_key(env, rngs, cards) != first


@pytest.mark.parametrize("count,expected", [(1, 5), (7, 7), (12, 10)])
def test_innate_opening_draw_expands_to_card_count_with_hand_cap(count, expected):
    cards = [DEFAULT_CARDS.create("aggression", upgrade_level=1) for _ in range(count)]
    cards += [DEFAULT_CARDS.create("strike") for _ in range(10)]
    c = CombatEngine(deck_factory=lambda: cards)
    c.reset()
    assert len(c.player.hand) == expected
    assert sum(x.spec.innate for x in c.player.hand) == min(count, 10)


def test_generated_cards_use_supplied_catalog_with_order_independent_sampling():
    from game.headless.cards.catalog import CardCatalog

    definitions = [DEFAULT_CARDS.definition(c) for c in ("stoke", "strike", "anger")]
    results = []
    for rows in (definitions, list(reversed(definitions))):
        catalog = CardCatalog(rows)
        c = CombatEngine(
            cards=catalog,
            cards_per_turn=3,
            deck_factory=lambda: [
                catalog.create("stoke", instance_id="a"),
                catalog.create("strike", instance_id="b"),
                catalog.create("strike", instance_id="c"),
            ],
        )
        c.reset()
        play(c, "a")
        assert all(x.definition.definition_id in ("anger", "stoke") for x in c.player.hand)
        snapshot = saved(c)
        clone = CombatEngine(cards=catalog)
        clone.restore(snapshot)
        assert saved(clone) == snapshot
        results.append(snapshot)
    assert results[0] == results[1]


def test_legacy_isolated_effect_targets_are_scoped_to_each_call():
    from random import Random
    from game.headless.core.player import Player
    from game.headless.core.deck import Deck

    p = Player(Deck([], Random(0)))
    first, second = SimpleEnemy(), SimpleEnemy()
    for target in (first, second):
        DEFAULT_CARDS.create("strike").play(p, target)
        assert target.hp == 34 and p.combat_enemies is None
        assert p.deck.in_play == [] and p.rules.plays == {} and p.rules.tasks == []


def test_legacy_player_rejects_foreign_target_before_mutating_state():
    c = fight("strike")
    before = saved(c)
    with pytest.raises(ValueError):
        c.player.play_card(0, SimpleEnemy())
    assert saved(c) == before
