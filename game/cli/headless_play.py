"""Play restricted authored or generated routes with direct game commands."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from game.headless.core.actions import ChooseCombatCard, EndTurn, PlayCard
from game.headless.run.actions import (
    ChooseAncientRelic, ChooseNode, ClaimGold, ChooseRewardCard, ClaimPotion, ClaimRelic, LeaveRewards,
    Rest, Smith, Hatch, ChooseUpgrade, LeaveRest, UsePotion,
    BuyShopItem, BeginShopRemoval, ChooseShopRemoval, LeaveShop,
    OpenChest, ClaimTreasureRelic, LeaveTreasure, ChooseEventOption, ChooseEventCard, LeaveEvent,
)
from game.headless.run.engine import RunEngine


def choose_demo_action(engine, rest_choice="smith", path="left"):
    """A deterministic example player, not an engine rule or trained policy."""
    actions = engine.legal_actions()
    nodes = [a for a in actions if isinstance(a, ChooseNode)]
    if nodes:
        return nodes[0] if path == "left" else nodes[-1]
    for kind in (ChooseAncientRelic, ChooseCombatCard, ClaimGold, ClaimPotion, ClaimRelic, OpenChest, ClaimTreasureRelic):
        if found := next((a for a in actions if isinstance(a, kind)), None):
            return found
    event_choices = [a for a in actions if isinstance(a, ChooseEventOption)]
    if event_choices:
        return next((a for a in event_choices if a.option_id in ("join_forces", "maintain_control", "loner", "smash", "give_up", "gold", "bottle", "dive_into_water", "rest", "plant", "take")
                     or a.option_id.startswith(("claim_potion_", "overcome_"))), event_choices[0])
    event_cards = [a for a in actions if isinstance(a, ChooseEventCard)]
    if event_cards:
        bash = next((c.instance_id for c in engine.state.deck if c.definition.definition_id == "bash"), None)
        return next((a for a in event_cards if a.card_instance_id == bash), event_cards[0])
    choices = [a for a in actions if isinstance(a, ChooseRewardCard) and a.definition_id is not None]
    if choices:
        return next((a for a in choices if a.definition_id == "pommel_strike"), choices[0])
    if Hatch() in actions:
        return Hatch()
    if Smith() in actions and rest_choice == "smith":
        return Smith()
    if Rest() in actions:
        return Rest()
    upgrades = [a for a in actions if isinstance(a, ChooseUpgrade) and a.instance_id is not None]
    if upgrades:
        bash = next((c.instance_id for c in engine.state.deck if c.definition.definition_id == "bash"), None)
        return next((a for a in upgrades if a.instance_id == bash), upgrades[0])
    if engine.state.pending and engine.state.pending.get("kind") == "shop":
        # Buy one affordable card, remove a starter, then leave; this is only
        # an example policy, never a restriction on the room's legal purchases.
        offers = engine.state.pending["offers"]
        bought_card = any(o["kind"] == "card" and o["sold"] for o in offers)
        if not bought_card:
            for offer in offers:
                if offer["kind"] == "card" and BuyShopItem(offer["offer_id"]) in actions:
                    return BuyShopItem(offer["offer_id"])
        if BeginShopRemoval() in actions:
            return BeginShopRemoval()
        removals = [a for a in actions if isinstance(a, ChooseShopRemoval) and a.instance_id is not None]
        if removals:
            strikes = {c.instance_id for c in engine.state.deck if c.definition.definition_id == "strike"}
            return next((a for a in removals if a.instance_id in strikes), removals[0])
    for kind in (LeaveRewards, LeaveRest, LeaveShop, LeaveTreasure, LeaveEvent, UsePotion):
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


def play_slice(*, seed=0, rest_choice="smith", verify_restore=False, route="first-slice", path="left", boss=None, elite=None, hallway=None, ancient=None):
    if path not in ("left", "right"):
        raise ValueError("Unknown demo path preference.")
    if ancient not in (None, "neow") or ancient is not None and route != "overgrowth-generated":
        raise ValueError("Neow start requires the generated Act 1 route.")
    if route == "overgrowth-generated":
        if any(value is not None for value in (boss, elite, hallway)):
            raise ValueError("Generated routes select encounters from owned queues.")
        from game.headless.run.ancient import PROFILE as ANCIENT_PROFILE
        engine = RunEngine.ironclad_act1(seed=seed, ancient_profile=ANCIENT_PROFILE if ancient else None)
    else:
        engine = RunEngine.ironclad_slice(seed=seed, route=route, boss=boss, elite=elite, hallway=hallway)
    trace = []
    for _ in range(2000):
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
    raise RuntimeError("Demo exceeded its 2000-command bound.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    from game.headless.run.scenarios import ROUTES
    from game.headless.encounters.catalog import ENCOUNTERS
    for option, kind in (("boss", "boss"), ("elite", "elite"), ("hallway", "combat")):
        parser.add_argument("--" + option, choices=tuple(name for name, encounter in ENCOUNTERS.items() if encounter.room_kind == kind and encounter.event_id is None),
                            help="Replace this encounter on the authored Act 1 route.")
    parser.add_argument("--ancient", choices=("neow",), help="Begin generated Act 1 with the restricted Neow pickup choices.")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--route", choices=(*ROUTES, "overgrowth-generated"), default="first-slice")
    parser.add_argument("--path", choices=("left", "right"), default="left",
                        help="Demo preference for the first or last available branch.")
    parser.add_argument("--rest-choice", choices=("rest", "smith"), default="smith")
    parser.add_argument("--verify-restore", action="store_true")
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args(argv)
    engine, trace = play_slice(seed=args.seed, rest_choice=args.rest_choice, verify_restore=args.verify_restore, route=args.route, path=args.path, boss=args.boss, elite=args.elite, hallway=args.hallway, ancient=args.ancient)
    state = engine.state
    print(json.dumps({"scope": "restricted_ironclad_a0_generated_act1" if args.route == "overgrowth-generated" else ("restricted_ironclad_a0_two_combat_slice" if args.route == "first-slice" else ("restricted_ironclad_a0_act1_route" if args.route == "overgrowth-act1" else "restricted_ironclad_a0_overgrowth_route")),
                      "map_profile": engine.graph.generation,
                      "ancient_start": None if state.ancient_start is None else asdict(state.ancient_start),
                      "event_profile": None if state.event_progression is None else state.event_progression.profile,
                      "rooms_visited": len(state.visited_nodes),
                      "route": args.route, "path": args.path, "seed": state.seed,
                      "phase": state.phase.value, "hp": state.hp, "max_hp": state.max_hp,
                      "gold": state.gold, "combats_completed": state.combats_completed,
                      "shop_purchases": sum(t["action"] == "BuyShopItem" for t in trace),
                      "shop_removals": state.shop_removals_used,
                      "chests_opened": sum(t["action"] == "OpenChest" for t in trace),
                      "events_resolved": sum(t["action"] == "ChooseEventOption" for t in trace),
                      "act_completion": None if state.act_completion is None else asdict(state.act_completion),
                      "deck_size": len(state.deck), "relics": [r.definition_id for r in state.relics], "upgraded_cards": [c.instance_id for c in state.deck if c.upgrade_level],
                      "potions_used": sum(t["action"] == "UsePotion" for t in trace),
                      "commands": len(trace), "restore_verified": args.verify_restore,
                      **({"trace": trace} if args.trace else {})}, indent=2))


if __name__ == "__main__":
    main()
