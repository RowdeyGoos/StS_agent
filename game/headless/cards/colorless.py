"""All 53 single-player colorless cards in native 0.107.1."""

from functools import partial
from game.headless.cards.builders import define
from game.headless.cards.effects import GainBlock, DrawCards
from game.headless.cards.operations import Attack, Power, CardOperation
from game.headless.cards.colorless_effects import ColorlessOperation as Op

card = partial(define, pool="colorless")
ALCHEMIZE = card(
    "alchemize",
    "Alchemize",
    1,
    "skill",
    "rare",
    (Op("alchemize"),),
    upgraded_cost=0,
    exhaust=True,
    generate=False,
)
ANOINTED = card(
    "anointed", "Anointed", 1, "skill", "rare", (Op("anointed"),), exhaust=True, upgraded_retain=True
)
AUTOMATION = card("automation", "Automation", 1, "power", "uncommon", (Power("automation"),), upgraded_cost=0)
BEAT_DOWN = card("beat_down", "Beat Down", 3, "skill", "rare", (Op("beat_down", 3, 4),))
BOLAS = card("bolas", "Bolas", 0, "attack", "rare", (Attack(), Op("return")), damage=3, upgraded_damage=4)
CALAMITY = card("calamity", "Calamity", 3, "power", "rare", (Power("calamity"),), upgraded_cost=2)
CATASTROPHE = card("catastrophe", "Catastrophe", 2, "skill", "uncommon", (Op("catastrophe", 2, 3),))
DARK_SHACKLES = card(
    "dark_shackles",
    "Dark Shackles",
    0,
    "skill",
    "uncommon",
    (Power("dark_shackles", 9, 15, target=True),),
    target=True,
    exhaust=True,
)
DISCOVERY = card(
    "discovery", "Discovery", 1, "skill", "uncommon", (Op("discovery"),), exhaust=True, upgraded_exhaust=False
)
DRAMATIC_ENTRANCE = card(
    "dramatic_entrance",
    "Dramatic Entrance",
    0,
    "attack",
    "uncommon",
    (Attack(all_enemies=True),),
    damage=11,
    upgraded_damage=15,
    target=False,
    exhaust=True,
    base_innate=True,
)
ENTROPY = card("entropy", "Entropy", 1, "power", "rare", (Power("entropy"),), innate=True)
EQUILIBRIUM = card(
    "equilibrium",
    "Equilibrium",
    2,
    "skill",
    "uncommon",
    (GainBlock(), Power("retain_hand")),
    block=13,
    upgraded_block=16,
)
ETERNAL_ARMOR = card("eternal_armor", "Eternal Armor", 3, "power", "rare", (Power("plating", 9, 12),))
FASTEN = card("fasten", "Fasten", 1, "power", "uncommon", (Power("fasten", 4, 6),))
FINESSE = card(
    "finesse",
    "Finesse",
    0,
    "skill",
    "uncommon",
    (GainBlock(), DrawCards()),
    block=4,
    upgraded_block=7,
    draw=1,
)
FISTICUFFS = card(
    "fisticuffs", "Fisticuffs", 1, "attack", "uncommon", (Op("fisticuffs"),), damage=7, upgraded_damage=9
)
FLASH_OF_STEEL = card(
    "flash_of_steel",
    "Flash of Steel",
    0,
    "attack",
    "uncommon",
    (Attack(), DrawCards()),
    damage=5,
    upgraded_damage=8,
    draw=1,
)
GOLD_AXE = card(
    "gold_axe", "Gold Axe", 1, "attack", "rare", (Attack(expression="plays", factor=1),), upgraded_retain=True
)
HAND_OF_GREED = card(
    "hand_of_greed",
    "Hand of Greed",
    2,
    "attack",
    "rare",
    (Op("hand_of_greed", 20, 25),),
    damage=20,
    upgraded_damage=25,
    generate=False,
)
HIDDEN_GEM = card("hidden_gem", "Hidden Gem", 1, "skill", "rare", (Op("hidden_gem", 2, 3),), generate=False)
IMPATIENCE = card("impatience", "Impatience", 0, "skill", "uncommon", (Op("impatience", 2, 3),))
JACK_OF_ALL_TRADES = card(
    "jack_of_all_trades",
    "Jack of All Trades",
    0,
    "skill",
    "uncommon",
    (Op("jack_of_all_trades", 1, 2),),
    exhaust=True,
)
JACKPOT = card(
    "jackpot", "Jackpot", 3, "attack", "rare", (Attack(), Op("jackpot", 3)), damage=25, upgraded_damage=30
)
MASTER_OF_STRATEGY = card(
    "master_of_strategy",
    "Master of Strategy",
    0,
    "skill",
    "rare",
    (DrawCards(),),
    draw=3,
    upgraded_draw=4,
    exhaust=True,
)
MAYHEM = card("mayhem", "Mayhem", 2, "power", "rare", (Power("mayhem"),), upgraded_cost=1)
MIND_BLAST = card(
    "mind_blast",
    "Mind Blast",
    1,
    "attack",
    "uncommon",
    (Attack(expression="draw_pile", factor=1),),
    upgraded_cost=0,
    base_innate=True,
)
NOSTALGIA = card("nostalgia", "Nostalgia", 1, "power", "rare", (Power("nostalgia"),), upgraded_cost=0)
OMNISLICE = card(
    "omnislice", "Omnislice", 0, "attack", "uncommon", (Op("omnislice"),), damage=8, upgraded_damage=11
)
PANACHE = card("panache", "Panache", 0, "power", "uncommon", (Power("panache", 10, 14),))
PANIC_BUTTON = card(
    "panic_button",
    "Panic Button",
    0,
    "skill",
    "uncommon",
    (GainBlock(), Power("no_block", 2)),
    block=30,
    upgraded_block=40,
    exhaust=True,
)
PREP_TIME = card("prep_time", "Prep Time", 1, "power", "uncommon", (Power("prep_time", 4, 6),))
PRODUCTION = card(
    "production", "Production", 0, "skill", "uncommon", (CardOperation("energy", 2, 3),), exhaust=True
)
PROLONG = card(
    "prolong", "Prolong", 0, "skill", "uncommon", (Op("prolong"),), exhaust=True, upgraded_exhaust=False
)
PROWESS = card(
    "prowess", "Prowess", 1, "power", "uncommon", (Power("strength", 1, 2), Power("dexterity", 1, 2))
)
PURITY = card("purity", "Purity", 0, "skill", "uncommon", (Op("purity", 3, 5),), retain=True, exhaust=True)
REND = card(
    "rend",
    "Rend",
    2,
    "attack",
    "rare",
    (Attack(expression="debuffs", factor=5, upgraded_factor=8),),
    damage=15,
    upgraded_damage=18,
)
RESTLESSNESS = card(
    "restlessness", "Restlessness", 0, "skill", "uncommon", (Op("restlessness", 2, 3),), retain=True
)
ROLLING_BOULDER = card(
    "rolling_boulder", "Rolling Boulder", 3, "power", "rare", (Power("rolling_boulder", 5, 10),)
)
SALVO = card(
    "salvo", "Salvo", 1, "attack", "rare", (Attack(), Power("retain_hand")), damage=12, upgraded_damage=16
)
SCRAWL = card("scrawl", "Scrawl", 1, "skill", "rare", (Op("scrawl"),), exhaust=True, upgraded_retain=True)
SECRET_TECHNIQUE = card(
    "secret_technique",
    "Secret Technique",
    0,
    "skill",
    "rare",
    (Op("secret_technique"),),
    exhaust=True,
    upgraded_exhaust=False,
)
SECRET_WEAPON = card(
    "secret_weapon",
    "Secret Weapon",
    0,
    "skill",
    "rare",
    (Op("secret_weapon"),),
    exhaust=True,
    upgraded_exhaust=False,
)
SEEKER_STRIKE = card(
    "seeker_strike",
    "Seeker Strike",
    1,
    "attack",
    "uncommon",
    (Attack(), Op("seeker_strike")),
    damage=9,
    upgraded_damage=12,
    strike=True,
)
SHOCKWAVE = card("shockwave", "Shockwave", 2, "skill", "uncommon", (Op("shockwave", 3, 5),), exhaust=True)
SPLASH = card("splash", "Splash", 1, "skill", "uncommon", (Op("splash"),))
STRATAGEM = card("stratagem", "Stratagem", 1, "power", "uncommon", (Power("stratagem"),), upgraded_cost=0)
THE_BOMB = card("the_bomb", "The Bomb", 2, "skill", "uncommon", (Power("the_bomb", 40, 50),))
THE_GAMBIT = card(
    "the_gambit",
    "The Gambit",
    0,
    "skill",
    "rare",
    (GainBlock(), Power("the_gambit")),
    block=50,
    upgraded_block=75,
)
THINKING_AHEAD = card(
    "thinking_ahead",
    "Thinking Ahead",
    0,
    "skill",
    "uncommon",
    (DrawCards(), Op("thinking_ahead")),
    draw=2,
    exhaust=True,
    upgraded_exhaust=False,
)
THRUMMING_HATCHET = card(
    "thrumming_hatchet",
    "Thrumming Hatchet",
    1,
    "attack",
    "uncommon",
    (Attack(), Op("return")),
    damage=11,
    upgraded_damage=14,
)
ULTIMATE_DEFEND = card(
    "ultimate_defend",
    "Ultimate Defend",
    1,
    "skill",
    "uncommon",
    (GainBlock(),),
    block=11,
    upgraded_block=15,
    defend=True,
)
ULTIMATE_STRIKE = card(
    "ultimate_strike",
    "Ultimate Strike",
    1,
    "attack",
    "uncommon",
    (Attack(),),
    damage=14,
    upgraded_damage=20,
    strike=True,
)
VOLLEY = card(
    "volley",
    "Volley",
    0,
    "attack",
    "uncommon",
    (Op("volley"),),
    damage=10,
    upgraded_damage=14,
    x=True,
    target=False,
)

DEFINITIONS = (
    ALCHEMIZE,
    ANOINTED,
    AUTOMATION,
    BEAT_DOWN,
    BOLAS,
    CALAMITY,
    CATASTROPHE,
    DARK_SHACKLES,
    DISCOVERY,
    DRAMATIC_ENTRANCE,
    ENTROPY,
    EQUILIBRIUM,
    ETERNAL_ARMOR,
    FASTEN,
    FINESSE,
    FISTICUFFS,
    FLASH_OF_STEEL,
    GOLD_AXE,
    HAND_OF_GREED,
    HIDDEN_GEM,
    IMPATIENCE,
    JACK_OF_ALL_TRADES,
    JACKPOT,
    MASTER_OF_STRATEGY,
    MAYHEM,
    MIND_BLAST,
    NOSTALGIA,
    OMNISLICE,
    PANACHE,
    PANIC_BUTTON,
    PREP_TIME,
    PRODUCTION,
    PROLONG,
    PROWESS,
    PURITY,
    REND,
    RESTLESSNESS,
    ROLLING_BOULDER,
    SALVO,
    SCRAWL,
    SECRET_TECHNIQUE,
    SECRET_WEAPON,
    SEEKER_STRIKE,
    SHOCKWAVE,
    SPLASH,
    STRATAGEM,
    THE_BOMB,
    THE_GAMBIT,
    THINKING_AHEAD,
    THRUMMING_HATCHET,
    ULTIMATE_DEFEND,
    ULTIMATE_STRIKE,
    VOLLEY,
)
