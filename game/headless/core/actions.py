"""Game commands, independent of public candidate IDs and fixed action encodings."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlayCard:
    instance_id: str
    target_slot: int | None = None

    def __post_init__(self):
        if not isinstance(self.instance_id, str) or not self.instance_id:
            raise ValueError("A play command requires an exact card instance ID.")
        if self.target_slot is not None and (type(self.target_slot) is not int or self.target_slot < 0):
            raise ValueError("Target slot must be a nonnegative integer or None.")


@dataclass(frozen=True, slots=True)
class EndTurn:
    pass


@dataclass(frozen=True, slots=True)
class ChooseCombatCard:
    instance_id: str

    def __post_init__(self):
        if not isinstance(self.instance_id, str) or not self.instance_id:
            raise ValueError("A combat choice requires an exact card instance ID.")


CombatAction = PlayCard | EndTurn | ChooseCombatCard
