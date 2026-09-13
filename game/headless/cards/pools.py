"""Single-player Ironclad acquisition pools, derived from explicit content metadata."""

from game.headless.cards.catalog import DEFAULT_CARDS

IRONCLAD_CARDS = tuple(d.definition_id for d in DEFAULT_CARDS.definitions if d.pool == "ironclad")
COMMON_CARDS = tuple(
    d.definition_id for d in DEFAULT_CARDS.definitions if d.pool == "ironclad" and d.rarity == "common"
)
UNCOMMON_CARDS = tuple(
    d.definition_id for d in DEFAULT_CARDS.definitions if d.pool == "ironclad" and d.rarity == "uncommon"
)
RARE_CARDS = tuple(
    d.definition_id for d in DEFAULT_CARDS.definitions if d.pool == "ironclad" and d.rarity == "rare"
)
REWARD_CARDS = (*COMMON_CARDS, *UNCOMMON_CARDS, *RARE_CARDS)
ANCIENT_CARDS = tuple(
    d.definition_id for d in DEFAULT_CARDS.definitions if d.pool == "ironclad" and d.rarity == "ancient"
)
