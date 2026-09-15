"""Native replacement factory vectors and owned Entropy/status continuations."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS, CardCatalog
from game.headless.cards.colorless_effects import transform, create
from game.headless.core.actions import PlayCard, ChooseCombatCard, ConfirmCombatSelection
from game.headless.core.native_rng import NativeRng
from game.headless.core.resolution import push, drain
from game.headless.generation.transforms import combat_options
from game.headless.powers.ironclad import apply_power, end_turn
from game.headless.powers.colorless import start_power
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine

VECTORS = json.loads((Path(__file__).parents[1] / "fixtures/headless_native_transform_vectors.json").read_text())
ALIASES = {"strike_ironclad": "strike", "defend_ironclad": "defend"}
SUPPORTED = {d.definition_id for d in DEFAULT_CARDS.definitions}
ROWS = [r for r in VECTORS["cases"] if ALIASES.get(r["original"], r["original"]) in SUPPORTED]


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def clone(run):
    other = RunEngine(cards=run.cards, card_ids=[])
    other.restore(saved(run))
    return other


def fight(*ids, cards=DEFAULT_CARDS):
    run = RunEngine(seed=2, rng_profile="native", config=RunConfig(), cards=cards, card_ids=ids)
    run.start_combat(encounter_id="overgrowth_cubex", cards_per_turn=0)
    run.combat.player.hand[:] = run.combat.player.deck.draw_pile
    run.combat.player.deck.draw_pile = []
    return run


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["original"])
def test_transform_pools_and_sequences_match_actual_native_factory(row):
    original = DEFAULT_CARDS.create(ALIASES.get(row["original"], row["original"]))
    options = combat_options(DEFAULT_CARDS, original)
    assert [d.definition_id for d in options] == row["options"]
    for sample in row["samples"]:
        rng = NativeRng(sample["seed"])
        assert [rng.choice(options).definition_id for _ in range(3)] == sample["selected"]
        assert rng.counter == sample["counter"]
        restored = NativeRng()
        restored.setstate(json.loads(json.dumps(rng.getstate())))
        assert restored.next_double() == rng.next_double() == sample["suffix"]


def test_all_native_combat_generatable_statuses_and_curses_have_matching_metadata():
    for pool in VECTORS["census"]:
        if pool["family"] not in ("status", "curse"):
            continue
        expected = [c for c in pool["cards"] if c["canGenerate"]]
        actual = [d for d in DEFAULT_CARDS.definitions if d.pool == pool["family"] and d.generate_in_combat]
        assert {d.definition_id for d in actual} == {c["id"] for c in expected}
        for c in expected:
            d = DEFAULT_CARDS.definition(c["id"])
            assert (d.rarity, d.levels[0].kind, d.levels[0].cost) == (c["rarity"].lower(), c["kind"].lower(), c["cost"])
            assert len(d.levels) == c["maxUpgrade"] + 1
            for name, keyword in (("exhausts", "Exhaust"), ("ethereal", "Ethereal"), ("retain", "Retain"), ("eternal", "Eternal"), ("innate", "Innate")):
                assert getattr(d.levels[0], name) == (keyword in c["keywords"]), (c["id"], keyword)


@pytest.mark.parametrize("identity,damage", [("burn", 2), ("toxic", 5), ("wither", 3)])
def test_status_end_damage_respects_block_and_restores(identity, damage):
    run = fight(identity)
    p = run.combat.player
    p.block = 1
    p.statuses.add("vulnerable", 9)
    before = p.hp
    other = clone(run)
    for r in (run, other):
        end_turn(r.combat.player)
    assert p.hp == before - damage + 1 and p.block == 0
    assert p.deck.discard_pile[0].definition.definition_id == identity
    assert saved(run) == saved(other)


def test_beckon_held_bypasses_block_but_buffer_prevents_it():
    run = fight("beckon")
    p = run.combat.player
    p.block = 20
    before = p.hp
    other = clone(run)
    apply_power(other.combat.player, "buffer", 1)
    end_turn(p)
    end_turn(other.combat.player)
    assert p.hp == before - 6 and p.block == 20
    assert other.combat.player.hp == before


def test_beckon_unblockable_damage_still_respects_supported_hp_caps():
    run = fight("beckon")
    p = run.combat.player
    p.block = 20
    p.statuses.add("slippery", 1)
    hp = p.hp
    end_turn(p)
    assert p.hp == hp - 1 and p.block == 20 and not p.statuses.get("slippery")


@pytest.mark.parametrize("identity,exhausted", [("beckon", False), ("debris", True), ("toxic", True)])
def test_playable_statuses_spend_energy_and_leave_correct_pile(identity, exhausted):
    run = fight(identity)
    p = run.combat.player
    original = p.hand[0]
    energy, hp = p.energy, p.hp
    other = clone(run)
    action = PlayCard(original.instance_id)
    for r in (run, other):
        r.apply(action)
    assert p.energy == energy - 1 and p.hp == hp
    assert original in (p.deck.exhaust_pile if exhausted else p.deck.discard_pile)
    assert saved(run) == saved(other)


@pytest.mark.parametrize("energy", [0, 1, 3])
@pytest.mark.parametrize("command", ["draw", "pillage"])
def test_void_loses_energy_on_each_actual_draw_only(energy, command):
    run = fight("void")
    p = run.combat.player
    p.deck.draw_pile = p.hand[:]
    p.hand.clear()
    p.energy = energy
    other = clone(run)
    for r in (run, other):
        push(r.combat.player, [command, 1, False] if command == "draw" else ["pillage"])
        drain(r.combat.player)
    assert p.energy == max(0, energy - 1)
    assert saved(run) == saved(other)
    end_turn(p)
    assert p.deck.exhaust_pile[0].definition.definition_id == "void"


def test_generated_void_does_not_trigger_draw_hook():
    run = fight()
    p = run.combat.player
    energy = p.energy
    create(p, DEFAULT_CARDS.definition("void"))
    assert p.energy == energy


def test_entropy_multi_choice_preserves_rng_piles_and_persistent_deck_across_restore():
    run = fight("wound", "injury", "defend")
    p = run.combat.player
    master = [(c.instance_id, c.definition.definition_id) for c in run.state.deck]
    apply_power(p, "entropy", 2)
    start_power(p, "entropy")
    selected = p.rules.selection["candidates"][:2]
    run.apply(ChooseCombatCard(selected[0]))
    other = clone(run)
    for action in (ChooseCombatCard(selected[1]), ConfirmCombatSelection()):
        for r in (run, other):
            r.apply(action)
        assert saved(run) == saved(other)
    assert not set(selected) & {c.instance_id for c in p.hand}
    assert p.deck.selection_rng.counter == 2
    assert [(c.instance_id, c.definition.definition_id) for c in run.state.deck] == master


def test_transform_clears_modifiers_and_runs_generated_entry_hook():
    cards = CardCatalog([replace(d, generate_in_combat=d.definition_id == "stomp") for d in DEFAULT_CARDS.definitions])
    run = fight("strike", cards=cards)
    p = run.combat.player
    original = p.hand[0]
    original.upgrade()
    original.combat_state.extra_damage = 20
    original.combat_state.replay_count = 3
    p.rules.attacks_finished = 2
    transform(p, original)
    replacement = p.hand[0]
    assert replacement.definition.definition_id == "stomp"
    assert replacement.instance_id != original.instance_id and not replacement.upgraded
    assert replacement.combat_state.extra_damage == replacement.combat_state.replay_count == 0
    assert replacement.combat_state.cost_change == -2


def test_empty_pool_and_foreign_instance_fail_before_rng_or_identity_changes():
    cards = CardCatalog([replace(d, generate_in_combat=False) for d in DEFAULT_CARDS.definitions])
    run = fight("strike", cards=cards)
    before = saved(run)
    with pytest.raises(ValueError, match="No eligible"):
        transform(run.combat.player, run.combat.player.hand[0])
    assert saved(run) == before
    run = fight("strike")
    before = saved(run)
    with pytest.raises(ValueError, match="owned card"):
        transform(run.combat.player, DEFAULT_CARDS.create("strike"))
    assert saved(run) == before


def test_foreign_family_is_preserved_when_supplied_explicitly():
    a = replace(DEFAULT_CARDS.definition("strike"), definition_id="foreign_a", pool="silent")
    b = replace(DEFAULT_CARDS.definition("anger"), definition_id="foreign_b", pool="silent")
    catalog = CardCatalog([a, b, DEFAULT_CARDS.definition("finesse")])
    assert combat_options(catalog, catalog.create("foreign_a")) == [b]


def test_automation_energy_gain_precedes_void_energy_loss():
    run = fight("void")
    p = run.combat.player
    p.deck.draw_pile = p.hand[:]
    p.hand.clear()
    apply_power(p, "automation", 1)
    key = next(k for k in p.rules.powers if k.startswith("automation:"))
    p.rules.auxiliaries[key] = 1
    p.energy = 0
    other = clone(run)
    for r in (run, other):
        r.combat.player.draw_cards(1)
    assert p.energy == 0 and p.rules.auxiliaries[key] == 10
    assert saved(run) == saved(other)


def test_status_end_effect_survives_reactive_draw_choice_and_rejects_missing_work():
    from copy import deepcopy
    from game.headless.core.actions import EndTurn
    from game.headless.run.inventory import add_relic

    run = RunEngine(seed=2, rng_profile="native", card_ids=["burn", "beckon", "strike", "defend", "bash"])
    add_relic(run.state, "centennial_puzzle")
    run.start_combat(cards_per_turn=0)
    p = run.combat.player
    for name in ("burn", "beckon"):
        card = next(c for c in p.deck.draw_pile if c.definition.definition_id == name)
        p.deck.draw_pile.remove(card)
        p.hand.append(card)
    p.deck.discard_pile[:] = p.deck.draw_pile
    p.deck.draw_pile.clear()
    apply_power(p, "stratagem", 1)
    run.apply(EndTurn())
    assert p.rules.selection is not None
    before = saved(run)
    broken = deepcopy(before)

    def remove_work(value):
        if isinstance(value, dict):
            if "end_hand_remaining" in value and value["end_hand_remaining"]:
                value["tasks"] = [t for t in value["tasks"] if t[0] != "end_hand_card"]
            for child in value.values():
                remove_work(child)
        elif isinstance(value, list):
            for child in value:
                remove_work(child)

    remove_work(broken)
    with pytest.raises(ValueError):
        run.restore(broken)
    assert saved(run) == before
    other = clone(run)
    while p.rules.selection:
        action = next((a for a in run.legal_actions() if isinstance(a, ConfirmCombatSelection)), run.legal_actions()[0])
        run.apply(action)
        other.apply(action)
        assert saved(run) == saved(other)
