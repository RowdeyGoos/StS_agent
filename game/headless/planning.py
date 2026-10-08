"""Restricted combat reconstruction from plain, observable facts.

This is a capability, not a snapshot sanitizer. No live engine is accepted. The
allowlists cover whole future transitions, unlike the immediate attack preview.
Unknown dependencies must be added with conformance cases before being enabled.
"""
from dataclasses import asdict

from game.headless.combat_preview import _card, UnknownPreview
from game.headless.core.combat import CombatEngine
from game.headless.core.deck import Deck
from game.headless.core.player import Player
from game.headless.core.native_service import COMBAT_STREAMS
from game.headless.powers.status import StatusCollection
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run.state import RunPhase
from game.headless.relics.base import RelicInstance
from game.headless.potions.base import PotionInstance
from game.headless.monsters.vantom import Vantom
from game.headless.monsters.overgrowth import SimpleEnemy, Nibbit, LeafSlimeMedium, TwigSlimeSmall
from game.headless.monsters.underdocks_normal import Seapunk, SludgeSpinner


class UnsupportedSearch(ValueError):
    """An observable dependency cannot be reconstructed by this capability."""


CARDS = frozenset('''strike defend bash anger twin_strike pommel_strike
shrug_it_off thunderclap iron_wave sword_boomerang
bludgeon body_slam whirlwind uppercut true_grit burning_pact
flame_barrier impervious inflame demon_form barricade feel_no_pain
dark_embrace rage battle_trance offering
bloodletting rampage perfected_strike headbutt wound dazed slimed burn clumsy'''.split())
RELICS = frozenset('''burning_blood blood_vial anchor horn_cleat captains_wheel
vajra oddly_smooth_stone strawberry pear bag_of_marbles bronze_scales
orichalcum bag_of_preparation strike_dummy the_boot hand_drill chemical_x
lantern regal_pillow meal_ticket juzu_bracelet potion_belt war_paint
whetstone molten_egg toxic_egg prayer_wheel white_beast_statue'''.split())
# These Neow relics act only on pickup. Their completed effects (gold, maximum
# HP and upgrades) are already explicit public facts at a combat opening.
RELICS = RELICS | frozenset(('golden_pearl', 'nutritious_oyster', 'neows_talisman'))
POWERS = frozenset('''dexterity vigor thorns plating barricade temporary_strength
temporary_dexterity ritual regen strength dark_embrace demon_form feel_no_pain
flame_barrier rage no_draw metallicize'''.split())
ENEMY_POWERS = frozenset('slippery vulnerable weak frail artifact shrink'.split())
POTIONS = frozenset('''fire_potion block_potion strength_potion dexterity_potion
energy_potion swift_potion explosive_ampoule flex_potion
weak_potion blood_potion gamblers_brew cure_all fysh_oil'''.split())
PLAYER_STATUSES = frozenset('weak vulnerable frail shrink artifact'.split())
MONSTERS = {c.__name__: c for c in (Vantom, SimpleEnemy, Nibbit, LeafSlimeMedium, TwigSlimeSmall, Seapunk, SludgeSpinner)}


def validate_inventory(facts):
    """Check current and previously observed sources, including consumed items."""
    # The inventory check also catches a previously exhausted source.
    descriptions = [c for pile in facts['piles'].values() for c in pile] + facts['deck']
    for c in descriptions:
        if c['definition_id'] not in CARDS:
            raise UnsupportedSearch('card:' + c['definition_id'])
        if set(c['flags']) - {'is_dupe', 'extra_damage'} or c['enchantment'] is not None:
            raise UnsupportedSearch('card_provenance')
    names = {c['definition_id'] for c in descriptions}
    if {'headbutt', 'dark_embrace'} <= names:
        # Ethereal exhaust draws can occur before the public end-turn hand is
        # discarded. This slice cannot infer how many known positions they used.
        raise UnsupportedSearch('unobserved_placement_draw_interaction')
    for r in facts['relics']:
        if r['definition_id'] not in RELICS or r['melted']:
            raise UnsupportedSearch('relic:' + r['definition_id'])
    for potion in facts['potions']:
        if potion and potion['definition_id'] not in POTIONS:
            raise UnsupportedSearch('potion:' + potion['definition_id'])


def reconstruct(facts, *, seed, enemy_phases):
    """Return a fresh run with independent native simulation streams.

The caller supplies *inferred* phases, then checks the complete projected root.
Display-only costs cannot substitute for the engine's future cost semantics.
"""
    if facts['character'] != 'ironclad' or facts['ascension'] != 0:
        raise UnsupportedSearch('character_or_ascension')
    if facts['selection'] or facts['resources'] or facts['stars']:
        raise UnsupportedSearch('pending_root')
    if any(name not in POWERS | PLAYER_STATUSES for name in facts['powers']):
        raise UnsupportedSearch('player_power')
    validate_inventory(facts)
    if any(facts['piles'].get(n) for n in ('in_play', 'offered', 'sequestered')):
        raise UnsupportedSearch('active_card_work')
    run = RunEngine(seed=seed, card_ids=[], max_hp=facts['player']['max_hp'],
                    hp=facts['player']['hp'], gold=facts['gold'], config=RunConfig(), rng_profile='native')
    streams = {name: run.state.rng.stream(name) for name in COMBAT_STREAMS}
    p = Player(Deck([], streams['shuffle'], streams=streams), max_hp=run.state.max_hp)
    p.catalog = run.cards
    for name in ('hp', 'block', 'energy', 'strength'):
        setattr(p, name, facts['player'][name])
    for name, amount in facts['powers'].items():
        if name in PLAYER_STATUSES:
            # Supported sources apply timed debuffs on the enemy side; its
            # completed duration tick already consumed any skip-first flag.
            p.statuses.add(name, amount)
        else:
            p.rules.powers[name] = amount
    p.rules.round_number = facts['player']['round']
    p.cards_played_this_turn = facts['plays_this_turn']
    p.rules.room_kind = facts['room_kind']
    p.rules.gold_available = facts['gold']
    refs = {}
    try:
        run.state.deck = [_card(c, 'run.card.' + str(i)) for i, c in enumerate(facts['deck'])]
        for i, value in enumerate(facts['deck']):
            refs[value['ref']] = ('deck', run.state.deck[i].instance_id)
        for pile, values in facts['piles'].items():
            cards = []
            for value in values:
                card = _card(value, 'combat.' + str(len(refs)))
                if p.card_cost(card) != value['energy'] or p.star_cost(card) != value['stars']:
                    raise UnsupportedSearch('card_cost_provenance')
                refs[value['ref']] = ('combat', card.instance_id)
                cards.append(card)
            setattr(p.deck, pile, cards)
    except UnknownPreview as error:
        raise UnsupportedSearch(str(error)) from error
    p.deck._allocated_ids = {c.instance_id for c in p.deck.all_cards()}
    p.deck.original_ids = {c.instance_id for c in p.deck.all_cards() if not c.combat_state.is_dupe}
    p.deck._next_instance_id = len(refs)
    top, bottom = [], []
    for field, destination in (('known_top', top), ('known_bottom', bottom)):
        for ref in facts.get(field, ()):
            if ref not in refs:
                raise UnsupportedSearch('inconsistent_known_draw')
            identity = refs[ref][1]
            card = next((c for c in p.deck.draw_pile if c.instance_id == identity), None)
            if card is None:
                raise UnsupportedSearch('inconsistent_known_draw')
            p.deck.draw_pile.remove(card)
            destination.append(card)
    streams['shuffle'].shuffle(p.deck.draw_pile)
    # Stack convention: pop from the end. Both inputs are nearest-end first.
    p.deck.draw_pile = bottom + p.deck.draw_pile + list(reversed(top))
    run.state.relics = [RelicInstance(r['definition_id'], 'run.item.' + str(i))
                        for i, r in enumerate(facts['relics'])]
    for r, instance in zip(facts['relics'], run.state.relics):
        refs[r['ref']] = ('relic', instance.instance_id)
    p.rules.relics = [asdict(r) for r in run.state.relics]
    p.rules.relic_data = {r.instance_id: {} for r in run.state.relics}
    run.state.potion_capacity = len(facts['potions'])
    run.state.potions = [None if v is None else PotionInstance(v['definition_id'], 'run.item.' + str(len(run.state.relics) + i))
                         for i, v in enumerate(facts['potions'])]
    for v, instance in zip(facts['potions'], run.state.potions):
        if instance:
            refs[v['ref']] = ('potion', instance.instance_id)
    p.rules.potions = [None if v is None else asdict(v) for v in run.state.potions]
    p.rules.potion_capacity = len(run.state.potions)
    p.rules.potion_slots = run.state.potions.count(None)
    combat = CombatEngine(seed=seed, cards=run.cards)
    combat.player, combat.turn = p, facts['player']['round']
    combat.native_streams, combat.rng = streams, streams['monster_ai']
    combat.enemies = []
    for value, phase in zip(facts['enemies'], enemy_phases):
        cls = MONSTERS.get(value['definition_id'])
        if cls is None:
            raise UnsupportedSearch('enemy:' + value['definition_id'])
        enemy = cls(rng=streams['monster_ai'])
        if hasattr(enemy, '_intent_index'):
            enemy._intent_index = phase
        enemy.hp, enemy.max_hp = value['hp'], value['max_hp']
        enemy.block, enemy.strength = value['block'], value['strength']
        if any(k not in ENEMY_POWERS for k in value['powers']):
            raise UnsupportedSearch('enemy_power')
        enemy.statuses = StatusCollection(dict(value['powers']))
        enemy.combat_player = p
        combat.enemies.append(enemy)
    p.combat_enemies = combat.enemies
    run.combat, run.state.phase = combat, RunPhase.COMBAT
    run.state.next_card_id = len(run.state.deck)
    run.state.next_item_id = len(refs) + 1
    return run, refs
