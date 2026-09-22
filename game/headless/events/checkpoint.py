"""Bind an event's last successful command to its owned gameplay state.

Nested relic choices execute through the ordinary acquisition system. Retaining
its result avoids duplicating that system in an event-specific replay engine.
This is consistency validation, not authentication of a user-edited snapshot.
"""

from dataclasses import asdict
from hashlib import sha256
import json
from game.headless.core.snapshots import card_record


def capture(state, data):
    continuation = {k: v for k, v in data.items() if k != "checkpoint"}
    return {
        "continuation": sha256(
            json.dumps(continuation, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "act_index": state.act_index,
        "wongo_points": state.wongo_points,
        "freed_repy": state.freed_repy,
        "hp": state.hp,
        "max_hp": state.max_hp,
        "gold": state.gold,
        "deck": [card_record(c) for c in state.deck],
        "relics": [asdict(r) for r in state.relics],
        "potions": [None if p is None else asdict(p) for p in state.potions],
        "next_card_id": state.next_card_id,
        "next_item_id": state.next_item_id,
        "potion_capacity": state.potion_capacity,
    }


def refresh(state):
    pending = state.pending
    if pending and pending.get("kind") == "scripted_event":
        from game.headless.events.catalog import EVENTS

        if getattr(EVENTS[pending["definition_id"]], "uses_steps", False):
            pending["data"]["checkpoint"] = capture(state, pending["data"])
