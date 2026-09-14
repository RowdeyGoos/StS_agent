"""Source-backed queue composition regressions; no native selector execution."""

from copy import deepcopy
from dataclasses import replace
import json

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS, CardCatalog
from game.headless.cards.operations import Attack
from game.headless.core.actions import PlayCard, ChooseCombatCard, ConfirmCombatSelection
from game.headless.core.combat import CombatEngine
from game.headless.powers.ironclad import apply_power
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run.inventory import add_relic


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def clone(run):
    other = RunEngine(cards=run.cards)
    other.restore(saved(run))
    return other


def setup(*, fillers=3, upgraded=False, strength=0, cards=DEFAULT_CARDS, outer="sword_boomerang"):
    run = RunEngine(
        seed=2,
        rng_profile="native",
        config=RunConfig(),
        cards=cards,
        card_ids=[outer] + (["defend"] * fillers if isinstance(fillers, int) else fillers),
    )
    add_relic(run.state, "gremlin_horn", cards=cards)
    run.start_combat(encounter_id="overgrowth_phrog_parasite", cards_per_turn=0)
    p = run.combat.player
    card = next(c for c in p.deck.draw_pile if c.definition.definition_id == outer)
    p.deck.draw_pile.remove(card)
    p.hand.append(card)
    if upgraded:
        card.upgrade()
    p.deck.discard_pile = p.deck.draw_pile
    p.deck.draw_pile = []
    p.strength = strength
    apply_power(p, "stratagem", 1)
    run.combat.enemies[0].hp = 1
    return run, card


def finish_choices(run, other):
    while run.combat.player.rules.selection:
        s = run.combat.player.rules.selection
        identity = next(i for i in s["candidates"] if i not in s["selected"])
        for action in (ChooseCombatCard(identity), ConfirmCombatSelection()):
            run.apply(action)
            other.apply(action)
            assert saved(run) == saved(other)


def test_multihit_finishes_against_children_before_horn_stratagem_is_visible():
    run, card = setup()
    before_targets = run.combat.player.deck.target_rng.counter
    run.apply(PlayCard(card.instance_id))
    p = run.combat.player
    assert p.rules.selection["source"] == "stratagem"
    assert p.rules.attacks_finished == 1 and card in p.deck.discard_pile
    assert sum(e.max_hp - e.hp for e in run.combat.enemies[1:]) == 2 * card.spec.base_damage
    assert len(run.combat.enemies) == 5
    assert not any(t[0] in ("random_hit", "spawn_wrigglers") for t in p.rules.tasks)
    assert p.deck.target_rng.counter - before_targets == 3
    before_draw_rng = p.deck.rng.getstate()
    before_target_rng = p.deck.target_rng.getstate()
    other = clone(run)
    finish_choices(run, other)
    assert p.deck.rng.getstate() == before_draw_rng
    assert p.deck.target_rng.getstate() == before_target_rng
    assert not p.rules.tasks and not p.rules.deferred_hooks and p.rules.active_hook == 0


def test_later_automatic_horn_draws_shrink_live_choice_to_explicit_singleton():
    run, card = setup(strength=100)
    run.apply(PlayCard(card.instance_id))
    p = run.combat.player
    assert len([e for e in run.combat.enemies if e.is_alive]) == 2
    assert p.rules.hook_sequence == 3 and p.rules.active_hook == 1
    assert len(p.hand) == 2
    assert p.rules.selection["candidates"] == [p.deck.draw_pile[0].instance_id]
    assert p.rules.selection["selected"] == []
    other = clone(run)
    finish_choices(run, other)
    assert p.rules.selection is None and len(p.hand) == 4


def test_live_choice_empty_on_activation_completes_without_exposing_stale_cards():
    run, card = setup(strength=100, upgraded=True)
    run.apply(PlayCard(card.instance_id))
    p = run.combat.player
    assert len([e for e in run.combat.enemies if e.is_alive]) == 1
    assert not p.rules.selection and not p.rules.tasks and not p.rules.deferred_hooks
    assert card in p.hand  # Resumed draw refills from the now-discarded outer card.
    assert saved(clone(run)) == saved(run)


def test_ending_combat_cancels_waiting_horn_choice_without_a_draw_or_extra_rng():
    # Five native-style random hits: Phrog, then all four children. This fixture
    # changes only the hit count to force the combat-ending boundary in one play.
    definition = DEFAULT_CARDS.definition("sword_boomerang")
    from game.headless.cards.effects import RandomEnemyAttack

    replacement = replace(definition, effects=(RandomEnemyAttack(5, 5),))
    catalog = CardCatalog(replacement if d is definition else d for d in DEFAULT_CARDS.definitions)
    run, card = setup(strength=100, fillers=8, cards=catalog)
    combat = run.combat
    combat.apply(PlayCard(card.instance_id))
    p = combat.player
    assert combat.done and combat.winner == "player"
    assert not p.rules.selection and not p.rules.deferred_hooks and not p.rules.tasks
    assert p.rules.active_hook == 0 and not p.rules.plays
    assert len(p.hand) == 3  # The final kill has no Horn callback; queued first draw is canceled.
    assert p.rules.hook_sequence == 4
    assert saved(clone(run)) == saved(run)


def seeker_hooks(*, replay=False):
    definition = DEFAULT_CARDS.definition("sword_boomerang")
    catalog = CardCatalog(
        (
            replace(d, levels=tuple(replace(level, base_damage=100) for level in d.levels))
            if d is definition
            else d
        )
        for d in DEFAULT_CARDS.definitions
    )
    run, card = setup(
        cards=catalog,
        fillers=["defend", "seeker_strike", "seeker_strike", "defend", "bash", "anger", "strike", "defend"],
    )
    p = run.combat.player
    p.rules.powers.pop("stratagem")
    apply_power(p, "hellraiser", 1)
    seekers = [c for c in p.deck.discard_pile if c.definition.definition_id == "seeker_strike"]
    first = next(c for c in p.deck.discard_pile if c.definition.definition_id == "defend")
    if replay:
        seekers[0].combat_state.replay_count = 1
    order = [first, *seekers] + [c for c in p.deck.discard_pile if c not in [first, *seekers]]
    p.deck.draw_pile, p.deck.discard_pile = list(reversed(order)), []
    run.apply(PlayCard(card.instance_id))
    return run, seekers


def test_nested_seeker_plays_keep_contexts_and_choices_in_fifo_order():
    run, seekers = seeker_hooks()
    p = run.combat.player
    assert [c.instance_id for c in p.deck.in_play] == [c.instance_id for c in seekers]
    assert p.current_card is seekers[0]  # The newest in-play card is parked.
    assert p.rules.selection["source"] == seekers[0].instance_id
    assert p.rules.deferred_hooks[0]["selection"]["source"] == seekers[1].instance_id
    assert not any(t[0] == "random_hit" for t in p.rules.tasks)  # Parent finished.
    other = clone(run)
    # The pinned selector filters the live draw pile by its original sample.
    # The second Seeker was sampled, but has since moved into another play.
    assert seekers[1].instance_id in p.rules.selection["whitelist"]
    assert seekers[1].instance_id not in p.rules.selection["candidates"]
    assert set(p.rules.selection["candidates"]) <= {c.instance_id for c in p.deck.draw_pile}
    for action in (ChooseCombatCard(p.rules.selection["candidates"][0]), ConfirmCombatSelection()):
        run.apply(action)
        other.apply(action)
        assert saved(run) == saved(other)
    assert p.current_card is seekers[1] and p.rules.selection["source"] == seekers[1].instance_id
    assert not p.rules.deferred_hooks and seekers[0] in p.deck.discard_pile
    fresh = clone(run)
    finish_choices(run, fresh)
    finish_choices(other, clone(other))
    assert saved(run) == saved(other)
    assert not p.deck.in_play and not p.rules.plays and p.rules.active_hook == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_context",
        "foreign_play_context",
        "cross_context_task",
        "foreign_source",
        "selected_while_waiting",
        "missing_choice",
        "invalid_task",
        "unowned_hook",
    ],
)
def test_malformed_deferred_ownership_is_rejected_atomically(mutation):
    run, seekers = seeker_hooks()
    before = saved(run)
    bad = deepcopy(before)
    rules = bad["combat"]["player"]["rules"]
    hook = rules["deferred_hooks"][0]
    if mutation == "duplicate_context":
        hook["context"] = rules["active_hook"]
    elif mutation == "foreign_play_context":
        rules["plays"][seekers[1].instance_id]["context"] = rules["hook_sequence"] + 1
    elif mutation == "cross_context_task":
        hook["tasks"][0][1] = seekers[0].instance_id
    elif mutation == "foreign_source":
        hook["selection"]["source"] = seekers[0].instance_id
    elif mutation == "selected_while_waiting":
        hook["selection"]["selected"] = hook["selection"]["candidates"][:1]
    elif mutation == "missing_choice":
        hook["selection"] = None
    elif mutation == "invalid_task":
        hook["tasks"].append(["execute_callback", "anything"])
    else:
        rules["relics"] = [r for r in rules["relics"] if r["definition_id"] != "gremlin_horn"]
    with pytest.raises(ValueError):
        run.restore(bad)
    assert saved(run) == before


def test_repeated_choice_keeps_active_hook_ahead_of_already_waiting_hooks():
    run, seekers = seeker_hooks(replay=True)
    p = run.combat.player
    context = p.rules.active_hook
    waiting = deepcopy(p.rules.deferred_hooks)
    other = clone(run)
    chosen = p.rules.selection["candidates"][0]
    for action in (ChooseCombatCard(chosen), ConfirmCombatSelection()):
        run.apply(action)
        other.apply(action)
        assert saved(run) == saved(other)
    assert p.rules.selection["source"] == seekers[0].instance_id
    assert p.rules.active_hook == context and p.rules.deferred_hooks == waiting
    assert p.rules.plays[seekers[0].instance_id]["remaining"] == 1
    finish_choices(run, other)
    assert not p.rules.plays and not p.rules.deferred_hooks


def test_outer_card_selector_blocks_detached_hook_and_preserves_pending_card_owner():
    from game.headless.cards.effects import SelectHandCard

    definition = DEFAULT_CARDS.definition("strike")
    replacement = replace(definition, effects=(Attack(), SelectHandCard("upgrade")))
    catalog = CardCatalog(replacement if d is definition else d for d in DEFAULT_CARDS.definitions)
    run, card = setup(cards=catalog, outer="strike", fillers=5)
    p = run.combat.player
    p.hand.extend(p.deck.discard_pile[:2])
    del p.deck.discard_pile[:2]
    run.apply(PlayCard(card.instance_id, 0))
    assert p.pending_play and p.rules.selection is None and p.current_card is card
    assert p.rules.active_hook == 0 and len(p.rules.deferred_hooks) == 1
    assert len(run.combat.enemies) == 5
    other = clone(run)
    action = ChooseCombatCard(p.pending_options()[0])
    run.apply(action)
    other.apply(action)
    assert saved(run) == saved(other)
    assert p.pending_play is None and p.rules.active_hook == 1
    assert p.rules.selection["source"] == "stratagem"
    finish_choices(run, other)
