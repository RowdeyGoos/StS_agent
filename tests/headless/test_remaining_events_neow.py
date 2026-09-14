"""Pinned solo Act 1 events, Neow generation, and exact private continuation."""

import json
from copy import deepcopy
import pytest
from game.headless.run.engine import RunEngine
from game.headless.run import events
from game.headless.run.actions import (
    ChooseEventOption,
    ChooseEventCard,
    LeaveEvent,
    ChooseAncientRelic,
    ChooseRelicCard,
    ConfirmRelicSelection,
    ChooseRelicReward,
    UsePotion,
    DiscardPotion,
    ChooseNode,
)
from game.headless.run.inventory import add_potion, add_relic
from game.headless.events.act1_content import DEFINITIONS
from game.headless.events.catalog import EVENTS
from game.headless.run.ancient import PROFILE, generate, EXCLUSIONS, CURSES
from game.headless.core.native_service import NativeRandomService as GameRandomService
from game.headless.core.actions import PlayCard, EndTurn


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def clone(run):
    other = RunEngine()
    other.restore(saved(run))
    assert saved(other) == saved(run)
    assert other.legal_actions() == run.legal_actions()
    return other


def step(run, action):
    other = clone(run)
    run.apply(action)
    other.apply(action)
    assert saved(other) == saved(run)
    clone(run)


def start(name, *, seed=11, hp=40, gold=200, relics=(), potions=("fire_potion", "blood_potion")):
    run = RunEngine(seed=seed, hp=hp, gold=gold)
    for relic in relics:
        add_relic(run.state, relic, cards=run.cards)
    for potion in potions:
        add_potion(run.state, potion)
    events.begin(run.state, name, cards=run.cards)
    return run


def option(run, name):
    return ChooseEventOption(run.state.pending["event_instance_id"], name)


def settle(run):
    for _ in range(100):
        clone(run)
        actions = run.legal_actions()
        if not actions or any(isinstance(a, LeaveEvent) for a in actions):
            return
        if run.state.relic_work:
            work = run.state.relic_work[0]
            action = next((a for a in actions if isinstance(a, ConfirmRelicSelection)), None)
            if action is None:
                action = next(
                    (
                        a
                        for a in actions
                        if isinstance(a, ChooseRelicCard) and a.instance_id not in work.get("selected", [])
                    ),
                    None,
                )
            if action is None:
                action = next(a for a in actions if isinstance(a, ChooseRelicReward) and a.index is not None)
        else:
            action = next(a for a in actions if isinstance(a, (ChooseEventOption, ChooseEventCard)))
        step(run, action)
    pytest.fail("Continuation did not settle")


BRANCHES = [
    (d.definition_id, n)
    for d in DEFINITIONS
    for n, _ in d.branches
    if n not in ("read_entire_book", "skip_book")
] + [("the_future_of_potions", "trade_0"), ("the_future_of_potions", "trade_1")]


@pytest.mark.parametrize("name,choice", BRANCHES)
def test_every_act1_branch_continues_exactly(name, choice):
    run = start(name)
    step(run, option(run, choice))
    settle(run)
    assert run.state.pending["stage"] == "resolved"
    step(run, LeaveEvent(run.state.pending["event_instance_id"]))
    assert run.state.pending is None


def test_full_native_act1_event_inventory():
    import re
    from pathlib import Path
    inventory = json.loads((Path(__file__).parents[1] / "fixtures/headless_act1_event_scope.json").read_text())
    names = inventory["overgrowth_events"] + inventory["shared_act1_events"]
    assert set(EVENTS) == {re.sub(r"(?<!^)(?=[A-Z])", "_", n).lower() for n in names}
    assert len(EVENTS) == 21
    run = RunEngine.ironclad_act1()
    assert set(run.state.config.event_pool) == set(EVENTS)
    clone(run)


@pytest.mark.parametrize("seed", range(30))
def test_neow_offers_two_positive_one_curse_and_exclusions(seed):
    offers = generate(GameRandomService(seed), ["kaleidoscope"])
    assert len(set(offers)) == 3 and offers[-1] in CURSES
    assert not set(offers[:2]) & set(CURSES)
    assert EXCLUSIONS.get(offers[-1]) not in offers[:2]
    if offers[-1] == "large_capsule":
        assert not set(offers) & {"small_capsule", "lava_rock"}
    run = RunEngine.ironclad_act1(seed=seed, ancient_profile=PROFILE)
    assert run.state.ancient_start.offers == offers
    clone(run)


def covering_seeds():
    found = {}
    for seed in range(300):
        for name in generate(GameRandomService(seed), ["kaleidoscope"]):
            found.setdefault(name, seed)
    return sorted(found.items())


@pytest.mark.parametrize("name,seed", covering_seeds())
def test_every_supported_neow_pickup_and_nested_choice(name, seed):
    run = RunEngine.ironclad_act1(seed=seed, ancient_profile=PROFILE)
    step(run, ChooseAncientRelic(name))
    from game.cli.headless_play import choose_demo_action

    for _ in range(100):
        if not run.state.relic_work:
            break
        assert not any(isinstance(a, ChooseNode) for a in run.legal_actions())
        step(run, choose_demo_action(run))
    assert not run.state.relic_work
    assert run.state.ancient_start.selected == name
    assert any(isinstance(a, ChooseNode) for a in run.legal_actions())


def test_future_freezes_bottles_then_releases_after_reward():
    run = start("the_future_of_potions")
    assert not any(isinstance(a, (UsePotion, DiscardPotion)) for a in run.legal_actions())
    original = run.state.potions[0].instance_id
    step(run, option(run, "trade_0"))
    assert all(p is None or p.instance_id != original for p in run.state.potions)
    assert all(v["upgrade_level"] == 1 for v in run.state.pending["data"]["active"]["modifiers"].values())
    step(run, option(run, "skip"))
    assert any(isinstance(a, UsePotion) for a in run.legal_actions())


def test_choir_removes_two_then_adds_playable_spore_mind():
    run = start("luminous_choir")
    old = len(run.state.deck)
    step(run, option(run, "reach_into_the_flesh"))
    assert run.state.pending["stage"] == "select_card"
    identity = run.state.pending["data"]["eligible"][0]
    step(run, ChooseEventCard(0, identity))
    assert len(run.state.deck) == old - 1
    assert not any(c.definition.definition_id == "spore_mind" for c in run.state.deck)
    settle(run)
    assert len(run.state.deck) == old - 1
    spore = next(c for c in run.state.deck if c.definition.definition_id == "spore_mind")
    assert spore.cost == 1 and spore.exhausts


def test_unrest_uses_captured_heal_and_does_not_run_rest_relics():
    run = start("unrest_site", relics=("regal_pillow",), hp=20, potions=("blood_potion",))
    step(run, UsePotion(run.state.potions[0].instance_id))
    step(run, option(run, "rest"))
    assert run.state.hp == 80
    assert run.state.deck[-1].definition.definition_id == "poor_sleep"


@pytest.mark.parametrize(
    "event,choice",
    [
        ("this_or_that", "plain"),
        ("brain_leech", "rip"),
        ("room_full_of_cheese", "search"),
        ("the_legends_were_true", "slowly_find_an_exit"),
    ],
)
def test_lethal_events_stop_but_fairy_revives(event, choice):
    run = start(event, hp=1, potions=())
    step(run, option(run, choice))
    assert run.state.hp == 0 and not run.legal_actions()
    if event == "this_or_that":
        assert run.state.gold == 200 + run.state.pending["data"]["variables"]["gold"]
    if event == "room_full_of_cheese":
        assert any(r.definition_id == "chosen_cheese" for r in run.state.relics)
    run = start(event, hp=1, potions=("fairy_in_a_bottle",))
    step(run, option(run, choice))
    settle(run)
    assert run.state.hp == 24


def test_invalid_branch_cursor_and_offers_restore_atomically():
    run = start("brain_leech")
    step(run, option(run, "share_knowledge"))
    baseline = saved(run)
    for mutate in (
        lambda d: d.update(cursor=10),
        lambda d: d["active"]["offers"].append("strike"),
        lambda d: d.update(choice="rip"),
    ):
        bad = deepcopy(baseline)
        mutate(bad["state"]["pending"]["data"])
        with pytest.raises(ValueError):
            run.restore(bad)
        assert saved(run) == baseline


@pytest.mark.parametrize(
    "name,choice,relic",
    [
        ("room_full_of_cheese", "search", "chosen_cheese"),
        ("tea_master", "bone_tea", "bone_tea"),
        ("tea_master", "ember_tea", "ember_tea"),
        ("tea_master", "tea_of_discourtesy", "tea_of_discourtesy"),
    ],
)
def test_repeated_event_relics_have_owned_instances(name, choice, relic):
    run = start(name, relics=(relic,))
    step(run, option(run, choice))
    owned = [r for r in run.state.relics if r.definition_id == relic]
    assert len(owned) == 2 and owned[0].instance_id != owned[1].instance_id


@pytest.mark.parametrize("mutation", ["hp", "gold", "remove_card", "potion", "cursor"])
def test_event_checkpoint_rejects_changed_result(mutation):
    run = start("unrest_site")
    step(run, option(run, "rest"))
    baseline = saved(run)
    broken = deepcopy(baseline)
    s = broken["state"]
    if mutation == "hp":
        s["hp"] -= 1
    elif mutation == "gold":
        s["gold"] += 99
    elif mutation == "remove_card":
        s["deck"].pop()
    elif mutation == "potion":
        s["potions"][0] = None
    else:
        s["pending"]["data"]["cursor"] = 0
    with pytest.raises(ValueError):
        run.restore(broken)
    assert saved(run) == baseline


def test_neow_cannot_restore_unsupported_kaleidoscope_offer():
    seed = next(s for s in range(100) if "kaleidoscope" in generate(GameRandomService(s)))
    run = RunEngine.ironclad_act1(seed=seed, ancient_profile=PROFILE)
    baseline = saved(run)
    bad = deepcopy(baseline)
    a = bad["state"]["ancient_start"]
    a["unavailable"] = []
    a["offers"] = generate(GameRandomService(seed))
    assert "kaleidoscope" in a["offers"]
    with pytest.raises(ValueError):
        run.restore(bad)
    assert saved(run) == baseline


def test_event_restores_during_nested_random_relic_pickup(monkeypatch):
    run = start("this_or_that")
    original = run.state.rng.choice
    monkeypatch.setattr(
        run.state.rng,
        "choice",
        lambda stream, pool: "orrery" if stream == "event.relic" else original(stream, pool),
    )
    # A deterministic forced outcome tests pickup continuation; the saved RNG
    # object remains an ordinary named service once the event transaction commits.
    run.apply(option(run, "ornate"))
    assert run.state.relic_work and not any(c.definition.definition_id == "clumsy" for c in run.state.deck)
    settle(run)
    assert run.state.deck[-1].definition.definition_id == "clumsy"


def test_self_help_power_and_empty_skip():
    from game.headless.run.deck import add_card

    run = RunEngine()
    add_card(run.state, run.cards.definition("inflame"))
    events.begin(run.state, "self_help_book")
    step(run, option(run, "read_entire_book"))
    settle(run)
    card = next(c for c in run.state.deck if c.definition.definition_id == "inflame")
    assert card.enchantment.definition_id == "swift" and card.enchantment.amount == 2
    run = RunEngine(card_ids=[])
    events.begin(run.state, "self_help_book")
    assert events.legal_actions(run.state) == (option(run, "skip_book"),)
    step(run, option(run, "skip_book"))


def combat_cards(*names):
    run = RunEngine(card_ids=list(names), gold=15)
    run.start_combat(cards_per_turn=len(names), energy_per_turn=20)
    run.combat.enemies[0].hp = run.combat.enemies[0].max_hp = 1000
    return run


@pytest.mark.parametrize("upgraded,hits", [(False, 3), (True, 4)])
def test_peck_hits_and_spore_exhaust(upgraded, hits):
    run = combat_cards("peck", "spore_mind")
    card = next(c for c in run.combat.player.hand if c.definition.definition_id == "peck")
    if upgraded:
        card.upgrade()
    step(run, PlayCard(card.instance_id, 0))
    assert run.combat.enemies[0].hp == 1000 - 2 * hits
    spore = next(c for c in run.combat.player.hand if c.definition.definition_id == "spore_mind")
    step(run, PlayCard(spore.instance_id))
    assert spore in run.combat.player.deck.exhaust_pile


def test_toric_captures_modified_block_and_two_independent_clears():
    run = combat_cards("toric_toughness", "toric_toughness")
    p = run.combat.player
    p.rules.powers["dexterity"] = 3
    for c in tuple(p.hand):
        step(run, PlayCard(c.instance_id))
    assert p.block == 16
    p.rules.powers["dexterity"] = 20
    p.statuses.add("frail", 3)
    from game.headless.cards.event_effects import after_block_cleared

    for _ in range(2):
        p.block = 0
        after_block_cleared(p)
        assert p.block == 16
        clone(run)
    p.block = 0
    after_block_cleared(p)
    assert p.block == 0
    assert not any(k.startswith("toric_toughness:") for k in p.rules.powers)


def test_slither_rerolls_absolute_combat_cost_and_restores_rng():
    from game.headless.enchantments.base import enchant, after_draw, can_enchant

    run = combat_cards("inflame", "whirlwind")
    p = run.combat.player
    card = next(c for c in p.hand if c.definition.definition_id == "inflame")
    assert not can_enchant(next(c for c in p.hand if c.definition.definition_id == "whirlwind"), "slither")
    enchant(card, "slither")
    card.combat_state.free_this_combat = True
    after_draw(card, p.deck)
    cost = p.card_cost(card)
    assert 0 <= cost <= 3 and not card.combat_state.free_this_combat
    card.upgrade()
    assert p.card_cost(card) == cost
    other = clone(run)
    for _ in range(6):
        after_draw(card, p.deck)
        same = next(c for c in other.combat.player.hand if c.instance_id == card.instance_id)
        after_draw(same, other.combat.player.deck)
        assert p.card_cost(card) == other.combat.player.card_cost(same)
    state = card.combat_state
    state.free_this_turn = True
    assert p.card_cost(card) == 0
    state.free_this_turn = False
    state.turn_cost_override = 3
    state.override_turn_baseline = state.cost_change
    state.override_combat_baseline = state.combat_cost_change
    assert p.card_cost(card) == 3
    state.turn_cost_override = None
    assert p.card_cost(card) == state.combat_cost_override


@pytest.mark.parametrize("name", ("debt", "decay", "doubt", "regret", "shame"))
def test_curse_end_hand_effects_and_continuation(name):
    run = combat_cards(name, "defend", "poor_sleep")
    p = run.combat.player
    p.block = 10
    hp = p.hp
    p.end_turn()
    run.sync_combat_loot()
    if name == "debt":
        assert run.state.gold == 5
    elif name == "decay":
        assert p.hp == hp and p.block == 8
    elif name == "regret":
        assert p.hp == hp - 3 and p.block == 10
    else:
        assert p.statuses.get("weak" if name == "doubt" else "frail") == 1
    assert [c.definition.definition_id for c in p.hand] == ["poor_sleep"]
    clone(run)


def test_normality_limits_manual_and_automatic_plays_and_then_releases():
    run = combat_cards("normality", "anger", "anger", "anger", "anger")
    p = run.combat.player
    for _ in range(3):
        step(run, next(a for a in run.legal_actions() if isinstance(a, PlayCard)))
    assert not any(isinstance(a, PlayCard) for a in run.legal_actions())
    from game.headless.core.resolution import start_play, drain

    extra = next(c for c in p.hand if c.definition.definition_id == "anger")
    start_play(p, extra, auto=True)
    drain(p)
    assert p.cards_played_this_turn == 3
    p.hand.remove(next(c for c in p.hand if c.definition.definition_id == "normality"))
    p.draw_cards(1)
    assert any(isinstance(a, PlayCard) for a in run.legal_actions())


def test_modifier_curse_pool_is_complete_and_bones_deferred():
    from game.headless.cards.curses import MODIFIER_CURSES

    assert len(MODIFIER_CURSES) == 10
    run = RunEngine()
    add_relic(run.state, "neows_bones", cards=run.cards)
    assert run.state.relic_work[-1]["operation"] == "curse"
    assert run.state.rng.request_count("relic.curse") == 0
    from game.cli.headless_play import choose_demo_action

    while run.state.relic_work:
        run.apply(choose_demo_action(run))
    assert run.state.rng.request_count("relic.curse") == 1
    assert run.state.deck[-1].definition.definition_id in MODIFIER_CURSES
    clone(run)


def test_toric_triggers_under_barricade():
    run = combat_cards("toric_toughness")
    p = run.combat.player
    step(run, PlayCard(p.hand[0].instance_id))
    p.rules.powers["barricade"] = 1
    p.start_turn(0)
    assert p.block == 10
    assert next(v for k, v in p.rules.powers.items() if k.startswith("toric_toughness:")) == 1
    clone(run)


def test_hellraiser_autoplays_before_slither_without_cost_rng():
    from game.headless.enchantments.base import enchant

    run = RunEngine(card_ids=["strike"])
    enchant(run.state.deck[0], "slither")
    run.start_combat(cards_per_turn=0)
    p = run.combat.player
    p.rules.powers["hellraiser"] = 1
    before = p.deck.energy_rng.getstate()
    p.draw_cards(1)
    assert p.deck.energy_rng.getstate() == before
    assert p.deck.discard_pile[0].combat_state.combat_cost_override is None
    clone(run)


def test_end_hand_damage_resumes_after_puzzle_draw_choice():
    run = RunEngine(card_ids=["regret", "debt", "defend", "strike", "defend", "strike"], gold=15)
    add_relic(run.state, "centennial_puzzle")
    run.start_combat(cards_per_turn=0)
    p = run.combat.player
    for name in ("regret", "debt"):
        card = next(c for c in p.deck.draw_pile if c.definition.definition_id == name)
        p.deck.draw_pile.remove(card)
        p.hand.append(card)
    p.deck.discard_pile.extend(p.deck.draw_pile)
    p.deck.draw_pile.clear()
    p.rules.powers["stratagem"] = 1
    run.apply(EndTurn())
    assert p.rules.selection is not None
    clone(run)
    from game.headless.core.actions import ConfirmCombatSelection, ChooseCombatCard

    for _ in range(20):
        if p.rules.selection is None:
            break
        actions = run.legal_actions()
        action = next((a for a in actions if isinstance(a, ConfirmCombatSelection)), actions[0])
        step(run, action)
    assert run.state.gold == 5


def test_regret_captures_after_stampede_and_ethereal_precedes_decay():
    from game.headless.powers.ironclad import end_turn

    for names, powers, loss, block in [
        (["regret", "strike"], {"stampede": 1}, 1, 0),
        (["dazed", "decay"], {"feel_no_pain": 3}, 0, 1),
    ]:
        run = RunEngine(card_ids=names)
        run.start_combat(cards_per_turn=0)
        p = run.combat.player
        p.hand.extend(p.deck.draw_pile)
        p.deck.draw_pile.clear()
        p.rules.powers.update(powers)
        hp = p.hp
        end_turn(p)
        assert hp - p.hp == loss
        assert p.block == block
        clone(run)


def test_remaining_curse_task_cannot_be_omitted_on_restore():
    run = RunEngine(card_ids=["decay", "regret", "strike", "defend", "strike"])
    add_relic(run.state, "centennial_puzzle")
    run.start_combat(cards_per_turn=0)
    p = run.combat.player
    for card in tuple(p.deck.draw_pile):
        p.deck.draw_pile.remove(card)
        (p.hand if card.definition.definition_id in ("decay", "regret") else p.deck.discard_pile).append(card)
    p.hand.sort(key=lambda c: c.definition.definition_id)
    p.rules.powers["stratagem"] = 1
    run.apply(EndTurn())
    assert p.rules.selection is not None
    snapshot = saved(run)

    def corrupt(value):
        if isinstance(value, dict):
            if "end_hand_remaining" in value:
                assert value["end_hand_remaining"]
                value["tasks"] = [t for t in value["tasks"] if t[0] != "end_hand_card"]
                return True
            return any(corrupt(v) for v in value.values())
        return False

    assert corrupt(snapshot)
    with pytest.raises(ValueError):
        RunEngine().restore(snapshot)


def test_full_curse_catalog_and_special_rules():
    from game.headless.cards.curses import ALL_CURSES, MODIFIER_CURSES
    from game.headless.core.resolution import start_play, drain
    from game.headless.powers.ironclad import end_turn

    assert len(set(ALL_CURSES)) == 18 and len(MODIFIER_CURSES) == 10
    run = RunEngine(card_ids=list(ALL_CURSES))
    assert len(run.state.deck) == 18
    run = RunEngine(card_ids=["enthralled", "strike"])
    run.start_combat(cards_per_turn=0)
    p = run.combat.player
    p.hand.extend(p.deck.draw_pile)
    p.deck.draw_pile.clear()
    enthralled = next(c for c in p.hand if c.definition.definition_id == "enthralled")
    assert all(
        not isinstance(a, PlayCard) or a.instance_id == enthralled.instance_id for a in run.legal_actions()
    )
    strike = next(c for c in p.hand if c.definition.definition_id == "strike")
    start_play(p, strike, auto=True)
    drain(p)
    assert strike in p.deck.discard_pile
    run.apply(PlayCard(enthralled.instance_id))
    clone(run)
    run = RunEngine(card_ids=["bad_luck", "ascenders_bane", "folly", "curse_of_the_bell"])
    run.start_combat(cards_per_turn=0)
    p = run.combat.player
    p.hand.extend(p.deck.draw_pile)
    p.deck.draw_pile.clear()
    p.block = 20
    hp = p.hp
    end_turn(p)
    assert hp - p.hp == 13 and p.block == 20
    assert {c.definition.definition_id for c in p.deck.exhaust_pile} == {"ascenders_bane", "folly"}
    clone(run)
