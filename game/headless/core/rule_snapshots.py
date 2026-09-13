"""Validation of plain card continuations and Ironclad combat state."""

from dataclasses import asdict
from copy import deepcopy
from game.headless.core.card_state import CombatRules
from game.headless.powers.ironclad import POWER_NAMES

TASK_ARITIES = {
    "iteration": 1,
    "effect": 2,
    "after_play": 1,
    "repeat": 1,
    "finish": 1,
    "draw": 2,
    "autoplay": 2,
    "autoplay_draw": 2,
    "exhaust": 1,
    "block": 2,
    "attack": 6,
    "status": 3,
    "pillage": 0,
    "generate": 4,
    "stampede": 1,
    "discard_hand": 0,
    "ethereal": 1,
    "discard_remaining": 0,
    "end_power": 1,
    "start_powers": 0,
}


def restore_rules(record, player):
    if not isinstance(record, dict) or set(record) != set(asdict(CombatRules())):
        raise ValueError("Invalid combat rule state fields.")
    r = CombatRules(**deepcopy(record))
    for key in (
        "attacks_started",
        "attacks_finished",
        "hp_loss_events",
        "hp_lost_this_turn",
        "exhausted_this_turn",
        "max_hp_gained",
        "ethereal_draws",
    ):
        if type(getattr(r, key)) is not int or getattr(r, key) < 0:
            raise ValueError("Invalid rule counter.")
    if type(r.player_side) is not bool or type(r.turn_ending) is not bool:
        raise ValueError("Invalid combat side state.")
    if r.attacks_finished > r.attacks_started:
        raise ValueError("Invalid attack history.")
    if not isinstance(r.powers, dict) or any(
        k not in POWER_NAMES or type(v) is not int or v < 0 for k, v in r.powers.items()
    ):
        raise ValueError("Invalid player power state.")
    if not isinstance(r.auxiliaries, dict) or any(
        k not in ("crimson_mantle", "inferno", "block_gains") or type(v) is not int or v < 0
        for k, v in r.auxiliaries.items()
    ):
        raise ValueError("Invalid auxiliary power state.")
    in_play = {c.instance_id: c for c in player.deck.in_play}
    if not isinstance(r.plays, dict) or set(r.plays) != set(in_play):
        raise ValueError("Play ownership mismatch.")
    for identity, frame in r.plays.items():
        required = {
            "target",
            "auto",
            "force_exhaust",
            "x",
            "remaining",
            "rupture",
            "destination",
            "effect_index",
        }
        if not isinstance(frame, dict) or set(frame) - {"blocks_gained"} != required:
            raise ValueError("Invalid play frame.")
        if (
            any(type(frame[k]) is not bool for k in ("auto", "force_exhaust"))
            or any(type(frame[k]) is not int or frame[k] < 0 for k in ("x", "remaining", "rupture"))
            or frame["remaining"] < 1
        ):
            raise ValueError("Invalid play resources.")
        if "blocks_gained" in frame and (
            type(frame["blocks_gained"]) is not int or frame["blocks_gained"] < 0
        ):
            raise ValueError("Invalid block history.")
        if frame["destination"] not in ("powers", "exhaust_pile", "discard_pile"):
            raise ValueError("Invalid resolved pile.")
        if type(frame["effect_index"]) is not int or not 0 <= frame["effect_index"] < len(
            in_play[identity].definition.effects
        ):
            raise ValueError("Invalid interrupted effect.")
        card = in_play[identity]
        if (frame["destination"] == "powers") != (card.spec.kind == "power"):
            raise ValueError("Result pile does not match card kind.")
        if (
            card.spec.kind != "power"
            and (card.exhausts or frame["force_exhaust"])
            and frame["destination"] != "exhaust_pile"
        ):
            raise ValueError("Required exhaustion is missing.")
        slot = frame["target"]
        if slot is not None and (type(slot) is not int or not 0 <= slot < len(player.combat_enemies)):
            raise ValueError("Invalid play target.")
        if in_play[identity].spec.uses_target and slot is None:
            raise ValueError("Missing play target.")
    if not isinstance(r.tasks, list):
        raise ValueError("Invalid work queue.")
    known = {c.instance_id: c for c in player.deck.all_cards()}
    for task in r.tasks:
        if (
            not isinstance(task, list)
            or not task
            or not isinstance(task[0], str)
            or task[0] not in TASK_ARITIES
            or len(task) != TASK_ARITIES[task[0]] + 1
        ):
            raise ValueError("Invalid combat task.")
        if any(type(v) not in (int, bool, str, type(None)) for v in task):
            raise ValueError("Task must contain plain values.")
        op, *args = task
        if op in ("iteration", "effect", "after_play", "repeat", "finish", "attack"):
            if args[0] not in r.plays:
                raise ValueError("Task has no owning play.")
        elif op in ("autoplay", "exhaust", "ethereal") and args[0] in r.plays:
            raise ValueError("Queued movement cannot remove an active play.")
        elif op in ("autoplay", "exhaust", "ethereal") and args[0] not in player.deck._allocated_ids:
            raise ValueError("Task references an unallocated card.")
        if op == "effect" and (
            type(args[1]) is not int or not 0 <= args[1] < len(known[args[0]].definition.effects)
        ):
            raise ValueError("Invalid queued effect.")
        if op == "end_power" and args[0] not in POWER_NAMES:
            raise ValueError("Invalid end power.")
        if op == "status":
            slot, name, amount = args
            if (
                type(slot) is not int
                or not 0 <= slot < len(player.combat_enemies)
                or name not in ("strength", "vulnerable", "weak", "mangle")
                or type(amount) is not int
                or amount < 0
            ):
                raise ValueError("Invalid queued status.")
        if op == "attack":
            _, slot, area, expression, factor, gain = args
            if (
                type(area) is not bool
                or (
                    slot is not None and (type(slot) is not int or not 0 <= slot < len(player.combat_enemies))
                )
                or (not area and slot is None)
            ):
                raise ValueError("Invalid queued attack target.")
            if expression not in ("base", "exhaust", "vulnerable", "strikes", "block") or any(
                type(v) is not int or v < 0 for v in (factor, gain)
            ):
                raise ValueError("Invalid queued attack expression.")
        if op in ("draw", "autoplay_draw", "block", "generate", "stampede") and (
            type(args[0]) is not int or args[0] < 0
        ):
            raise ValueError("Invalid queued amount.")
        if op in ("draw", "autoplay_draw", "block", "autoplay") and type(args[-1]) is not bool:
            raise ValueError("Invalid queued flag.")
        if op == "generate" and any(type(v) is not bool for v in args[1:]):
            raise ValueError("Invalid generation flags.")
    for identity, frame in r.plays.items():
        control = [
            t
            for t in r.tasks
            if t[0] in ("iteration", "effect", "after_play", "repeat", "finish") and t[1] == identity
        ]
        expected = [
            ["effect", identity, i]
            for i in range(frame["effect_index"] + 1, len(in_play[identity].definition.effects))
        ] + [["after_play", identity]]
        if control != expected:
            raise ValueError("Invalid interrupted play continuation.")
        if identity == player.deck.in_play[-1].instance_id and r.tasks[: len(expected)] != expected:
            raise ValueError("Pending selector has unexpected work before its continuation.")
    if [t[1] for t in r.tasks if t[0] == "after_play"] != [
        c.instance_id for c in reversed(player.deck.in_play)
    ]:
        raise ValueError("Nested plays must finish before their parents.")
    if bool(r.tasks) != bool(r.plays):
        # Pending start/end autoplay can leave outer turn work plus nested plays;
        # externally observable work always suspends at a card selector.
        raise ValueError("Unowned pending combat work.")
    player.rules = r
