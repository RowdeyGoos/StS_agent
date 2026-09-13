"""Pinned colorless inventory and resumable cross-card game behavior."""

import json
from copy import deepcopy
from pathlib import Path
import pytest
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.cards.pools import COLORLESS_CARDS, REWARD_CARDS
from game.headless.core.actions import PlayCard, ChooseCombatCard, ConfirmCombatSelection, EndTurn
from game.headless.core.combat import CombatEngine
from game.headless.powers.ironclad import apply_power
from game.headless.run.engine import RunEngine
from tests.headless.test_ironclad_complete import fight, play, saved


def settle(c, *, choose=True):
    for _ in range(100):
        if c.player.pending_play is None and c.player.rules.selection is None:
            return
        clone = CombatEngine()
        clone.restore(saved(c))
        assert saved(clone) == saved(c)
        actions = c.legal_actions()
        s = c.player.rules.selection
        confirm = ConfirmCombatSelection()
        action = confirm if confirm in actions and (not choose or s["selected"]) else actions[0]
        c.apply(action)
        clone.apply(action)
        assert saved(clone) == saved(c)
    pytest.fail("Selection did not terminate")


def test_native_inventory():
    data = json.loads(
        Path(__file__).with_name("fixtures").joinpath("colorless_native_inventory.json").read_text()
    )
    rows = [r for r in data["cards"] if r["definition_id"] not in data["excluded_multiplayer"]]
    assert len(rows) == len(COLORLESS_CARDS) == 53
    assert set(COLORLESS_CARDS) == {r["definition_id"] for r in rows}
    assert not set(COLORLESS_CARDS) & set(REWARD_CARDS)
    for row in rows:
        d = DEFAULT_CARDS.definition(row["definition_id"])
        sp = d.levels[0]
        assert (sp.cost, sp.kind, d.rarity, sp.uses_target) == (
            row["cost"],
            row["kind"],
            row["rarity"],
            row["uses_target"],
        )
        assert len(d.levels) == 2


@pytest.mark.parametrize("identity", COLORLESS_CARDS)
@pytest.mark.parametrize("level", [0, 1])
def test_every_card_play_and_three_turn_json_continuation(identity, level):
    c = fight(
        identity,
        "defend",
        "strike",
        draw=("strike", "defend", "bloodletting", "feed", "pommel_strike"),
        discard=("strike", "defend", "bash"),
        level=level,
        hp=10000,
    )
    play(c, "card.0")
    settle(c)
    for _ in range(3):
        clone = CombatEngine()
        clone.restore(saved(c))
        assert saved(clone) == saved(c)
        c.apply(EndTurn())
        clone.apply(EndTurn())
        assert saved(clone) == saved(c)
        settle(c)


def test_purity_optional_multiple_exact_selection_and_rejection():
    c = fight("purity", "strike", "defend", "bash")
    play(c, "card.0")
    before = saved(c)
    with pytest.raises(ValueError):
        c.apply(ChooseCombatCard("foreign"))
    assert saved(c) == before
    c.apply(ChooseCombatCard("card.1"))
    c.apply(ChooseCombatCard("card.2"))
    c.apply(ChooseCombatCard("card.1"))
    assert c.player.rules.selection["selected"] == ["card.2"]
    c.apply(ConfirmCombatSelection())
    assert {x.instance_id for x in c.player.deck.exhaust_pile} == {"card.0", "card.2"}
    c = fight("purity", "strike")
    play(c, "card.0")
    c.apply(ConfirmCombatSelection())
    assert c.player.hand[0].definition.definition_id == "strike"


@pytest.mark.parametrize("identity", ["discovery", "splash"])
def test_offers_skip_or_select_without_rng_on_reads(identity):
    c = fight(identity)
    play(c, "card.0")
    assert len(c.player.deck.offered) == 3
    assert len({x.definition.definition_id for x in c.player.deck.offered}) == 3
    state = saved(c)
    for _ in range(3):
        c.legal_actions()
    assert saved(c) == state
    c.apply(ConfirmCombatSelection())
    assert not c.player.deck.offered and not c.player.hand
    c.restore(state)
    chosen = c.player.deck.offered[0].instance_id
    c.apply(ChooseCombatCard(chosen))
    c.apply(ConfirmCombatSelection())
    assert c.player.card_cost(c.player.hand[0]) == 0
    assert not c.player.deck.offered


def test_hidden_gem_replays_x_cards_and_drum_exhaust():
    c = fight("hidden_gem", draw=("cascade",))
    play(c, "card.0")
    assert c.player.deck.draw_pile[0].combat_state.replay_count == 2
    c = fight("hidden_gem", "true_grit", draw=("drum_of_battle",))
    play(c, "card.0")
    c.player.draw_cards(1)
    energy = c.player.energy
    play(c, "card.1")
    assert c.player.energy == energy - 1 + 6
    c = fight("hidden_gem", draw=("strike",))
    play(c, "card.0")
    c.player.draw_cards(1)
    play(c, "card.1")
    assert c.enemies[0].hp == 982
    assert len(c.player.deck.discard_pile) == 2


@pytest.mark.parametrize("identity", ["bolas", "thrumming_hatchet"])
def test_return_from_exhaust_exact_instance_only_next_turn(identity):
    c = fight(identity, identity)
    from game.headless.core.resolution import start_play, drain

    start_play(c.player, c.player.hand[0], c.enemies[0], auto=True, force_exhaust=True)
    drain(c.player)
    c.apply(EndTurn())
    assert [x.instance_id for x in c.player.hand] == ["card.0"]
    c.apply(EndTurn())
    assert not c.player.hand


def test_stratagem_interrupts_shuffle_before_draw_and_automation_counts_real_draws():
    c = fight("stratagem", "automation", "finesse", discard=("strike", "bash", "defend"))
    play(c, "card.0")
    play(c, "card.1")
    play(c, "card.2")
    assert c.player.rules.selection["source"] == "stratagem"
    assert not c.player.hand
    key = next(k for k in c.player.rules.powers if k.startswith("automation:"))
    assert c.player.rules.auxiliaries[key] == 10
    settle(c)
    assert len(c.player.hand) == 2
    assert c.player.rules.auxiliaries[key] == 9


def test_separate_panache_and_bomb_instances():
    c = fight("panache", "panache", "finesse", "production", "ultimate_defend", "prolong", "prowess")
    play(c, "card.0")
    play(c, "card.1")
    for i in range(2, 6):
        play(c, f"card.{i}")
    assert c.enemies[0].hp == 990
    play(c, "card.6")
    assert c.enemies[0].hp == 980
    c = fight("the_bomb", "the_bomb")
    play(c, "card.0")
    c.apply(EndTurn())
    # Recover the second copy discarded at the previous end of turn.
    other = next(x for x in c.player.deck.discard_pile if x.instance_id == "card.1")
    c.player.deck.discard_pile.remove(other)
    c.player.hand.append(other)
    play(c, "card.1")
    c.apply(EndTurn())
    c.enemies[0].block = 0
    c.apply(EndTurn())
    assert c.enemies[0].hp == 960
    c.apply(EndTurn())
    assert c.enemies[0].hp == 920


def test_fisticuffs_and_omnislice_damage_result_includes_block_and_overkill():
    c = fight("fisticuffs")
    c.enemies[0].block = 50
    play(c, "card.0")
    assert c.player.block == 7
    c = fight("omnislice")
    from game.headless.monsters.overgrowth import SimpleEnemy

    second = SimpleEnemy(max_hp=100)
    second.combat_player = c.player
    c.enemies.append(second)
    c.enemies[0].hp = 1
    c.enemies[0].apply_status("vulnerable", 2)
    second.apply_status("vulnerable", 2)
    c.player.strength = 2
    play(c, "card.0")
    assert second.hp == 85  # 15 on primary, no second strength/vulnerable multiplier.


def test_dark_shackles_artifact_and_expiration():
    c = fight("dark_shackles")
    c.enemies[0].apply_status("artifact", 1)
    play(c, "card.0")
    assert c.enemies[0].statuses.get("dark_shackles") == 0
    c = fight("dark_shackles")
    play(c, "card.0")
    before = c.player.hp
    c.apply(EndTurn())
    assert c.player.hp == before
    assert c.enemies[0].statuses.get("dark_shackles") == 0


def test_retain_defend_vigor_and_gambit():
    c = fight("equilibrium", "ultimate_defend", "strike")
    play(c, "card.0")
    c.apply(EndTurn())
    assert len(c.player.hand) == 2
    apply_power(c.player, "fasten", 4)
    apply_power(c.player, "dexterity", 2)
    play(c, "card.1")
    assert c.player.block == 17
    apply_power(c.player, "vigor", 4)
    play(c, "card.2")
    assert c.enemies[0].hp == 990
    c = fight("the_gambit")
    play(c, "card.0")
    c.player.take_damage(2, is_attack=False)
    assert c.player.is_alive
    c.player.take_damage(60)
    assert not c.player.is_alive


def test_nostalgia_and_gold_axe_history():
    c = fight("nostalgia", "strike", "gold_axe")
    play(c, "card.0")
    play(c, "card.1")
    assert c.player.deck.draw_pile[-1].instance_id == "card.1"
    play(c, "card.2")
    assert c.enemies[0].hp == 992
    assert c.player.deck.discard_pile[-1].instance_id == "card.2"


def test_run_generated_loot_survives_victory_and_snapshot():
    run = RunEngine(card_ids=("alchemize", "hand_of_greed"))
    c = run.start_combat(cards_per_turn=2, energy_per_turn=10)
    alchemy = next(x for x in c.player.hand if x.definition.definition_id == "alchemize")
    run.apply(PlayCard(alchemy.instance_id))
    assert sum(x is not None for x in run.state.potions) == 1
    clone = RunEngine()
    clone.restore(json.loads(json.dumps(run.snapshot())))
    assert clone.snapshot() == run.snapshot()
    greed = next(x for x in c.player.hand if x.definition.definition_id == "hand_of_greed")
    c.enemies[0].hp = 1
    run.apply(PlayCard(greed.instance_id, 0))
    assert run.state.gold == 20
    assert sum(x is not None for x in run.state.potions) == 1


def test_alchemize_full_inventory_advances_only_potion_rng():
    c = fight("alchemize")
    c.player.rules.potion_slots = 0
    before = c.player.deck.potion_rng.getstate()
    generation = c.player.deck.generation_rng.getstate()
    play(c, "card.0")
    assert c.player.deck.potion_rng.getstate() != before
    assert c.player.deck.generation_rng.getstate() == generation
    assert not c.player.rules.potions_generated


@pytest.mark.parametrize("mutation", ["foreign", "bounds", "operation", "source", "timer"])
def test_malformed_pending_snapshot_rejected_atomically(mutation):
    c = fight("purity", "strike", "defend")
    apply_power(c.player, "automation", 1)
    play(c, "card.0")
    before = saved(c)
    broken = deepcopy(before)
    r = broken["player"]["rules"]
    s = r["selection"]
    if mutation == "foreign":
        s["candidates"].append("alien")
    if mutation == "bounds":
        s["maximum"] = 10
    if mutation == "operation":
        s["operation"] = "transform"
    if mutation == "source":
        s["source"] = "stratagem"
    if mutation == "timer":
        r["auxiliaries"]["automation:0"] = 0
    with pytest.raises(ValueError):
        c.restore(broken)
    assert saved(c) == before


def test_mayhem_runs_after_hand_draw_and_start_power_choices():
    c = fight(draw=("bash", "strike", "defend"))
    c.cards_per_turn = 1
    apply_power(c.player, "mayhem", 1)
    apply_power(c.player, "entropy", 1)
    # One hand card transforms automatically before Mayhem plays Strike.
    c.apply(EndTurn())
    assert c.enemies[0].hp == 994
    assert len(c.player.hand) == 1
    assert c.player.hand[0].definition.definition_id != "defend"
    assert c.player.deck.draw_pile[0].definition.definition_id == "bash"


def test_panache_rage_juggernaut_preserve_listener_order():
    from game.headless.monsters.overgrowth import SimpleEnemy

    c = fight("panache", "strike")
    c.enemies[0].hp = 5
    other = SimpleEnemy(max_hp=100)
    other.combat_player = c.player
    c.enemies.append(other)
    play(c, "card.0")
    key = next(k for k in c.player.rules.powers if k.startswith("panache:"))
    c.player.rules.auxiliaries[key] = 1
    apply_power(c.player, "rage", 3)
    apply_power(c.player, "juggernaut", 6)
    c.player.deck.target_rng.seed(1)
    c.apply(PlayCard("card.1", 1))
    assert other.hp == 78  # Strike6, Panache10, then Juggernaut6 on sole survivor.


def test_entropy_replacements_preserve_categories_and_clear_combat_modifiers():
    from game.headless.cards.colorless_effects import transform

    for identity, category in [
        ("wound", "status"),
        ("clumsy", "curse"),
        ("break", "colorless"),
        ("strike", "ironclad"),
    ]:
        c = fight(identity)
        card = c.player.hand[0]
        card.combat_state.replay_count = 3
        card.combat_state.extra_damage = 20
        old_id = card.instance_id
        transform(c.player, card)
        replacement = c.player.hand[0]
        assert replacement.instance_id != old_id
        assert replacement.definition.definition_id != identity
        assert not replacement.combat_state.replay_count and not replacement.combat_state.extra_damage
        assert replacement.upgrade_level == 0
        if category in ("status", "curse"):
            assert replacement.spec.kind == category
        else:
            assert replacement.definition.pool == category


def test_entropy_mandatory_count_cannot_be_lowered_in_snapshot():
    c = fight("strike", "defend", "bash")
    apply_power(c.player, "entropy", 2)
    from game.headless.powers.colorless import start_power

    start_power(c.player, "entropy")
    before = saved(c)
    broken = deepcopy(before)
    selection = broken["player"]["rules"]["selection"]
    selection["candidates"] = selection["candidates"][:1]
    selection["minimum"] = selection["maximum"] = 1
    with pytest.raises(ValueError):
        c.restore(broken)
    assert saved(c) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("potion_slots", 1),
        ("potion_pool", ["block_potion"]),
        ("gold_gained", 5),
        ("potions_generated", ["fire_potion"]),
    ],
)
def test_run_snapshot_binds_combat_loot_to_inventory(field, value):
    from game.headless.run.inventory import add_potion

    run = RunEngine(card_ids=("alchemize",))
    for _ in range(3):
        add_potion(run.state, "fire_potion")
    run.start_combat()
    before = json.loads(json.dumps(run.snapshot()))
    broken = deepcopy(before)
    broken["combat"]["player"]["rules"][field] = value
    with pytest.raises(ValueError):
        run.restore(broken)
    assert json.loads(json.dumps(run.snapshot())) == before


def test_all_colorless_cards_are_acquirable_in_their_merchant_rarity_slots():
    from game.headless.shops.catalog import SLOTS

    colorless = [s for s in SLOTS if s.kind == "card" and not s.sale_eligible]
    assert len(colorless) == 2
    assert {i for s in colorless for i, _ in s.items} == set(COLORLESS_CARDS)
    for slot, rarity, price in zip(colorless, ("uncommon", "rare"), (86, 172)):
        assert all(DEFAULT_CARDS.definition(i).rarity == rarity and cost == price for i, cost in slot.items)


def test_discovery_free_cost_expires_after_play_or_turn():
    c = fight("strike", "defend")
    c.player.hand[0].combat_state.free_until_played = True
    c.player.hand[1].combat_state.free_until_played = True
    energy = c.player.energy
    play(c, "card.0")
    assert c.player.energy == energy
    assert not c.player.deck.discard_pile[-1].combat_state.free_until_played
    c.apply(EndTurn())
    assert not any(x.combat_state.free_until_played for x in c.player.deck.all_cards())


def test_retain_and_ethereal_exhaust_still_take_precedence():
    c = fight("equilibrium", "dazed", "restlessness")
    play(c, "card.0")
    c.apply(EndTurn())
    assert [x.definition.definition_id for x in c.player.hand] == ["restlessness"]
    assert [x.definition.definition_id for x in c.player.deck.exhaust_pile] == ["dazed"]


def test_panic_button_blocks_card_block_but_not_unpowered_gains():
    c = fight("panic_button", "ultimate_defend")
    play(c, "card.0")
    play(c, "card.1")
    assert c.player.block == 30
    c.player.gain_block(5)
    assert c.player.block == 35
    c.apply(EndTurn())
    assert c.player.rules.powers["no_block"] == 1
    c.apply(EndTurn())
    assert not c.player.rules.powers.get("no_block")


def test_rend_counts_debuff_kinds_not_stacks_and_excludes_temporary_strength_loss():
    c = fight("rend")
    e = c.enemies[0]
    e.apply_status("weak", 20)
    e.apply_status("vulnerable", 2)
    e.apply_status("dark_shackles", 9)
    e.apply_status("mangle", 10)
    play(c, "card.0")
    assert e.hp == 963  # floor((15 + 2*5)*1.5)


def test_automation_instances_keep_separate_draw_counters():
    c = fight("automation", "automation", draw=("strike",) * 12)
    play(c, "card.0")
    c.player.draw_cards(2)
    play(c, "card.1")
    for _ in range(8):
        c.player.draw_cards(1)
    assert [c.player.rules.auxiliaries[k] for k in c.player.rules.powers if k.startswith("automation:")] == [
        10,
        2,
    ]


def test_discovery_does_not_discount_negative_canonical_x_cost(monkeypatch):
    c = fight("discovery")
    offers = [DEFAULT_CARDS.definition(i) for i in ("cascade", "whirlwind", "anger")]
    monkeypatch.setattr(c.player.deck.generation_rng, "sample", lambda choices, count: offers)
    play(c, "card.0")
    selected = next(x for x in c.player.deck.offered if x.definition.definition_id == "cascade")
    c.apply(ChooseCombatCard(selected.instance_id))
    c.apply(ConfirmCombatSelection())
    assert not selected.combat_state.free_until_played
    assert c.player.card_cost(selected) == c.player.energy


def test_discovery_modifier_copied_by_play_effect_before_original_cleanup():
    c = fight("anger")
    c.player.hand[0].combat_state.free_until_played = True
    play(c, "card.0")
    copies = c.player.deck.discard_pile
    assert copies[0].instance_id != "card.0" and copies[0].combat_state.free_until_played
    assert copies[1].instance_id == "card.0" and not copies[1].combat_state.free_until_played


def test_zero_damage_fisticuffs_can_gain_dexterity_block():
    c = fight("fisticuffs")
    c.player.strength = -7
    apply_power(c.player, "dexterity", 2)
    play(c, "card.0")
    assert c.player.block == 2


def test_prolong_with_barricade_still_receives_after_block_cleared_hook():
    c = fight("prolong")
    apply_power(c.player, "barricade", 1)
    c.player.block = 20
    play(c, "card.0")
    c.apply(EndTurn())
    assert c.player.block == 34  # 20 - SimpleEnemy's6 + saved20.
    assert "block_next_turn" not in c.player.rules.powers


def test_pillage_completes_automation_hook_before_next_draw_shuffle():
    c = fight("pillage", draw=("strike",), discard=("defend", "bash"))
    apply_power(c.player, "automation", 1)
    apply_power(c.player, "stratagem", 1)
    c.player.rules.auxiliaries["automation:0"] = 1
    energy = c.player.energy
    play(c, "card.0")
    assert c.player.rules.selection["source"] == "stratagem"
    assert c.player.rules.auxiliaries["automation:0"] == 10
    assert c.player.energy == energy  # cost1 followed by the tenth-draw reward1.
    settle(c)


def test_juggling_copy_of_bolas_does_not_inherit_original_play_history():
    c = fight("bolas")
    apply_power(c.player, "juggling", 1)
    c.player.rules.attacks_started = c.player.rules.attacks_finished = 2
    play(c, "card.0")
    assert len(c.player.hand) == 1
    assert not c.player.hand[0].combat_state.return_next_turn
    c.apply(EndTurn())
    assert [card.instance_id for card in c.player.hand] == ["card.0"]


@pytest.mark.parametrize("identity", ["whirlwind", "volley", "fiend_fire"])
def test_zero_hit_attack_command_consumes_vigor(identity):
    c = fight(identity)
    if identity != "fiend_fire":
        c.player.energy = 0
    apply_power(c.player, "vigor", 4)
    play(c, "card.0")
    assert not c.player.rules.powers.get("vigor")
    assert c.enemies[0].hp == 1000


def test_unmet_pacts_end_condition_does_not_consume_vigor():
    c = fight("pacts_end")
    apply_power(c.player, "vigor", 4)
    play(c, "card.0")
    assert c.player.rules.powers["vigor"] == 4
    assert c.enemies[0].hp == 1000
