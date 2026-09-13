"""Play restricted authored routes using direct game commands and no RL stack."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from game.headless.core.actions import ChooseCombatCard, EndTurn, PlayCard
from game.headless.run.actions import (
    ChooseNode, ClaimGold, ChooseRewardCard, ClaimPotion, ClaimRelic, LeaveRewards,
    Rest, Smith, ChooseUpgrade, LeaveRest, UsePotion,
)
from game.headless.run.engine import RunEngine


def choose_demo_action(engine, rest_choice="smith", path="left"):
    """A deterministic example player, not an engine rule or trained policy."""
    actions = engine.legal_actions()
    nodes = [a for a in actions if isinstance(a, ChooseNode)]
    if nodes:
        return nodes[0] if path == "left" else nodes[-1]
    for kind in (ChooseCombatCard, ClaimGold, ClaimPotion, ClaimRelic):
        if found := next((a for a in actions if isinstance(a, kind)), None):
            return found
    choices = [a for a in actions if isinstance(a, ChooseRewardCard) and a.definition_id is not None]
    if choices:
        return next((a for a in choices if a.definition_id == "pommel_strike"), choices[0])
    if Smith() in actions and rest_choice == "smith":
        return Smith()
    if Rest() in actions:
        return Rest()
    upgrades = [a for a in actions if isinstance(a, ChooseUpgrade) and a.instance_id is not None]
    if upgrades:
        bash = next((c.instance_id for c in engine.state.deck if c.definition.definition_id == "bash"), None)
        return next((a for a in upgrades if a.instance_id == bash), upgrades[0])
    for kind in (LeaveRewards, LeaveRest, UsePotion):
        if found := next((a for a in actions if isinstance(a, kind)), None):
            return found
    plays = [a for a in actions if isinstance(a, PlayCard)]
    if plays:
        cards = {c.instance_id: c for c in engine.combat.player.hand}
        def priority(action):
            card = cards[action.instance_id]
            target_hp = 10**6 if action.target_slot is None else engine.combat.enemies[action.target_slot].hp
            return (card.spec.kind != "attack", target_hp, card.definition.definition_id != "bash")
        return min(plays, key=priority)
    if EndTurn() in actions:
        return EndTurn()
    raise ValueError("No supported demo decision is available.")


def play_slice(*, seed=0, rest_choice="smith", verify_restore=False, route="first-slice", path="left"):
    if path not in ("left", "right"):
        raise ValueError("Unknown demo path preference.")
    engine = RunEngine.ironclad_slice(seed=seed, route=route)
    trace = []
    for _ in range(500):
        if not engine.legal_actions():
            return engine, trace
        action = choose_demo_action(engine, rest_choice, path)
        if verify_restore:
            snapshot = json.loads(json.dumps(engine.snapshot()))
            clone = RunEngine()
            clone.restore(snapshot)
            if clone.legal_actions() != engine.legal_actions():
                raise AssertionError("Restored decisions differ.")
            clone.apply(action)
        trace.append({"phase": engine.state.phase.value, "action": type(action).__name__, **asdict(action)})
        engine.apply(action)
        if verify_restore and json.loads(json.dumps(engine.snapshot())) != json.loads(json.dumps(clone.snapshot())):
            raise AssertionError("Restored continuation differs.")
    raise RuntimeError("Demo exceeded its 500-command bound.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    from game.headless.run.scenarios import ROUTES
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--route", choices=tuple(ROUTES), default="first-slice")
    parser.add_argument("--path", choices=("left", "right"), default="left",
                        help="Demo preference for the first or last available branch.")
    parser.add_argument("--rest-choice", choices=("rest", "smith"), default="smith")
    parser.add_argument("--verify-restore", action="store_true")
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args(argv)
    engine, trace = play_slice(seed=args.seed, rest_choice=args.rest_choice, verify_restore=args.verify_restore, route=args.route, path=args.path)
    state = engine.state
    print(json.dumps({"scope": "restricted_ironclad_a0_two_combat_slice" if args.route == "first-slice" else ("restricted_ironclad_a0_act1_route" if args.route == "overgrowth-act1" else "restricted_ironclad_a0_overgrowth_route"),
                      "route": args.route, "path": args.path, "seed": state.seed,
                      "phase": state.phase.value, "hp": state.hp, "max_hp": state.max_hp,
                      "gold": state.gold, "combats_completed": state.combats_completed,
                      "act_completion": None if state.act_completion is None else asdict(state.act_completion),
                      "deck_size": len(state.deck), "relics": [r.definition_id for r in state.relics], "upgraded_cards": [c.instance_id for c in state.deck if c.upgrade_level],
                      "potions_used": sum(t["action"] == "UsePotion" for t in trace),
                      "commands": len(trace), "restore_verified": args.verify_restore,
                      **({"trace": trace} if args.trace else {})}, indent=2))


if __name__ == "__main__":
    main()
