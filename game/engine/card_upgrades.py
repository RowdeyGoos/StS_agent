"""Programmatic persistent upgrade operation at an idle combat boundary.

This is the HF13 implementation seam. Rest-site selection and other upgrade
sources must supply their own legal decisions before calling an upgrade rule.
"""

from dataclasses import replace

from game.content.card_upgrades import STRIKE_UPGRADE_CONTENT_FINGERPRINT
from game.contracts.headless_v0 import DecisionPhase
from game.engine.headless_state import (
    PersistentCardInstance,
    StateValidationError,
    WorldState,
)
from game.simulation.card import CardSpec, UPGRADED_STRIKE_SPEC


def _upgrade_target(world: WorldState, instance_id: str) -> PersistentCardInstance:
    world.validate()
    if world.content_fingerprint != STRIKE_UPGRADE_CONTENT_FINGERPRINT:
        raise StateValidationError("World content does not enable the Strike upgrade profile.")
    if (
        world.phase is not DecisionPhase.COMBAT
        or world.current_hp <= 0
        or world.active_combat_launch_key is not None
        or world.pending_decision is not None
        or world.automatic_queue
    ):
        raise StateValidationError("Upgrade requires an idle, living combat boundary.")
    card = next((card for card in world.master_deck if card.instance_id == instance_id), None)
    if card is None:
        raise StateValidationError("Upgrade target is not in the persistent deck.")
    if card.definition_id != "strike" or card.upgraded:
        raise StateValidationError("Only a non-upgraded Strike can be upgraded in this profile.")
    return card


def preview_card_upgrade(world: WorldState, instance_id: str) -> CardSpec:
    """Return immutable effect metadata without allocating IDs or consuming RNG."""
    _upgrade_target(world, instance_id)
    return UPGRADED_STRIKE_SPEC


def upgrade_persistent_card(world: WorldState, instance_id: str) -> PersistentCardInstance:
    """Upgrade one exact instance in place, preserving its ID and deck position."""
    card = _upgrade_target(world, instance_id)
    upgraded = replace(card, upgraded=True)
    world.master_deck = tuple(
        upgraded if item.instance_id == instance_id else item for item in world.master_deck
    )
    return upgraded
