"""Enchantment content and serializable per-card state."""

from dataclasses import dataclass, asdict
from types import MappingProxyType


@dataclass
class EnchantmentInstance:
    definition_id: str
    amount: int = 1
    triggered: bool = False


@dataclass(frozen=True, slots=True)
class Sown:
    definition_id: str = "sown"

    def on_play(self, instance, player):
        # Native wrapper skips enchantments after player death. GainEnergy itself
        # skips a terminal fight, but Sown still records its consumed trigger.
        if not player.is_alive or instance.triggered:
            return
        if not player.combat_is_ending:
            player.energy += instance.amount
        instance.triggered = True


ENCHANTMENTS = MappingProxyType({"sown": Sown()})


def can_enchant(card):
    # Existing "block" cards are native skills. Native master-deck gate: no status/curse/quest cards, Unplayable, or existing
    # enchantment. Sown is nonstackable and has no additional type restriction.
    return card.spec.kind in ("attack", "skill", "block", "power") and card.cost >= 0 and card.enchantment is None


def enchant(card, definition_id="sown", amount=1):
    if definition_id not in ENCHANTMENTS or type(amount) is not int or amount <= 0 or not can_enchant(card):
        raise ValueError("Card cannot receive this enchantment.")
    card.enchantment = EnchantmentInstance(definition_id, amount)
    return card


def validate(card, *, permanent=False):
    instance = card.enchantment
    if instance is None:
        return
    if (not isinstance(instance, EnchantmentInstance) or instance.definition_id not in ENCHANTMENTS
            or type(instance.amount) is not int or instance.amount <= 0 or type(instance.triggered) is not bool
            or card.spec.kind not in ("attack", "skill", "block", "power")
            or permanent and (instance.triggered or card.cost < 0)):
        raise ValueError("Invalid card enchantment state.")


def record(card):
    return None if card.enchantment is None else asdict(card.enchantment)


def restore(record):
    if record is None:
        return None
    if not isinstance(record, dict) or set(record) != {"definition_id", "amount", "triggered"}:
        raise ValueError("Invalid enchantment state fields.")
    return EnchantmentInstance(**record)


def fingerprint():
    return [asdict(definition) for definition in ENCHANTMENTS.values()]
