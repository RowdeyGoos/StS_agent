"""Compatibility imports; gameplay implementation lives in game.headless."""

from game.headless.powers.status import (
    StatusDefinition,
    StatusCollection,
    get_status_amount,
    modify_attack_damage_for_statuses,
    SHRINK,
    VULNERABLE,
    STATUS_STACK_SCALE,

    STATUS_DEFINITIONS,
)

# Frozen legacy encoder vocabulary; broader powers use direct game commands.
SUPPORTED_STATUS_NAMES = (SHRINK, VULNERABLE)
