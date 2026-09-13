"""Enchantment content and serializable per-card state."""

from dataclasses import dataclass, asdict
from types import MappingProxyType


@dataclass
class EnchantmentInstance:
    definition_id: str
    amount: int = 1
    triggered: bool = False
    extra_damage: int = 0


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


@dataclass(frozen=True, slots=True)
class EnchantmentDefinition:
    definition_id: str

    def on_play(self, instance, player):
        if not player.is_alive:
            return
        if self.definition_id == "momentum":
            instance.extra_damage += instance.amount
        elif self.definition_id == "adroit" and not player.combat_is_ending:
            player.gain_block(instance.amount, powered=True)
        elif self.definition_id == "swift" and not instance.triggered:
            instance.triggered = True
            player.draw_cards(instance.amount)


ENCHANTMENTS = MappingProxyType({"sown": Sown(), **{
    name: EnchantmentDefinition(name) for name in ("sharp", "adroit", "momentum", "royally_approved", "swift", "nimble", "glam")
}})


def can_enchant(card, definition_id="sown"):
    # Existing "block" cards are native skills. Native master-deck gate: no status/curse/quest cards, Unplayable, or existing
    # enchantment. Sown is nonstackable and has no additional type restriction.
    kind = card.spec.kind
    if definition_id not in ENCHANTMENTS or kind not in ("attack", "skill", "block", "power") or card.cost < 0 or card.enchantment is not None:
        return False
    if definition_id in ("sharp", "momentum"):
        return kind == "attack"
    if definition_id == "royally_approved":
        return kind in ("attack", "skill", "block")
    if definition_id == "nimble":
        return card.spec.block_gain > 0 or any(getattr(effect, "operation", None) == "evil_eye" for effect in card.definition.effects)
    return True


def enchant(card, definition_id="sown", amount=1):
    if definition_id not in ENCHANTMENTS or type(amount) is not int or amount <= 0 or not can_enchant(card, definition_id):
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
            or type(instance.extra_damage) is not int or instance.extra_damage < 0
            or instance.definition_id != "momentum" and instance.extra_damage != 0
            or permanent and (instance.triggered or instance.extra_damage or card.cost < 0)):
        raise ValueError("Invalid card enchantment state.")


def record(card):
    return None if card.enchantment is None else asdict(card.enchantment)


def restore(record):
    if record is None:
        return None
    if not isinstance(record, dict) or set(record) != {"definition_id", "amount", "triggered", "extra_damage"}:
        raise ValueError("Invalid enchantment state fields.")
    return EnchantmentInstance(**record)


def fingerprint():
    return [asdict(definition) for definition in ENCHANTMENTS.values()]
