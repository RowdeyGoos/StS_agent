"""Pinned solo character starts and native character-pool declaration order."""
from dataclasses import dataclass
from types import MappingProxyType

@dataclass(frozen=True, slots=True)
class Character:
    max_hp: int
    deck: tuple[str, ...]
    relic: str
    orb_slots: int
    relic_pool: tuple[str, ...]
    potion_pool: tuple[str, ...]

CHARACTERS = MappingProxyType({
    'ironclad': Character(80, ('strike', 'strike', 'strike', 'strike', 'strike', 'defend', 'defend', 'defend', 'defend', 'bash'), 'burning_blood', 0, ('brimstone', 'burning_blood', 'charons_ashes', 'demon_tongue', 'paper_phrog', 'red_skull', 'ruined_helmet', 'self_forming_clay'), ('blood_potion', 'soldiers_stew', 'ashwater')),
    'silent': Character(70, ('strike_silent', 'strike_silent', 'strike_silent', 'strike_silent', 'strike_silent', 'defend_silent', 'defend_silent', 'defend_silent', 'defend_silent', 'defend_silent', 'neutralize', 'survivor'), 'ring_of_the_snake', 0, ('helical_dart', 'ninja_scroll', 'paper_krane', 'ring_of_the_snake', 'snecko_skull', 'tingsha', 'tough_bandages', 'twisted_funnel'), ('poison_potion', 'ghost_in_a_jar', 'cunning_potion')),
    'regent': Character(75, ('strike_regent', 'strike_regent', 'strike_regent', 'strike_regent', 'defend_regent', 'defend_regent', 'defend_regent', 'defend_regent', 'falling_star', 'venerate'), 'divine_right', 0, ('divine_right', 'fencing_manual', 'galactic_dust', 'lunar_pastry', 'mini_regent', 'orange_dough', 'regalite', 'vitruvian_minion'), ('star_potion', 'cosmic_concoction', 'kings_courage')),
    'necrobinder': Character(66, ('strike_necrobinder', 'strike_necrobinder', 'strike_necrobinder', 'strike_necrobinder', 'defend_necrobinder', 'defend_necrobinder', 'defend_necrobinder', 'defend_necrobinder', 'bodyguard', 'unleash'), 'bound_phylactery', 0, ('big_hat', 'bone_flute', 'book_repair_knife', 'bookmark', 'bound_phylactery', 'funerary_mask', 'ivory_tile', 'undying_sigil'), ('potion_of_doom', 'pot_of_ghouls', 'bone_brew')),
    'defect': Character(75, ('strike_defect', 'strike_defect', 'strike_defect', 'strike_defect', 'defend_defect', 'defend_defect', 'defend_defect', 'defend_defect', 'zap', 'dualcast'), 'cracked_core', 3, ('cracked_core', 'data_disk', 'emotion_chip', 'gold_plated_cables', 'power_cell', 'metronome', 'runic_capacitor', 'symbiotic_virus'), ('focus_potion', 'essence_of_darkness', 'potion_of_capacity')),
})
STARTER_UPGRADES = MappingProxyType(dict(zip(
    ('burning_blood', 'ring_of_the_snake', 'divine_right', 'bound_phylactery', 'cracked_core'),
    ('black_blood', 'ring_of_the_drake', 'divine_destiny', 'phylactery_unbound', 'infused_core'))))


def definition(name):
    if not isinstance(name, str) or name not in CHARACTERS:
        raise ValueError('Unsupported solo character.')
    return CHARACTERS[name]


def character(owner):
    if hasattr(owner, 'rules'):
        return owner.rules.character
    config = getattr(owner, 'config', None)
    return config.character if config else 'ironclad'


def reward_cards(name, *, rare=False):
    from game.headless.cards.catalog import DEFAULT_CARDS
    return tuple(d.definition_id for rarity in (('rare',) if rare else ('common', 'uncommon', 'rare'))
                 for d in DEFAULT_CARDS.definitions if d.pool == name and d.rarity == rarity)


def card_order(name):
    from game.headless.core import content_order
    if name == 'ironclad':
        return content_order.IRONCLADCARDPOOL
    from game.headless.generation.foreign import ORDINARY
    return ORDINARY[name]


def potion_pool(name):
    from game.headless.core.content_order import SHAREDPOTIONPOOL
    return (*definition(name).potion_pool, *SHAREDPOTIONPOOL)


def relic_pool(name, *, shop=False):
    from game.headless.core.content_order import SHAREDRELICPOOL
    from game.headless.relics.base import RELICS
    from game.headless.relics.eligibility import SHOP_EXCLUDED
    rarities = ('common', 'uncommon', 'rare', 'shop') if shop else ('common', 'uncommon', 'rare')
    return tuple(n for n in (*SHAREDRELICPOOL, *definition(name).relic_pool)
                 if RELICS[n].rarity in rarities and (not shop or n not in SHOP_EXCLUDED))


def ancient_cards(name, cards):
    definition(name)
    replacement = {'ironclad':'break', 'silent':'suppress', 'regent':'meteor_shower',
                   'necrobinder':'protector', 'defect':'quadcast'}[name]
    return tuple(d for d in cards.definitions if d.pool == name and d.rarity == 'ancient' and d.definition_id != replacement)
