"""One restricted ordinary A0 chest; native global relic pools remain separate."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TreasureDefinition:
    definition_id: str
    relic_pool: tuple[str, ...]
    fallback_relic: str
    gold_range: tuple[int, int]


ORDINARY_CHEST = TreasureDefinition("supported_treasure_v1", ("strawberry", "pear", "mango"), "circlet", (42, 52))


def fingerprint():
    return {"definition_id": ORDINARY_CHEST.definition_id, "relic_pool": list(ORDINARY_CHEST.relic_pool),
            "fallback_relic": ORDINARY_CHEST.fallback_relic, "gold_range": list(ORDINARY_CHEST.gold_range)}
