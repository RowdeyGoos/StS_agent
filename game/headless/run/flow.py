"""Direct gameplay command dispatch; room and content rules stay in their modules."""

from game.headless.core.actions import ChooseCombatCard, ConfirmCombatSelection, EndTurn, PlayCard
from game.headless.encounters.catalog import ENCOUNTERS
from game.headless.events.catalog import EVENTS
from game.headless.potions.base import POTIONS
from game.headless.run.actions import (
    ContinueAct, UseRestRelic, ChooseCookCard, ConfirmCook, RerollCardReward, SacrificeCardReward, ChooseExtraReward, ChooseAncientRelic, ChooseNode, ClaimGold, ChooseRewardCard, ClaimPotion, ClaimRelic, LeaveRewards,
    Rest, Smith, Hatch, Lift, Dig, ChooseUpgrade, LeaveRest, UsePotion, DiscardPotion,
    BuyShopItem, BeginShopRemoval, ChooseShopRemoval, LeaveShop,
    OpenChest, ClaimTreasureRelic, LeaveTreasure, ChooseEventOption, ChooseEventCard, LeaveEvent,
)
from game.headless.run import rest_site, rewards, shop, treasure, events, ancient
from game.headless.run.inventory import discard_potion, potion_slot
from game.headless.run.state import RunPhase


def legal_actions(engine) -> tuple:
    state, combat = engine.state, engine.combat
    if state.relic_work:
        from game.headless.relics.pickup import legal_actions as relic_actions
        from game.headless.relics.reward_alternatives import actions as alternatives
        return (*relic_actions(state), *alternatives(state))
    from game.headless.run.campaign import can_continue
    if can_continue(engine):
        return (ContinueAct(),)
    if state.phase in (RunPhase.VICTORY, RunPhase.DEFEAT, RunPhase.SLICE_COMPLETE, RunPhase.ACT_COMPLETE):
        return ()
    if state.phase is RunPhase.ROOM and state.pending.get("kind") == "ancient":
        return ancient.legal_actions(state)
    from game.headless.relics.reward_alternatives import actions as alternatives
    actions = alternatives(state)
    if state.phase is RunPhase.COMBAT:
        actions.extend(combat.legal_actions())
        if combat.player.pending_play is not None or combat.player.rules.selection is not None:
            return tuple(actions)
    elif state.phase is RunPhase.ROUTE and state.pending is None:
        actions.extend(ChooseNode(n) for n in engine.available_nodes())
    elif state.phase is RunPhase.REWARD and state.pending.get("combat_reward"):
        reward = state.pending
        if not reward["gold_claimed"]:
            actions.append(ClaimGold())
        if not reward["card_resolved"]:
            actions.extend(ChooseRewardCard(c) for c in reward["offers"])
            actions.append(ChooseRewardCard(None))
        if reward["potion"] is not None and not reward["potion_claimed"] and None in state.potions:
            actions.append(ClaimPotion())
        if reward["relic"] is not None and not reward["relic_claimed"]:
            actions.append(ClaimRelic())
        for index, extra in enumerate(reward["extra_rewards"]):
            if not extra["resolved"]:
                actions.extend(ChooseExtraReward(index, name) for name in [*(extra["offers"] if extra["kind"] != "potion" or None in state.potions else []), None])
        actions.append(LeaveRewards())
    elif state.phase is RunPhase.ROOM and state.pending.get("kind") == "rest_site":
        stage = state.pending["stage"]
        actions.extend(rest_site.ancient_actions(state))
        from game.headless.relics.run_rules import has, owned
        used = state.pending["used"]
        if stage == "options" or (stage == "hatched" and has(state, "miniature_tent")):
            if "rest" not in used:
                actions.append(Rest())
            from game.headless.run.hatching import eggs
            if eggs(state) and "hatch" not in used:
                actions.append(Hatch())
            if rest_site.eligible_upgrades(state) and "smith" not in used:
                actions.append(Smith())
            if owned(state, "girya") and owned(state, "girya").counter < 3 and "lift" not in used:
                actions.append(Lift())
            if has(state, "shovel") and "dig" not in used:
                actions.append(Dig())
            if used:
                actions.append(LeaveRest())
        elif stage == "smith":
            actions.extend(ChooseUpgrade(c) for c in state.pending["eligible"])
            actions.append(ChooseUpgrade(None))
        elif stage in ("resolved", "hatched"):
            actions.append(LeaveRest())
    if state.phase is RunPhase.ROOM and state.pending.get("kind") == "shop":
        actions.extend(shop.legal_actions(state))
        if state.pending["stage"] == "remove":
            return tuple(actions)
    if state.phase is RunPhase.ROOM and state.pending.get("kind") == "treasure":
        actions.extend(treasure.legal_actions(state))
    if state.phase is RunPhase.ROOM and state.pending.get("kind") == "scripted_event":
        actions.extend(events.legal_actions(state))
        if (state.pending["stage"] == "select_card"
                or state.pending["definition_id"] in ("the_future_of_potions", "ranwid_the_elder", "stone_of_all_time") and state.pending["stage"] != "resolved"):
            return tuple(actions)
    from game.headless.potions.use import actions as potion_actions
    actions.extend(potion_actions(engine))
    actions.extend(DiscardPotion(p.instance_id) for p in state.potions if p is not None)
    return tuple(actions)


def apply(engine, action):
    if action not in legal_actions(engine):
        raise ValueError(f"Illegal run action: {action!r}")
    state = engine.state
    if isinstance(action, ContinueAct):
        return engine.advance_act()
    if isinstance(action, (RerollCardReward, SacrificeCardReward)):
        from game.headless.relics.reward_alternatives import apply as alternate
        return alternate(state, engine.cards, action)
    if engine.combat is not None:
        # Run inventory is authoritative between commands (including direct
        # acquisition through the shared inventory API).
        from dataclasses import asdict
        r = engine.combat.player.rules
        r.gold_available = state.gold
        r.potions = [None if p is None else asdict(p) for p in state.potions]
        r.potion_slots = state.potions.count(None)
        from game.headless.relics.damage import potions_changed
        potions_changed(engine.combat.player)
    if state.relic_work:
        from game.headless.relics.pickup import apply as apply_relic_choice
        result = apply_relic_choice(state, engine.cards, action)
        return result
    if isinstance(action, ChooseAncientRelic):
        return ancient.choose(state, action, cards=engine.cards)
    if isinstance(action, ChooseNode):
        # Unknown resolution and room construction form one transaction. Native
        # outcome odds commit only with a usable room; failures restore navigation,
        # RNG and the unresolved map point together.
        from copy import deepcopy
        before = deepcopy(state)
        try:
            node = engine.choose_node(action.node_id)
            if node.kind in ("combat", "elite", "boss"):
                from game.headless.encounters.progression import encounter_at
                encounter_id = encounter_at(state, node)
                if encounter_id not in ENCOUNTERS or ENCOUNTERS[encounter_id].room_kind != node.kind:
                    raise ValueError("Unsupported or mismatched encounter.")
                return engine.start_combat(encounter_id=encounter_id)
            if node.kind == "event":
                if node.event_id not in EVENTS:
                    raise ValueError("Unsupported map event.")
                if node.row == 0:
                    from game.headless.relics.run_rules import entered_room
                    events.begin(state, node.event_id, cards=engine.cards)
                    entered_room(state, 'event')
                else:
                    events.begin(state, node.event_id, cards=engine.cards)
            elif node.kind == "treasure":
                treasure.begin(state)
            elif node.kind == "shop":
                shop.begin(state, engine.cards)
            elif node.kind == "rest":
                rest_site.begin_rest_site(state)
            elif node.kind not in ("slice_end", "terminal"):
                raise ValueError("Unsupported room.")
            return node
        except Exception:
            state.__dict__.clear()
            state.__dict__.update(before.__dict__)
            engine.combat = None
            raise
    if isinstance(action, (PlayCard, ChooseCombatCard, ConfirmCombatSelection, EndTurn, UsePotion)):
        if isinstance(action, UsePotion):
            from game.headless.potions.use import use
            result = use(engine, action)
            if engine.combat is None:
                return result
        else:
            result = engine.combat.apply(action)
        engine.sync_combat_loot()
        if result.done:
            engine.finish_combat()
        return result
    if isinstance(action, DiscardPotion):
        from dataclasses import asdict
        before = [None if p is None else asdict(p) for p in state.potions]
        result = discard_potion(state, action.instance_id)
        from game.headless.events.potion_context import record
        record(state, before)
        if engine.combat is not None:
            from dataclasses import asdict
            engine.combat.player.rules.potions = [None if p is None else asdict(p) for p in state.potions]
        return result
    if isinstance(action, ChooseEventOption):
        from game.headless.events.combat import EventCombatRequest
        from copy import deepcopy
        before = deepcopy(state)
        try:
            result = events.choose(state, action.event_instance_id, action.option_id, cards=engine.cards)
            if isinstance(result, EventCombatRequest):
                from game.headless.run.event_combat import start
                return start(engine, result)
            return result
        except Exception:
            state.__dict__.clear()
            state.__dict__.update(before.__dict__)
            raise
    if isinstance(action, ChooseEventCard):
        return events.select_card(state, action.event_instance_id, action.card_instance_id, cards=engine.cards)
    if isinstance(action, LeaveEvent):
        return events.leave(state, action.event_instance_id)
    if isinstance(action, OpenChest):
        return treasure.open_chest(state)
    if isinstance(action, ClaimTreasureRelic):
        return treasure.claim_relic(state, action.treasure_id, cards=engine.cards)
    if isinstance(action, LeaveTreasure):
        return treasure.leave(state)
    if isinstance(action, BuyShopItem):
        return shop.buy(state, engine.cards, action.offer_id)
    if isinstance(action, BeginShopRemoval):
        return shop.begin_removal(state)
    if isinstance(action, ChooseShopRemoval):
        return shop.choose_removal(state, action.instance_id)
    if isinstance(action, LeaveShop):
        return shop.leave(state)
    if isinstance(action, ChooseExtraReward):
        return rewards.choose_extra(state, engine.cards, action.index, action.definition_id)
    if isinstance(action, ClaimGold):
        return rewards.claim_gold(state)
    if isinstance(action, ChooseRewardCard):
        return rewards.choose_card(state, engine.cards, action.definition_id)
    if isinstance(action, ClaimRelic):
        return rewards.claim_relic(state, cards=engine.cards)
    if isinstance(action, ClaimPotion):
        return rewards.claim_potion(state)
    if isinstance(action, LeaveRewards):
        return rewards.leave_combat_rewards(state, cards=engine.cards)
    if isinstance(action, UseRestRelic):
        return rest_site.use_ancient(state, engine.cards, action.option)
    if isinstance(action, (ChooseCookCard, ConfirmCook)):
        return rest_site.cook_choice(state, action)
    if isinstance(action, Lift):
        return rest_site.lift(state)
    if isinstance(action, Dig):
        return rest_site.dig(state)
    if isinstance(action, Rest):
        return rest_site.heal(state, cards=engine.cards)
    if isinstance(action, Hatch):
        from game.headless.run.hatching import hatch
        return hatch(state, engine.cards)
    if isinstance(action, Smith):
        return rest_site.begin_smith(state)
    if isinstance(action, ChooseUpgrade):
        return rest_site.choose_upgrade(state, action.instance_id)
    if isinstance(action, LeaveRest):
        return rest_site.leave(state)
    raise ValueError("Unsupported run command.")
