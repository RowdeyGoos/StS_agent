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
        if self.definition_id == "inky" and not player.combat_is_ending:
            from game.headless.core.resolution import push
            card = player.current_card
            target = player.rules.plays[card.instance_id]["target"]
            slots = range(len(player.combat_enemies)) if card.combat_state.all_enemies else (target,)
            push(player, *[["status", slot, "weak", 1] for slot in slots if slot is not None and player.combat_enemies[slot].is_alive])
        elif self.definition_id == "momentum":
            instance.extra_damage += instance.amount
        elif self.definition_id == "adroit" and not player.combat_is_ending:
            player.gain_block(instance.amount, powered=True)
        elif self.definition_id == "swift" and not instance.triggered:
            instance.triggered = True
            player.draw_cards(instance.amount)


ENCHANTMENTS = MappingProxyType({"sown": Sown(), **{
    name: EnchantmentDefinition(name) for name in ("sharp", "adroit", "momentum", "royally_approved", "swift", "nimble", "glam", "slither", "inky", "goopy", "tezcataras_ember", "instinct", "imbued", "clone")
}})


def can_enchant(card, definition_id="sown"):
    # Existing "block" cards are native skills. Native master-deck gate: no status/curse/quest cards, Unplayable, or existing
    # enchantment. Sown is nonstackable and has no additional type restriction.
    kind = card.spec.kind
    if definition_id not in ENCHANTMENTS or kind not in ("attack", "skill", "block", "power") or card.cost < 0 or card.enchantment is not None:
        return False
    if definition_id == "slither":
        return not card.spec.x_cost
    if definition_id == "imbued":
        return kind in ("skill", "block")
    if definition_id == "goopy":
        return card.definition.defend
    if definition_id in ("sharp", "momentum", "instinct"):
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


def after_draw(card, deck):
    if card.enchantment is None or card.enchantment.definition_id != "slither" or card not in deck.hand:
        return
    randomize_cost(card, deck)


def randomize_cost(card, deck):
    v=card.combat_state
    v.combat_cost_override=deck.energy_rng.randrange(4)
    from game.headless.core.card_costs import mark_setter
    mark_setter(v, 'combat')
    v.combat_override_baseline=v.combat_cost_change
    v.cost_change=v.turn_cost_change=0
    v.played_cost_baselines[:2]=[0, 0]
    v.free_this_turn=v.free_this_combat=v.free_until_played=False
    v.turn_cost_override=None
