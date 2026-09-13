"""Explicit opt-in content identity for the first source-backed card upgrade.

This extends the reduced fixture, not the game's complete card pool. Native
source evidence is recorded in docs/evidence/strike_upgrade_2026_09_13.md.
"""

from dataclasses import asdict
from hashlib import sha256
import json

from game.content.reduced_v0 import CONTENT_FINGERPRINT as BASE_CONTENT_FINGERPRINT
from game.simulation.card import UPGRADED_STRIKE_SPEC

BASE_CARD_PROFILE = "base"
STRIKE_UPGRADE_PROFILE = "strike_upgrade_v1"
STRIKE_UPGRADE_CONTENT_FINGERPRINT = sha256(
    json.dumps(
        {
            "profile": STRIKE_UPGRADE_PROFILE,
            "base_content_fingerprint": BASE_CONTENT_FINGERPRINT,
            "definition_id": "strike",
            "upgrade_limit": 1,
            "upgraded_spec": asdict(UPGRADED_STRIKE_SPEC),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


def validate_card_profile(card_profile: str) -> None:
    if card_profile not in (BASE_CARD_PROFILE, STRIKE_UPGRADE_PROFILE):
        raise ValueError(f"Unsupported card profile: {card_profile!r}.")


def projected_card_name(legacy_name: object, card_profile: str) -> tuple[object, bool]:
    """Resolve only this profile's variant; callers still validate base names."""
    validate_card_profile(card_profile)
    if card_profile == STRIKE_UPGRADE_PROFILE and legacy_name == "Strike+":
        return "Strike", True
    return legacy_name, False
