"""Hand choices, interrupted card resolution and combat-only mutations."""

import json
from copy import deepcopy

import pytest

from game.headless.cards.base import CardDefinition, CardSpec
from game.headless.cards.catalog import CardCatalog, DEFAULT_CARDS
from game.headless.cards.effects import DrawCards, GainBlock, SelectHandCard
from game.headless.core.actions import ChooseCombatCard, EndTurn, PlayCard
from game.headless.core.combat import CombatEngine
from game.headless.run.actions import DiscardPotion, UsePotion
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_potion


def saved(engine):
    return json.loads(json.dumps(engine.snapshot()))


def setup(card_id="armaments", level=0, others=("strike", "strike")):
    run = RunEngine(card_ids=(card_id, *others))
    if level:
        run.upgrade_card("run.card.0")
    combat = run.start_combat(cards_per_turn=10)
    return run, combat


@pytest.mark.parametrize("card_id,level,block", [("armaments", 0, 5), ("true_grit", 1, 9)])
def test_pending_choice_has_exact_ids_cost_and_block_once_and_roundtrips(card_id, level, block):
    run, combat = setup(card_id, level)
    add_potion(run.state, "fire_potion")
    run.apply(PlayCard("run.card.0"))
    assert combat.player.block == block and combat.player.energy == 2
    assert [c.instance_id for c in combat.player.deck.in_play] == ["run.card.0"]
    assert set(run.legal_actions()) == {ChooseCombatCard("run.card.1"), ChooseCombatCard("run.card.2")}
    before = saved(run)
    potion = run.state.potions[0].instance_id
    for action in (EndTurn(), PlayCard("run.card.1", 0), ChooseCombatCard("run.card.0"),
                   ChooseCombatCard("missing"), UsePotion(potion, 0), DiscardPotion(potion)):
        with pytest.raises(ValueError):
            run.apply(action)
        assert saved(run) == before
    restored = RunEngine()
    restored.restore(before)
    for engine in (run, restored):
        engine.apply(ChooseCombatCard("run.card.2"))
        player = engine.combat.player
        assert player.pending_play is None and player.deck.in_play == []
        assert player.block == block and player.energy == 2
        assert [c.instance_id for c in player.deck.discard_pile] == ["run.card.0"]
        if card_id == "armaments":
            assert {c.instance_id: c.upgrade_level for c in player.hand} == {"run.card.1": 0, "run.card.2": 1}
        else:
            assert [c.instance_id for c in player.deck.exhaust_pile] == ["run.card.2"]
        assert [c.upgrade_level for c in engine.state.deck] == [level, 0, 0]
    assert saved(run) == saved(restored)


@pytest.mark.parametrize("card_id,level,block", [("armaments", 0, 5), ("armaments", 1, 5),
                                               ("true_grit", 0, 7), ("true_grit", 1, 9)])
@pytest.mark.parametrize("others", [(), ("strike",)])
def test_zero_and_one_eligible_auto_resolve(card_id, level, block, others):
    run, combat = setup(card_id, level, others)
    run.apply(PlayCard("run.card.0"))
    assert combat.player.pending_play is None
    assert combat.player.deck.in_play == []
    assert combat.player.block == block
    if others:
        if card_id == "armaments":
            assert combat.player.hand[0].upgrade_level == 1
        else:
            assert len(combat.player.deck.exhaust_pile) == 1
    clone = RunEngine()
    clone.restore(saved(run))
    assert saved(clone) == saved(run)


def test_armaments_filters_max_upgrades_and_statuses_and_upgrades_all_once():
    run, combat = setup(level=1, others=("strike", "body_slam", "slimed", "defend"))
    defend = next(c for c in combat.player.hand if c.definition.definition_id == "defend")
    defend.upgrade()
    run.apply(PlayCard("run.card.0"))
    assert combat.player.pending_play is None
    assert {c.definition.definition_id: c.upgrade_level for c in combat.player.hand} == {
        "strike": 1, "body_slam": 1, "slimed": 0, "defend": 1}
    combat.player.energy = 0
    assert PlayCard("run.card.2", 0) in combat.legal_actions()
    run.apply(PlayCard("run.card.2", 0))
    assert combat.enemies[0].hp == 35
    # Upgrades survive reshuffling within combat, but never change the master deck.
    combat.player.deck.discard_hand()
    combat.player.draw_cards(10)
    assert next(c for c in combat.player.hand if c.instance_id == "run.card.2").upgrade_level == 1
    assert [c.upgrade_level for c in run.state.deck] == [1, 0, 0, 0, 0]
    combat.enemies[0].hp = 0
    combat.resolve_external_effect()
    run.finish_combat()
    next_combat = run.start_combat(cards_per_turn=10)
    assert {c.instance_id: c.upgrade_level for c in next_combat.player.hand} == {
        c.instance_id: c.upgrade_level for c in run.state.deck}


def test_base_armaments_with_one_eligible_filters_without_prompt():
    run, combat = setup(others=("strike", "slimed", "defend"))
    next(c for c in combat.player.hand if c.definition.definition_id == "defend").upgrade()
    run.apply(PlayCard("run.card.0"))
    assert combat.player.pending_play is None
    assert next(c for c in combat.player.hand if c.instance_id == "run.card.1").upgrade_level == 1


def test_random_exhaust_has_owned_continuation_and_does_not_consume_shuffle_rng():
    run, combat = setup("true_grit", others=("strike", "slimed", "defend"))
    restored = RunEngine()
    restored.restore(saved(run))
    shuffle_state = combat.rng.getstate()
    selection_state = combat.player.deck.selection_rng.getstate()
    for engine in (run, restored):
        engine.apply(PlayCard("run.card.0"))
        assert engine.combat.player.pending_play is None
        assert len(engine.combat.player.deck.exhaust_pile) == 1
        assert engine.combat.rng.getstate() == shuffle_state
        assert engine.combat.player.deck.selection_rng.getstate() != selection_state
    assert saved(run) == saved(restored)


@pytest.mark.parametrize("change", [
    lambda s: s.update(pending_play=None),
    lambda s: s["pending_play"].update(effect_index=0),
    lambda s: s["pending_play"].update(effect_index=True),
    lambda s: s["pending_play"].update(effect_index=99),
    lambda s: s["pending_play"].update(target_slot=0),
    lambda s: s["pending_play"].update(callback="anything"),
    lambda s: s["deck"]["piles"]["in_play"].clear(),
    lambda s: s["deck"]["piles"]["in_play"][0].update(upgrade_level=1),
    lambda s: s["deck"]["piles"].update(hand=s["deck"]["piles"]["hand"][:1]),
    lambda s: s["deck"].update(selection_rng=-1),
])
def test_malformed_pending_restore_is_atomic(change):
    _, combat = setup()
    combat.apply(PlayCard("run.card.0"))
    before = saved(combat)
    invalid = deepcopy(before)
    change(invalid)
    with pytest.raises(ValueError):
        combat.restore(invalid)
    assert saved(combat) == before


def test_authored_effect_suffix_and_second_choice_resume_without_replaying_prefix():
    # Synthetic composition exercises the reusable continuation, not another native card.
    definition = CardDefinition("two_choices", (CardSpec("Two choices", 1, "skill", block_gain=4,
                                                        draw_count=1, uses_target=False),),
                                (GainBlock(), SelectHandCard("upgrade"),
                                 SelectHandCard("exhaust"), DrawCards()))
    catalog = CardCatalog((*DEFAULT_CARDS.definitions, definition))
    combat = CombatEngine(deck_factory=lambda: [catalog.create(i) for i in
                          ("two_choices", "strike", "strike", "defend")], cards_per_turn=4)
    combat.reset()
    card = next(c for c in combat.player.hand if c.definition.definition_id == "two_choices")
    combat.apply(PlayCard(card.instance_id))
    combat.apply(combat.legal_actions()[0])
    assert combat.player.pending_play.effect_index == 2
    assert combat.player.block == 4 and combat.player.energy == 2
    snapshot = json.loads(json.dumps(combat.snapshot(cards=catalog)))
    clone = CombatEngine()
    clone.restore(snapshot, cards=catalog)
    action = combat.legal_actions()[-1]
    for engine in (combat, clone):
        engine.apply(action)
        assert engine.player.pending_play is None
        assert engine.player.block == 4 and engine.player.energy == 2
        assert len(engine.player.deck.exhaust_pile) == 1
        # Draw cannot draw the currently resolving source card.
        assert engine.player.deck.discard_pile[-1].instance_id == card.instance_id
    assert combat.snapshot(cards=catalog) == clone.snapshot(cards=catalog)


@pytest.mark.parametrize("card_id,level", [("armaments", 0), ("true_grit", 1)])
def test_isolated_player_can_resolve_untargeted_card_with_legacy_enemy_argument(card_id, level):
    from random import Random
    from game.headless.core.deck import Deck
    from game.headless.core.player import Player
    from game.headless.monsters.overgrowth import SimpleEnemy
    player = Player(Deck([DEFAULT_CARDS.create(card_id, upgrade_level=level),
                          DEFAULT_CARDS.create("strike"), DEFAULT_CARDS.create("defend")], Random(3)))
    player.start_turn()
    index = next(i for i, card in enumerate(player.hand) if card.definition.definition_id == card_id)
    player.play_card(index, SimpleEnemy())
    assert player.pending_play.target_slot is None
    player.choose_combat_card(player.pending_options()[0])
    assert player.pending_play is None and len(player.deck.discard_pile) == 1
