"""Restore of offered-card choices whose eligibility depends on the owning character.

`restore_rules` validates the saved selection before it installs the restored
rules on the player, so these checks must take the character from the record
being validated, not from the player's placeholder rules.
"""

import json

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.characters import CHARACTERS
from game.headless.core.actions import PlayCard
from game.headless.generation.combat import card_pool
from game.headless.generation.foreign import splash_pool
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_relic
from game.headless.run.state import RunConfig


def saved(engine):
    return json.loads(json.dumps(engine.snapshot()))


def restored(snapshot):
    engine = RunEngine()
    engine.restore(json.loads(json.dumps(snapshot)))
    return engine


def start(character, *, relic=None, cards=None, seed=2):
    run = RunEngine(seed=seed, config=RunConfig(character=character), card_ids=cards)
    if relic is not None:
        add_relic(run.state, relic)
    run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=1000), cards_per_turn=5)
    return run


def start_splash(character, seed):
    run = start(character, cards=["splash"] * 3, seed=seed)
    run.apply(next(a for a in run.legal_actions() if isinstance(a, PlayCard)))
    return run


def offered_ids(run):
    return [c.definition.definition_id for c in run.combat.player.deck.offered]


def pool_ids(family, kind=None):
    return {d.definition_id for d in card_pool(DEFAULT_CARDS, family, kind)}


def assert_branches_match(build):
    """Every legal action gives the same state in a never-restored engine and its restore."""
    snapshot = saved(build())
    clone = restored(snapshot)
    assert saved(clone) == snapshot
    actions = build().legal_actions()
    assert clone.legal_actions() == actions
    for action in actions:
        live, twin = build(), restored(snapshot)
        assert saved(live) == snapshot
        live.apply(action)
        twin.apply(action)
        assert saved(twin) == saved(live)
        assert twin.legal_actions() == live.legal_actions()


@pytest.mark.parametrize("character", CHARACTERS)
def test_choices_paradox_offer_restores_for_every_character(character):
    run = start(character, relic="choices_paradox")
    selection = run.combat.player.rules.selection
    assert selection is not None
    assert selection["candidates"] == [c.instance_id for c in run.combat.player.deck.offered]
    assert len(set(offered_ids(run))) == 5 and set(offered_ids(run)) <= pool_ids(character)
    assert_branches_match(lambda: start(character, relic="choices_paradox"))


@pytest.mark.parametrize("character", CHARACTERS)
def test_splash_offer_restores_for_every_character(character):
    seeds = range(1, 7)
    offers = set()
    for seed in seeds:
        run = start_splash(character, seed)
        assert run.combat.player.rules.selection is not None
        offers.update(offered_ids(run))
        assert_branches_match(lambda: start_splash(character, seed))
    eligible = {d.definition_id for d in splash_pool(DEFAULT_CARDS, character)}
    assert offers <= eligible and not offers & pool_ids(character)
    if character != "ironclad":
        # The placeholder rules name Ironclad; these seeds offer an Ironclad attack.
        assert offers & pool_ids("ironclad")


@pytest.mark.parametrize("relic", ["toolbox", "gambling_chip"])
@pytest.mark.parametrize("character", CHARACTERS)
def test_neighbouring_relic_choices_restore_for_every_character(character, relic):
    run = start(character, relic=relic)
    assert run.combat.player.rules.selection is not None
    assert_branches_match(lambda: start(character, relic=relic))


def paradox_snapshot(character):
    snapshot = saved(start(character, relic="choices_paradox"))
    restored(snapshot)  # The untampered snapshot is accepted.
    return snapshot


def offers_of(snapshot):
    return snapshot["combat"]["deck"]["piles"]["offered"]


def foreign_definitions(character, count, exclude=()):
    other = "silent" if character == "ironclad" else "ironclad"
    return sorted(pool_ids(other) - pool_ids(character) - set(exclude))[:count]


def drop_last_offer(snapshot, character):
    removed = offers_of(snapshot).pop()
    candidates = snapshot["combat"]["player"]["rules"]["selection"]["candidates"]
    candidates.remove(removed["instance_id"])


def duplicate_definition(snapshot, character):
    offers = offers_of(snapshot)
    offers[1]["definition_id"] = offers[0]["definition_id"]


def one_foreign_offer(snapshot, character):
    offers = offers_of(snapshot)
    offers[0]["definition_id"] = foreign_definitions(character, 1, [o["definition_id"] for o in offers])[0]


def all_offers_from_placeholder_pool(snapshot, character):
    # Accepted before the fix for every non-Ironclad owner: it checked Ironclad's pool.
    offers = offers_of(snapshot)
    for offer, definition in zip(offers, foreign_definitions(character, len(offers))):
        offer["definition_id"] = definition


def basic_card_offer(snapshot, character):
    offers_of(snapshot)[0]["definition_id"] = "strike"


def missing_retain(snapshot, character):
    offers_of(snapshot)[2]["combat_state"]["retain_this_combat"] = False


@pytest.mark.parametrize(
    "tamper",
    [drop_last_offer, duplicate_definition, one_foreign_offer, all_offers_from_placeholder_pool,
     basic_card_offer, missing_retain],
)
@pytest.mark.parametrize("character", CHARACTERS)
def test_tampered_choices_paradox_offers_are_rejected(character, tamper):
    snapshot = paradox_snapshot(character)
    tamper(snapshot, character)
    with pytest.raises(ValueError, match="Invalid Choices Paradox offers"):
        restored(snapshot)


@pytest.mark.parametrize("character", [c for c in CHARACTERS if c != "ironclad"])
def test_splash_offer_from_owner_pool_is_rejected(character):
    # Accepted before the fix: the placeholder owner excluded Ironclad, not the real owner.
    snapshot = saved(start_splash(character, 1))
    restored(snapshot)
    offer = offers_of(snapshot)[0]
    taken = {o["definition_id"] for o in offers_of(snapshot)}
    offer["definition_id"] = sorted(pool_ids(character, "attack") - taken)[0]
    with pytest.raises(ValueError, match="Invalid Splash attack offers"):
        restored(snapshot)
