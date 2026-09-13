"""Direct game commands for the supported run decisions."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChooseNode:
    node_id: str


@dataclass(frozen=True, slots=True)
class ClaimGold:
    pass


@dataclass(frozen=True, slots=True)
class ChooseRewardCard:
    definition_id: str | None  # None declines the card reward.


@dataclass(frozen=True, slots=True)
class ClaimPotion:
    pass


@dataclass(frozen=True, slots=True)
class ClaimRelic:
    pass


@dataclass(frozen=True, slots=True)
class LeaveRewards:
    pass


@dataclass(frozen=True, slots=True)
class Rest:
    pass


@dataclass(frozen=True, slots=True)
class Smith:
    pass


@dataclass(frozen=True, slots=True)
class ChooseUpgrade:
    instance_id: str | None  # None cancels and returns to the rest options.


@dataclass(frozen=True, slots=True)
class LeaveRest:
    pass


@dataclass(frozen=True, slots=True)
class UsePotion:
    instance_id: str
    target_slot: int | None = None

    def __post_init__(self):
        if not isinstance(self.instance_id, str) or not self.instance_id:
            raise ValueError("Potion use requires an instance ID.")
        if self.target_slot is not None and (type(self.target_slot) is not int or self.target_slot < 0):
            raise ValueError("Potion target must be a nonnegative enemy slot or None.")


@dataclass(frozen=True, slots=True)
class DiscardPotion:
    instance_id: str


@dataclass(frozen=True, slots=True)
class BuyShopItem:
    offer_id: str


@dataclass(frozen=True, slots=True)
class BeginShopRemoval:
    pass


@dataclass(frozen=True, slots=True)
class ChooseShopRemoval:
    instance_id: str | None  # None cancels without spending gold or using removal.


@dataclass(frozen=True, slots=True)
class LeaveShop:
    pass


@dataclass(frozen=True, slots=True)
class OpenChest:
    pass


@dataclass(frozen=True, slots=True)
class ClaimTreasureRelic:
    treasure_id: int


@dataclass(frozen=True, slots=True)
class LeaveTreasure:
    pass
