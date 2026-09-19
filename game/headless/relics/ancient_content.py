"""Pinned solo Ancient relic inventory and immutable definition construction."""

ANCIENT_ADDITIONS = ('alchemical_coffer', 'archaic_tooth', 'astrolabe', 'beautiful_bracelet', 'biiig_hug', 'black_star', 'blessed_antler', 'blood_soaked_rose', 'brilliant_scarf', 'calling_bell', 'choices_paradox', 'claws', 'crossbow', 'delicate_frond', 'diamond_diadem', 'distinguished_cape', 'driftwood', 'dusty_tome', 'ectoplasm', 'electric_shrymp', 'empty_cage', 'fiddle', 'fur_coat', 'glass_eye', 'glitter', 'golden_compass', 'iron_club', 'jeweled_mask', 'jewelry_box', 'lords_parasol', 'meat_cleaver', 'music_box', 'nutritious_soup', 'paels_blood', 'paels_claw', 'paels_eye', 'paels_flesh', 'paels_growth', 'paels_horn', 'paels_legion', 'paels_tears', 'paels_tooth', 'paels_wing', 'pandoras_box', 'philosophers_stone', 'preserved_fog', 'prismatic_gem', 'pumpkin_candle', 'radiant_pearl', 'runic_pyramid', 'sai', 'sand_castle', 'sea_glass', 'seal_of_gold', 'sere_talon', 'signet_ring', 'snecko_eye', 'sozu', 'spiked_gauntlets', 'storybook', 'tanxs_whistle', 'throwing_axe', 'toasty_mittens', 'touch_of_orobas', 'toy_box', 'tri_boomerang', 'velvet_choker', 'war_hammer', 'whispering_earring', 'yummy_cookie')


def definitions(relic_type):
    result = {n: relic_type(n, rarity="ancient") for n in ANCIENT_ADDITIONS}
    for name in ("iron_club", "paels_wing", "pumpkin_candle", "toy_box"):
        result[name] = relic_type(name, rarity="ancient", counter_limit=2**31-1)
    result['paels_legion'] = relic_type('paels_legion', rarity='ancient', adds_pet=True)
    result['signet_ring'] = relic_type('signet_ring', rarity='ancient', pickup_gold=999)
    result['black_blood'] = relic_type('black_blood', rarity='starter', victory_heal=12)
    return result


MEMORY = {
    "fur_coat": {"active": "bool"},
    'brilliant_scarf': {'turn_manual': 2**31-1},
    'diamond_diadem': {'turn_plays': 2**31-1, 'protected': 'bool'},
    'music_box': {'turn_used': 'bool', 'triggering_card': 'card'},
    'paels_eye': {'used': 'bool', 'extra_turn': 'bool', 'turn_manual': 2**31-1},
    'paels_legion': {'cooldown': 2, 'triggering_card': 'card'},
    'paels_tears': {'stored': 'bool'},
    'throwing_axe': {'used': 'bool'},
    'velvet_choker': {'turn_plays': 2**31-1},
    'whispering_earring': {'active': 'bool'},
}
