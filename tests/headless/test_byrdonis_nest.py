"""Byrdonis Nest, egg ownership, Hatch, and colorless deck interactions."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from game.headless.cards.catalog import CardCatalog, DEFAULT_CARDS
from game.headless.core.snapshots import card_record
from game.headless.core.actions import EndTurn, PlayCard
from game.headless.enchantments.base import enchant
from game.headless.events.eligibility import entry_conditions
from game.headless.events.progression import EventProgression
from game.headless.run import events, rest_site
from game.headless.run.actions import (
    ChooseEventOption, ChooseEventCard, LeaveEvent, Hatch, Rest, Smith,
    ChooseUpgrade, LeaveRest, ClaimRelic,
)
from game.headless.run.config import RunConfig
from game.headless.run.deck import add_card, remove_card
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_relic


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def step(run, action):
    clone = RunEngine(cards=run.cards)
    clone.restore(saved(run))
    assert clone.legal_actions() == run.legal_actions()
    run.apply(action)
    clone.apply(action)
    assert saved(run) == saved(clone)


def nest(**kwargs):
    run = RunEngine(**kwargs)
    events.begin(run.state, 'byrdonis_nest', cards=run.cards)
    return run


@pytest.mark.parametrize('hp', [1, 40, 80])
def test_eat_gains_seven_current_and_max_hp_once(hp):
    run = nest(hp=hp)
    deck = [card_record(c) for c in run.state.deck]
    step(run, ChooseEventOption(0, 'eat'))
    assert (run.state.hp, run.state.max_hp) == (hp + 7, 87)
    assert [card_record(c) for c in run.state.deck] == deck
    before = saved(run)
    with pytest.raises(ValueError):run.apply(ChooseEventOption(0, 'eat'))
    assert saved(run) == before
    step(run, LeaveEvent(0))


def test_take_empty_deck_then_hatch_and_play_in_next_combat():
    run = nest(card_ids=[], hp=35)
    step(run, ChooseEventOption(0, 'take'))
    egg = run.state.deck[0]
    assert egg.definition.definition_id == 'byrdonis_egg'
    assert not egg.spec.ethereal and len(egg.definition.levels) == 1
    step(run, LeaveEvent(0))
    rest_site.begin_rest_site(run.state)
    assert Hatch() in run.legal_actions() and Rest() in run.legal_actions()
    assert Smith() not in run.legal_actions()
    step(run, Hatch())
    swoop = run.state.deck[0]
    assert swoop.definition.definition_id == 'byrd_swoop' and swoop.instance_id != egg.instance_id
    assert (run.state.hp, run.state.max_hp) == (35, 80)
    assert run.legal_actions() == (LeaveRest(),)
    before = saved(run)
    with pytest.raises(ValueError):run.apply(Hatch())
    assert saved(run) == before
    step(run, LeaveRest())
    run.start_combat(encounter_id='overgrowth_nibbit')
    hp = run.combat.enemies[0].hp
    step(run, PlayCard(swoop.instance_id, 0))
    assert run.combat.enemies[0].hp == hp - 14
    assert run.combat.player.energy == 3
    assert any(c.instance_id == swoop.instance_id for c in run.combat.player.deck.discard_pile)


def test_egg_unplayable_not_ethereal_and_removable():
    run = RunEngine(card_ids=['byrdonis_egg'])
    run.start_combat(encounter_id='overgrowth_nibbit')
    assert run.legal_actions() == (EndTurn(),)
    step(run, EndTurn())
    assert not run.combat.player.deck.exhaust_pile
    assert run.combat.player.hand[0].definition.definition_id == 'byrdonis_egg'
    run = RunEngine(card_ids=['byrdonis_egg'])
    assert entry_conditions(run.state)['event_pet']
    remove_card(run.state, run.state.deck[0].instance_id)
    assert not entry_conditions(run.state)['event_pet']
    rest_site.begin_rest_site(run.state)
    assert Hatch() not in run.legal_actions()


def test_hatch_all_eggs_in_place_keeps_other_card_state_and_allows_duplicate_pet():
    run = RunEngine(card_ids=['byrdonis_egg', 'strike', 'byrdonis_egg', 'defend'])
    run.state.deck[1].upgrade()
    enchant(run.state.deck[1])
    run.state.deck[0].combats_seen = 3
    strike = card_record(run.state.deck[1])
    # A repeated event after the supported queue is exhausted can grant another egg.
    add_relic(run.state, 'byrdpip', cards=run.cards)
    for i in (0, 2):
        run.state.deck[i] = run.cards.create('byrdonis_egg', instance_id=run.state.allocate_card_id())
    rest_site.begin_rest_site(run.state)
    step(run, Smith())
    step(run, ChooseUpgrade(None))
    assert Hatch() in run.legal_actions()
    step(run, Hatch())
    assert [c.definition.definition_id for c in run.state.deck] == ['byrd_swoop', 'strike', 'byrd_swoop', 'defend']
    assert card_record(run.state.deck[1]) == strike
    assert len(run.state.relics) == 2
    assert len({r.instance_id for r in run.state.relics}) == 2
    before = saved(run)
    bad = deepcopy(before)
    bad['state']['pending']['relic_id'] = run.state.relics[0].instance_id
    bad['state']['relics'].pop()
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run) == before


def test_rest_instead_of_hatch_preserves_egg_for_later_site():
    run = RunEngine(card_ids=['byrdonis_egg'], hp=30)
    rest_site.begin_rest_site(run.state)
    step(run, Rest())
    assert run.state.hp == 54 and not run.state.relics
    step(run, LeaveRest())
    rest_site.begin_rest_site(run.state)
    assert Hatch() in run.legal_actions()


def test_missing_hatch_target_rejects_without_mutation():
    cards = CardCatalog(d for d in DEFAULT_CARDS.definitions if d.definition_id != 'byrd_swoop')
    run = RunEngine(cards=cards, card_ids=['byrdonis_egg'])
    rest_site.begin_rest_site(run.state)
    before = saved(run)
    with pytest.raises(ValueError):run.apply(Hatch())
    assert saved(run) == before


@pytest.mark.parametrize('upgrade,damage', [(0, 14), (1, 18)])
def test_swoop_uses_player_attack_modifiers(upgrade, damage):
    run = RunEngine(card_ids=['byrd_swoop'])
    if upgrade:run.state.deck[0].upgrade()
    run.start_combat(encounter_id='overgrowth_nibbit')
    player, enemy = run.combat.player, run.combat.enemies[0]
    player.strength = 2
    player.statuses.add('weak', 1)
    enemy.statuses.add('vulnerable', 1)
    hp = enemy.hp
    step(run, PlayCard(player.hand[0].instance_id, 0))
    assert enemy.hp == hp - int((damage + 2) * .75 * 1.5)
    assert player.energy == 3


@pytest.mark.parametrize('name,upgrade,value', [
    ('finesse', 0, 4), ('finesse', 1, 7),
    ('flash_of_steel', 0, 5), ('flash_of_steel', 1, 8),
])
def test_colorless_cards_draw_after_effect_without_drawing_current_play(name, upgrade, value):
    run = RunEngine(card_ids=[name])
    if upgrade:run.state.deck[0].upgrade()
    run.start_combat(encounter_id='overgrowth_nibbit')
    player, enemy = run.combat.player, run.combat.enemies[0]
    hp = enemy.hp
    step(run, PlayCard(player.hand[0].instance_id, 0 if name == 'flash_of_steel' else None))
    assert (hp - enemy.hp if name == 'flash_of_steel' else player.block) == value
    assert not player.hand and len(player.deck.discard_pile) == 1 and player.energy == 3


@pytest.mark.parametrize('source', ['byrdonis_egg', 'byrd_swoop', 'finesse', 'flash_of_steel', 'shockwave'])
@pytest.mark.parametrize('event,choice', [('aroma_of_chaos', 'let_go'), ('morphic_grove', 'group'), ('whispering_hollow', 'hug')])
def test_special_and_colorless_cards_transform_in_correct_pool(source, event, choice):
    run = RunEngine(card_ids=[source], gold=150)
    original = run.state.deck[0].instance_id
    events.begin(run.state, event)
    step(run, ChooseEventOption(0, choice))
    result = run.state.deck[0]
    from game.headless.cards.pools import COLORLESS_CARDS
    assert result.definition.definition_id in set(COLORLESS_CARDS) - {source}
    assert result.instance_id != original and result.upgrade_level == 0
    assert not entry_conditions(run.state)['event_pet']


def test_event_queue_skips_owned_egg_or_pet_but_permits_exhausted_fallback():
    for name in ('egg', 'pet', 'neither'):
        run = RunEngine(card_ids=['byrdonis_egg'] if name == 'egg' else [])
        if name == 'pet':add_relic(run.state, 'byrdpip', cards=run.cards)
        conditions = entry_conditions(run.state)
        queue = EventProgression(['byrdonis_nest', 'sapphire_seed'])
        assert queue.pull('first', conditions=conditions) == ('byrdonis_nest' if name == 'neither' else 'sapphire_seed')
        fallback = EventProgression(['byrdonis_nest'])
        assert fallback.pull('first', conditions=conditions) == 'byrdonis_nest'
        assert fallback.pull('second', conditions=conditions) == 'byrdonis_nest'


@pytest.mark.parametrize('stage', ['options', 'take', 'eat', 'hatched'])
def test_invalid_event_or_hatch_restore_is_atomic(stage):
    run = nest(card_ids=['strike'])
    if stage != 'options':step(run, ChooseEventOption(0, 'take' if stage == 'hatched' else stage))
    if stage == 'hatched':
        step(run, LeaveEvent(0))
        rest_site.begin_rest_site(run.state)
        step(run, Hatch())
    before = saved(run)
    bad = deepcopy(before)
    if stage == 'hatched':bad['state']['deck'][-1]['upgrade_level'] = 1
    else:bad['state']['pending']['data']['initial_hp'] -= 1
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run) == before


def test_reward_pet_pickup_uses_owned_custom_card_catalog_and_missing_target_is_atomic():
    for missing in (False, True):
        definitions = [d for d in DEFAULT_CARDS.definitions if d.definition_id != 'byrd_swoop']
        if not missing:
            swoop = DEFAULT_CARDS.definition('byrd_swoop')
            definitions.append(replace(swoop, levels=tuple(replace(s, base_damage=22) for s in swoop.levels)))
        run = RunEngine(cards=CardCatalog(definitions), card_ids=['byrdonis_egg'], config=RunConfig(reward_relics=('byrdpip',)))
        run.start_combat(encounter_id='overgrowth_byrdonis')
        for enemy in run.combat.enemies:enemy.take_damage(10000, is_attack=False)
        run.combat.resolve_external_effect()
        run.finish_combat()
        if missing:
            before = saved(run)
            with pytest.raises(ValueError):run.apply(ClaimRelic())
            assert saved(run) == before
        else:
            step(run, ClaimRelic())
            assert run.state.deck[0].spec.base_damage == 22


@pytest.mark.parametrize('name', ['finesse', 'flash_of_steel'])
def test_colorless_draws_one_available_card(name):
    run = RunEngine(card_ids=[name, 'defend'])
    run.start_combat(encounter_id='overgrowth_nibbit')
    deck = run.combat.player.deck
    card = next(c for c in deck.hand if c.definition.definition_id == name)
    other = next(c for c in deck.hand if c is not card)
    deck.hand, deck.draw_pile = [card], [other]
    step(run, PlayCard(card.instance_id, 0 if name == 'flash_of_steel' else None))
    assert [c.instance_id for c in deck.hand] == [other.instance_id]
    assert not deck.draw_pile


def test_wellspring_can_remove_egg_and_missing_colorless_pool_rejects_event_atomically():
    run = RunEngine(card_ids=['byrdonis_egg'])
    events.begin(run.state, 'wellspring')
    step(run, ChooseEventOption(0, 'bathe'))
    assert [c.definition.definition_id for c in run.state.deck] == ['guilty']
    assert not entry_conditions(run.state)['event_pet']
    cards = CardCatalog(d for d in DEFAULT_CARDS.definitions if d.definition_id != 'finesse')
    run = RunEngine(cards=cards, card_ids=['byrdonis_egg'])
    before = saved(run)
    with pytest.raises(ValueError):events.begin(run.state, 'aroma_of_chaos', cards=cards)
    assert saved(run) == before
