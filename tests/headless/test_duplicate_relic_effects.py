"""Physical duplicate relic effects after native shared-bag refill.

Source: RelicCmd.Obtain/Player.AddRelicInternal append independent instances;
Hook.ShouldDie chooses the first eligible late preventer, while every Tungsten
Rod participates in ModifyHpLostAfterOsty.
"""

import json

import pytest

from game.headless.core.combat import CombatEngine
from game.headless.potions.base import PotionInstance
from game.headless.relics.base import RelicInstance
from game.headless.relics.run_rules import damage
from game.headless.run.engine import RunEngine


def setup(mode, relics, *, fairy=False):
    potions = [PotionInstance("fairy_in_a_bottle", "test.potion")] if fairy else []
    if mode == "combat":
        engine = CombatEngine(player_max_hp=80)
        engine.reset(relics=relics, initial_hp=20, potions=potions)
        subject = engine.player

        def lose(amount):
            subject.lose_hp(amount)
            engine.resolve_external_effect()

        counters = lambda: [r["counter"] for r in subject.rules.relics]
    else:
        engine = RunEngine(hp=20, max_hp=80)
        subject = engine.state
        subject.relics = list(relics)
        subject.potions = potions
        lose = lambda amount: damage(subject, amount)
        counters = lambda: [r.counter for r in subject.relics]
    return engine, subject, lose, counters


@pytest.mark.parametrize("mode", ("combat", "run"))
def test_duplicate_tails_prevent_separate_deaths_in_inventory_order(mode):
    _, subject, lose, counters = setup(mode, [
        RelicInstance("lizard_tail", "tail.first"),
        RelicInstance("lizard_tail", "tail.second"),
    ])
    lose(100)
    assert subject.hp == 40 and counters() == [1, 0]
    lose(100)
    assert subject.hp == 40 and counters() == [1, 1]
    lose(100)
    assert subject.hp == 0 and counters() == [1, 1]


@pytest.mark.parametrize("mode", ("combat", "run"))
def test_used_tail_does_not_hide_new_tail_and_fairy_has_priority(mode):
    _, subject, lose, counters = setup(mode, [
        RelicInstance("lizard_tail", "tail.used", counter=1),
        RelicInstance("lizard_tail", "tail.fresh"),
    ], fairy=True)
    lose(100)
    assert subject.hp == 24 and counters() == [1, 0]
    lose(100)
    assert subject.hp == 40 and counters() == [1, 1]


@pytest.mark.parametrize("mode", ("combat", "run"))
@pytest.mark.parametrize("amount,expected", ((1, 20), (2, 20), (5, 17)))
def test_each_tungsten_rod_reduces_damage_without_negative_loss(mode, amount, expected):
    _, subject, lose, _ = setup(mode, [
        RelicInstance("tungsten_rod", "rod.first"),
        RelicInstance("tungsten_rod", "rod.second"),
    ])
    lose(amount)
    assert subject.hp == expected


def test_duplicate_tail_counters_resume_independently_from_combat_json():
    engine, _, lose, _ = setup("combat", [
        RelicInstance("lizard_tail", "tail.first"),
        RelicInstance("lizard_tail", "tail.second"),
    ])
    lose(100)
    saved = json.loads(json.dumps(engine.snapshot()))
    restored = CombatEngine()
    restored.restore(saved)
    restored.player.lose_hp(100)
    restored.resolve_external_effect()
    lose(100)
    assert restored.player.hp == 40
    assert json.loads(json.dumps(restored.snapshot())) == json.loads(json.dumps(engine.snapshot()))


def card_combat(names, relics, *, upgraded=False):
    from game.headless.cards.catalog import DEFAULT_CARDS
    from game.headless.monsters.overgrowth import SimpleEnemy
    engine = CombatEngine(
        deck_factory=lambda: [DEFAULT_CARDS.create(name, upgrade_level=int(upgraded)) for name in names],
        cards_per_turn=len(names), energy_per_turn=10,
        enemy_factory=lambda: SimpleEnemy(max_hp=1000),
    )
    engine.reset(relics=relics)
    return engine


def play(engine, name):
    from game.headless.core.actions import PlayCard
    card = next(c for c in engine.player.hand if c.definition.definition_id == name)
    engine.apply(next(a for a in engine.legal_actions() if isinstance(a, PlayCard) and a.instance_id == card.instance_id))


@pytest.mark.parametrize("counters,damage", (((9, 9), 24), ((0, 9), 12)))
def test_each_activating_pen_nib_multiplies_same_play(counters, damage):
    engine = card_combat(("strike",), [RelicInstance("pen_nib", f"nib.{i}", counter=value)
                                            for i, value in enumerate(counters)])
    play(engine, "strike")
    assert engine.enemies[0].hp == 1000 - damage
    assert [r["counter"] for r in engine.player.rules.relics] == [(v + 1) % 10 for v in counters]


def test_duplicate_vambraces_only_multiply_first_card():
    engine = card_combat(("defend", "defend"), [RelicInstance("vambrace", f"brace.{i}") for i in range(2)])
    play(engine, "defend")
    assert engine.player.block == 20
    play(engine, "defend")
    assert engine.player.block == 25
    assert all(m["used"] for m in engine.player.rules.relic_data.values())


def test_duplicate_lamps_share_triggering_card_but_own_usage():
    engine = card_combat(("bash", "bash"), [RelicInstance("unsettling_lamp", f"lamp.{i}") for i in range(2)])
    play(engine, "bash")
    assert engine.enemies[0].statuses.get("vulnerable") == 8
    play(engine, "bash")
    assert engine.enemies[0].statuses.get("vulnerable") == 10
    assert all(m["used"] for m in engine.player.rules.relic_data.values())


def test_each_dummy_and_cannon_adds_damage():
    engine = card_combat(("strike",), [RelicInstance(name, f"bonus.{i}") for i, name in enumerate(
        ("strike_dummy", "strike_dummy", "miniature_cannon", "miniature_cannon"))], upgraded=True)
    play(engine, "strike")
    assert engine.enemies[0].hp == 979  # Strike+9 + two3-damage bonuses of each kind.


@pytest.mark.parametrize("hp,expected", ((20, 44), (35, 47)))
def test_each_meat_on_the_bone_rechecks_post_heal_threshold(hp, expected):
    from game.headless.relics.run_rules import victory
    run = RunEngine(hp=hp, max_hp=80)
    run.state.relics = [RelicInstance("meat_on_the_bone", f"meat.{i}") for i in range(2)]
    victory(run.state)
    assert run.state.hp == expected


def test_two_mailboxes_create_four_rewards_with_per_instance_sources():
    from game.headless.relics.run_rules import rest_rewards
    from game.headless.relics.pickup import validate
    run = RunEngine()
    run.state.relics = [RelicInstance("tiny_mailbox", f"mail.{i}") for i in range(2)]
    rest_rewards(run.state)
    assert [w["source"] for w in run.state.relic_work] == ["mail.0", "mail.0", "mail.1", "mail.1"]
    assert all(w["kind"] == "potion_reward" for w in run.state.relic_work)
    validate(run.state, run.cards)


def test_two_tops_draw_twice_from_one_empty_hand_event():
    engine = card_combat(("strike", "defend", "defend"), [RelicInstance("unceasing_top", f"top.{i}") for i in range(2)])
    p = engine.player
    strike = next(c for c in p.hand if c.definition.definition_id == "strike")
    p.deck.draw_pile.extend(c for c in p.hand if c is not strike)
    p.hand[:] = [strike]
    play(engine, "strike")
    assert len(p.hand) == 2


def test_two_top_draws_resume_after_stratagem_shuffle_choice():
    from game.headless.core.actions import ChooseCombatCard, ConfirmCombatSelection
    from game.headless.powers.ironclad import apply_power
    engine = card_combat(("strike", "defend", "defend"), [RelicInstance("unceasing_top", f"top.{i}") for i in range(2)])
    p = engine.player
    strike = next(c for c in p.hand if c.definition.definition_id == "strike")
    p.deck.discard_pile.extend(c for c in p.hand if c is not strike)
    p.hand[:] = [strike]
    apply_power(p, "stratagem", 1)
    play(engine, "strike")
    action = next(a for a in engine.legal_actions() if isinstance(a, ChooseCombatCard))
    clone = CombatEngine()
    clone.restore(json.loads(json.dumps(engine.snapshot())))
    engine.apply(action)
    clone.apply(action)
    engine.apply(ConfirmCombatSelection())
    clone.apply(ConfirmCombatSelection())
    assert len(p.hand) == 3  # Stratagem's selected card, then both Top draws.
    assert json.loads(json.dumps(clone.snapshot())) == json.loads(json.dumps(engine.snapshot()))


def test_two_candies_append_independent_power_positions_and_restore():
    from game.headless.run.config import RunConfig
    from game.headless.run.rewards import begin_combat_rewards
    run = RunEngine(seed=2, rng_profile="native", config=RunConfig(reward_cards=("inflame", "barricade", "rupture")))
    run.obtain_relic("lasting_candy")
    run.obtain_relic("lasting_candy")
    run.obtain_relic("prayer_wheel")
    begin_combat_rewards(run.state, run.cards)
    assert len(run.state.pending["offers"]) == 5
    assert len(run.state.pending["extra_rewards"][0]["offers"]) == 5
    clone = RunEngine()
    clone.restore(json.loads(json.dumps(run.snapshot())))
    assert clone.legal_actions() == run.legal_actions()


def test_candy_ignores_inactive_first_copy_and_keeps_duplicate_upgrade_positions(monkeypatch):
    from game.headless.relics.rewards import combat_modifiers
    from game.headless.generation import odds
    run = RunEngine(seed=2, rng_profile="native")
    run.state.relics = [RelicInstance("lasting_candy", "candy.old", counter=1),
                        RelicInstance("lasting_candy", "candy.first"),
                        RelicInstance("lasting_candy", "candy.second")]
    calls = []

    def create(*args, **kwargs):
        calls.append(kwargs)
        return ["inflame"], ["inflame"] if len(calls) == 2 else []

    monkeypatch.setattr(odds, "card_offers", create)
    offers = ["inflame", "barricade", "rupture"]
    mods = combat_modifiers(run.state, run.cards, offers, tuple(offers))
    assert offers == ["inflame", "barricade", "rupture", "inflame", "inflame"]
    assert [m["upgrade_level"] for m in mods] == [0, 0, 0, 0, 1]
    assert all(call["mode"] == "base" for call in calls)


def test_each_candy_uses_three_native_draws_and_does_not_repeat_available_powers():
    from game.headless.relics.rewards import add_power_option
    run = RunEngine(seed=42, rng_profile="native")
    run.state.relics = [RelicInstance("lasting_candy", f"candy.{i}") for i in range(2)]
    offers = ["strike", "defend", "bash"]
    before = run.state.rng.request_count("rewards")
    offset = run.state.generation_odds["card_offset"]
    add_power_option(run.state, run.cards, offers, ("inflame", "barricade", "rupture"))
    assert len(offers) == len(set(offers)) == 5
    assert run.state.rng.request_count("rewards") == before + 6
    assert run.state.generation_odds["card_offset"] == offset


@pytest.mark.parametrize("offers", (
    ["strike", "defend", "bash", "anger"],
    ["strike", "defend", "bash", "inflame", "barricade", "rupture"],
    ["strike", "strike", "bash", "inflame"],
))
def test_duplicate_candy_validation_rejects_wrong_kinds_counts_and_base_duplicates(offers):
    from game.headless.relics.rewards import validate_combat_offers
    run = RunEngine()
    run.state.relics = [RelicInstance("lasting_candy", f"candy.{i}") for i in range(2)]
    with pytest.raises(ValueError):
        validate_combat_offers(run.state, run.cards, offers)
