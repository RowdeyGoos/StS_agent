"""Ordinary rest healing and cancelable single-card smithing."""

from game.headless.run.deck import upgrade_card
from game.headless.run.state import RunPhase
from game.headless.relics.run_rules import has, owned, counter, max_hp


def begin_rest_site(state) -> None:
    state.require_room_entry("rest")
    if state.pending is None:
        from game.headless.relics.run_rules import entered_room
        entered_room(state, "rest")
    state.pending = {"kind": "rest_site", "stage": "options", "used": []}
    state.phase = RunPhase.ROOM


def eligible_upgrades(state) -> tuple[str, ...]:
    return tuple(c.instance_id for c in state.deck if c.upgrade_level + 1 < len(c.definition.levels))


def _pending(state, stage):
    if state.phase is not RunPhase.ROOM or not state.pending or state.pending.get("kind") != "rest_site" or (state.pending.get("stage") != stage and not (stage == "options" and state.pending.get("stage") == "hatched" and has(state, "miniature_tent"))):
        raise ValueError("Rest-site action is unavailable.")
    return state.pending


def heal_amount(state) -> int:
    return min(state.max_hp * 3 // 10 + (15 if has(state, "regal_pillow") else 0), state.max_hp - state.hp)


def heal(state) -> int:
    pending = _pending(state, "options")
    if "rest" in pending["used"]:
        raise ValueError("Rest was already used here.")
    amount = heal_amount(state)
    state.hp += amount
    complete(state, "rest")
    if has(state, "stone_humidifier"):
        max_hp(state, 5)
    if has(state, "tiny_mailbox"):
        from game.headless.relics.pickup import potion_reward
        potion_reward(state, owned(state, "tiny_mailbox").instance_id)
    return amount


def begin_smith(state) -> None:
    pending = _pending(state, "options")
    if "smith" in pending["used"]:
        raise ValueError("Smithing was already used here.")
    choices = eligible_upgrades(state)
    if not choices:
        raise ValueError("No supported card can be upgraded.")
    state.pending = {"kind": "rest_site", "stage": "smith", "used": pending["used"], "eligible": list(choices)}


def choose_upgrade(state, instance_id: str | None):
    pending = _pending(state, "smith")
    if instance_id is None:
        state.pending = {"kind": "rest_site", "stage": "options", "used": pending["used"]}
        return None
    if instance_id not in pending["eligible"] or instance_id not in eligible_upgrades(state):
        raise ValueError("Card is not eligible for this upgrade choice.")
    card = upgrade_card(state, instance_id)
    complete(state, "smith")
    return card


def leave(state) -> None:
    if state.pending and state.pending.get("stage") == "options" and has(state, "miniature_tent") and state.pending["used"]:
        _pending(state, "options")
    else:
        _pending(state, "hatched" if state.pending and state.pending.get("stage") == "hatched" else "resolved")
    state.pending = None
    state.phase = RunPhase.ROUTE


def complete(state, option):
    used = [*state.pending["used"], option]
    state.pending = {"kind": "rest_site", "stage": "options" if has(state, "miniature_tent") else "resolved", "used": used}


def lift(state):
    pending = _pending(state, "options")
    relic = owned(state, "girya")
    if relic is None or relic.counter >= 3 or "lift" in pending["used"]:
        raise ValueError("Lifting is unavailable.")
    counter(state, relic, relic.counter + 1)
    complete(state, "lift")


def dig(state):
    pending = _pending(state, "options")
    relic = owned(state, "shovel")
    if relic is None or "dig" in pending["used"]:
        raise ValueError("Digging is unavailable.")
    from game.headless.relics.pickup import relic_reward
    relic_reward(state, relic.instance_id)
    complete(state, "dig")
