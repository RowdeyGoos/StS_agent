"""Validation of plain card continuations and Ironclad combat state."""

from dataclasses import asdict
from copy import deepcopy
from game.headless.core.card_state import CombatRules
from game.headless.powers.ironclad import POWER_NAMES
from game.headless.powers.colorless import NAMES, INSTANCED, name
from game.headless.core.choice_snapshots import validate_selection, valid_power

TASK_ARITIES = {
    "end_hand_card": 1,
    "potion_effect": 2,
    "potion_finish": 1,
    "potion_status": 4,
    "gigantification_end": 1,
    "gigantification_begin": 1,
    "relic_hook": 3,
    "relic_damage": 5,
    "iteration": 1,
    "effect": 2,
    "after_play": 1,
    "after_enchantment": 1,
    "repeat": 1,
    "finish": 1,
    "death_hook": 1,
    "draw": 2,
    "autoplay": 2,
    "autoplay_draw": 2,
    "exhaust": 1,
    "block": 2,
    "attack": 7,
    "random_hit": 2,
    "after_card_power": 2,
    "after_card_enemies": 1,
    "after_card_enchantment": 1,
    "mayhem": 0,
    "cleanup_turn": 0,
    "selected": 4,
    "energy": 1,
    "after_draw": 0,
    "after_draw_card": 1,
    "start_power": 1,
    "early_end": 1,
    "catastrophe": 1,
    "status": 3,
    "pillage": 0,
    "generate": 5,
    "stampede": 1,
    "shuffle_choice": 0,
    "spawn_wrigglers": 1,
    "discard_hand": 0,
    "ethereal": 1,
    "discard_remaining": 0,
    "end_power": 1,
    "start_powers": 0,
}


from game.headless.core import silent_snapshots
TASK_ARITIES.update(silent_snapshots.TASK_ARITIES)


def restore_rules(record, player):
    if not isinstance(record, dict) or set(record) != set(asdict(CombatRules())):
        raise ValueError("Invalid combat rule state fields.")
    r = CombatRules(**deepcopy(record))
    for key in (
        "discarded_turn", "drawn_combat", "skills_finished", "shivs_finished", "extra_card_rewards",
        "attacks_started",
        "attacks_finished",
        "hp_loss_events",
        "hp_lost_this_turn",
        "exhausted_this_turn",
        "max_hp_gained",
        "ethereal_draws",
        "skills_started",
        "plays_finished",
        "power_sequence",
        "gold_gained",
        "gold_available",
        "gold_lost",
        "end_turn_hand_size",
        "potion_slots",
        "potion_capacity",
        "round_number",
    ):
        if type(getattr(r, key)) is not int or getattr(r, key) < 0:
            raise ValueError("Invalid rule counter.")
    if r.gold_lost > r.gold_available + r.gold_gained or r.end_turn_hand_size > 10:
        raise ValueError("Invalid turn resource state.")
    if type(r.player_side) is not bool or type(r.turn_ending) is not bool:
        raise ValueError("Invalid combat side state.")
    if r.attacks_finished > r.attacks_started:
        raise ValueError("Invalid attack history.")
    if not isinstance(r.powers, dict) or any(
        not valid_power(k, r.power_sequence) or type(v) is not int or (v < 0 and k != "dexterity") for k, v in r.powers.items()
    ):
        raise ValueError("Invalid player power state.")
    if not isinstance(r.auxiliaries, dict) or any(
        (k not in ("crimson_mantle", "inferno", "block_gains") and k.removesuffix(".ready") not in r.powers)
        or type(v) is not int
        or v < 0
        for k, v in r.auxiliaries.items()
    ):
        raise ValueError("Invalid auxiliary power state.")
    from game.headless.relics.combat import validate as validate_relics
    validate_relics(r.relics, r.relic_data, player.deck._allocated_ids)
    if r.room_kind not in ("combat", "elite", "boss") or r.round_number < 1:
        raise ValueError("Invalid combat relic room context.")
    from game.headless.potions.snapshots import validate as validate_potions
    validate_potions(r, player)
    silent_snapshots.validate_state(r, player)
    from game.headless.core.hook_snapshots import groups, validate_choices
    work = groups(r, player)
    validate_choices(r, player)
    in_play = {c.instance_id: c for c in player.deck.in_play}
    if not isinstance(r.plays, dict) or set(r.plays) != set(in_play):
        raise ValueError("Play ownership mismatch.")
    for identity, frame in r.plays.items():
        required = {
            "context",
            "target",
            "auto",
            "force_exhaust",
            "x",
            "energy_value",
            "remaining",
            "rupture",
            "destination",
            "effect_index",
            "stage",
            "silent_before",
        }
        if not isinstance(frame, dict) or set(frame) - {"blocks_gained", "calamity", "gigantification", "echo_kills"} != required:
            raise ValueError("Invalid play frame.")
        if (
            any(type(frame[k]) is not bool for k in ("auto", "force_exhaust"))
            or any(type(frame[k]) is not int or frame[k] < 0 for k in ("x", "energy_value", "remaining", "rupture"))
            or not 1 <= frame["remaining"] <= 3 + int(in_play[identity].enchantment is not None and in_play[identity].enchantment.definition_id == "glam") + in_play[identity].combat_state.replay_count
        ):
            raise ValueError("Invalid play resources.")
        if type(frame["context"]) is not int or frame["context"] not in work:
            raise ValueError("Play has no owning execution context.")
        if frame["stage"] not in ("effects", "enchantment", "hooks"):
            raise ValueError("Invalid play resolution stage.")
        if "gigantification" in frame and (type(frame["gigantification"]) is not bool or not frame["gigantification"] or not r.powers.get("gigantification")):
            raise ValueError("Invalid captured Gigantification.")
        if "calamity" in frame and (type(frame["calamity"]) is not int or frame["calamity"] < 0):
            raise ValueError("Invalid captured Calamity.")
        if "blocks_gained" in frame and (
            type(frame["blocks_gained"]) is not int or frame["blocks_gained"] < 0
        ):
            raise ValueError("Invalid block history.")
        if frame["destination"] not in ("powers", "exhaust_pile", "discard_pile", "draw_pile"):
            raise ValueError("Invalid resolved pile.")
        if type(frame["effect_index"]) is not int or not 0 <= frame["effect_index"] < len(
            in_play[identity].definition.effects
        ):
            raise ValueError("Invalid interrupted effect.")
        silent_snapshots.validate_frame(frame, player)
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
    from game.headless.cards.curses import END_HAND_CURSES
    if not isinstance(r.end_hand_remaining, list):
        raise ValueError("Invalid remaining end-of-hand effects.")
    end_hand_ids = []
    all_tasks = [t for tasks in work.values() for t in tasks]
    for task in all_tasks:
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
        if op == "death_hook":
            slot = args[0]
            if (type(slot) is not int or not 0 <= slot < len(player.combat_enemies)
                    or player.combat_enemies[slot].is_alive
                    or not any(v["definition_id"] == "gremlin_horn" for v in r.relics)):
                raise ValueError("Unowned death hook.")
        if op == "spawn_wrigglers":
            from game.headless.monsters.phrog_parasite import PhrogParasite
            slot = args[0]
            if (type(slot) is not int or not 0 <= slot < len(player.combat_enemies)
                    or not isinstance(player.combat_enemies[slot], PhrogParasite)
                    or player.combat_enemies[slot].is_alive or player.combat_enemies[slot].spawned
                    or not player.combat_enemies[slot].statuses.get("infested")
                    or all_tasks.count(task) != 1):
                raise ValueError("Unowned parasite spawn continuation.")
        if op == "shuffle_choice" and not r.powers.get("stratagem"):
            raise ValueError("Unowned shuffle choice.")
        if op == "after_draw_card" and args[0] not in player.deck._allocated_ids:
            raise ValueError("Unowned drawn-card hook.")
        if op == "end_hand_card":
            source = known.get(args[0])
            if (source is None or args[0] in end_hand_ids or not r.turn_ending
                    or not (source.spec.end_turn_damage or source.spec.end_turn_hp_loss or source.definition.definition_id in END_HAND_CURSES)):
                raise ValueError("Unowned end-of-hand effect.")
            end_hand_ids.append(args[0])
        if op == 'relic_damage' and (args[0] not in r.relic_data or type(args[1]) is not int or args[1] < 0 or type(args[2]) is not bool or type(args[3]) is not bool or (args[4] is not None and (type(args[4]) is not int or not 0 <= args[4] < len(player.combat_enemies)))):
            raise ValueError('Invalid owned relic damage continuation.')
        if op in (
            "iteration",
            "effect",
            "after_play",
            "after_enchantment",
            "repeat",
            "finish",
            "attack",
            "random_hit",
            "gigantification_end",
            "gigantification_begin",
            "after_card_power",
            "after_card_enemies",
            "after_card_enchantment",
        ):
            if args[0] not in r.plays:
                raise ValueError("Task has no owning play.")
        elif op in ("autoplay", "exhaust", "ethereal") and args[0] in r.plays:
            raise ValueError("Queued movement cannot remove an active play.")
        elif op in ("autoplay", "exhaust", "ethereal") and args[0] not in player.deck._allocated_ids:
            raise ValueError("Task references an unallocated card.")
        if op == "relic_hook" and (args[0] not in r.relic_data or args[1] not in ("before_draw", "after_draw", "before_end", "after_end", "after_play", "exhaust", "exhaust_ethereal", "shuffle", "after_side_start") or (args[2] and args[2] not in player.deck._allocated_ids)):
            raise ValueError("Invalid relic hook continuation.")
        if op == "random_hit" and (type(args[1]) is not int or args[1] < 0):
            raise ValueError("Invalid random attack.")
        if op == "after_card_power" and not valid_power(args[1], r.power_sequence):
            raise ValueError("Invalid card hook.")
        if op == "selected" and (
            args[0] not in player.deck._allocated_ids
            or args[0] in r.plays
            or args[1] not in ("move", "exhaust", "transform", "discard_redraw", "free_combat", "hand_trick", "nightmare", "well_laid_plans")
            or args[2] not in ("hand", "draw_pile")
            or args[3] not in ("", "free_this_turn", "free_until_played")
        ):
            raise ValueError("Invalid selected-card work.")
        if op == "effect" and (
            type(args[1]) is not int or not 0 <= args[1] < len(known[args[0]].definition.effects)
        ):
            raise ValueError("Invalid queued effect.")
        if op in ("end_power", "early_end", "start_power") and not valid_power(args[0], r.power_sequence):
            raise ValueError("Invalid end power.")
        if op == "status":
            slot, name, amount = args
            if (
                type(slot) is not int
                or not 0 <= slot < len(player.combat_enemies)
                or name not in ("strength", "vulnerable", "weak", "mangle", "dark_shackles", "poison", "strangle")
                or type(amount) is not int
                or amount < 0
            ):
                raise ValueError("Invalid queued status.")
        if op == "attack":
            _, slot, area, expression, factor, gain, vigor = args
            if (
                type(area) is not bool
                or (
                    slot is not None and (type(slot) is not int or not 0 <= slot < len(player.combat_enemies))
                )
                or (not area and slot is None)
            ):
                raise ValueError("Invalid queued attack target.")
            if expression not in (
                "base",
                "exhaust",
                "vulnerable",
                "strikes",
                "block",
                "plays",
                "draw_pile",
                "debuffs", "discards", "draws", "precise",
            ) or any(type(v) is not int or v < 0 for v in (factor, gain, vigor)):
                raise ValueError("Invalid queued attack expression.")
        if op in ("draw", "autoplay_draw", "block", "generate", "stampede", "energy", "catastrophe") and (
            type(args[0]) is not int or args[0] < 0
        ):
            raise ValueError("Invalid queued amount.")
        if op in ("draw", "autoplay_draw", "block", "autoplay") and type(args[-1]) is not bool:
            raise ValueError("Invalid queued flag.")
        if op == "generate" and any(type(v) is not bool for v in args[1:]):
            raise ValueError("Invalid generation flags.")
    if end_hand_ids != r.end_hand_remaining:
        raise ValueError("Missing end-of-hand continuation.")
    for identity, frame in r.plays.items():
        tasks = work[frame["context"]]
        control = [
            t
            for t in tasks
            if t[0] in ("iteration", "effect", "after_play", "after_enchantment", "repeat", "finish") and t[1] == identity
        ]
        expected = [
            ["effect", identity, i]
            for i in range(frame["effect_index"] + 1, len(in_play[identity].definition.effects))
        ] + [["after_play", identity]]
        if frame["stage"] != "effects":
            expected = [["after_enchantment" if frame["stage"] == "enchantment" else "repeat", identity]]
        if control != expected:
            raise ValueError("Invalid interrupted play continuation.")
        if (
            r.selection is None
            and frame["context"] == r.active_hook
            and identity == next(c.instance_id for c in reversed(player.deck.in_play)
                                 if r.plays[c.instance_id]["context"] == r.active_hook)
            and tasks[: len(expected)] != expected
        ):
            raise ValueError("Pending selector has unexpected work before its continuation.")
    for context, tasks in work.items():
        if [t[1] for t in tasks if t[0] in ("after_play", "after_enchantment", "repeat")] != [
            c.instance_id for c in reversed(player.deck.in_play) if r.plays[c.instance_id]["context"] == context
        ]:
            raise ValueError("Nested plays must finish before their parents in their own context.")
        for task in tasks:
            if task[0] in silent_snapshots.TASK_ARITIES:
                silent_snapshots.validate_task(task, r, player, context)
            if task[0] in ("iteration", "effect", "after_play", "after_enchantment", "repeat", "finish",
                           "attack", "random_hit", "gigantification_end", "gigantification_begin",
                           "after_card_power", "after_card_enemies", "after_card_enchantment"):
                if r.plays[task[1]]["context"] != context:
                    raise ValueError("Task belongs to a different execution context.")
    if r.selection is None and bool(r.tasks) != any(f["context"] == r.active_hook for f in r.plays.values()):
        # Pending start/end autoplay can leave outer turn work plus nested plays;
        # externally observable work always suspends at a card selector.
        raise ValueError("Unowned pending combat work.")
    player.rules = r
    from game.headless.core.enemy_turn import validate as validate_enemy_turn
    validate_enemy_turn(r.enemy_turn, player)
