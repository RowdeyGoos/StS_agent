"""Direct gameplay command dispatch; room and content rules stay in their modules."""

from game.headless.core.actions import ChooseCombatCard, EndTurn, PlayCard
from game.headless.encounters.catalog import ENCOUNTERS
from game.headless.potions.base import POTIONS
from game.headless.run.actions import (
    ChooseNode, ClaimGold, ChooseRewardCard, ClaimPotion, ClaimRelic, LeaveRewards,
    Rest, Smith, ChooseUpgrade, LeaveRest, UsePotion, DiscardPotion,
    BuyShopItem, BeginShopRemoval, ChooseShopRemoval, LeaveShop,
)
from game.headless.run import rest_site, rewards, shop
from game.headless.run.inventory import discard_potion, potion_slot
from game.headless.run.state import RunPhase


def legal_actions(engine) -> tuple:
    state, combat = engine.state, engine.combat
    if state.phase in (RunPhase.VICTORY, RunPhase.DEFEAT, RunPhase.SLICE_COMPLETE, RunPhase.ACT_COMPLETE):
        return ()
    actions = []
    if state.phase is RunPhase.COMBAT:
        actions.extend(combat.legal_actions())
        if combat.player.pending_play is not None:
            return tuple(actions)
        if not combat.done:
            for potion in state.potions:
                if potion is None:
                    continue
                definition = POTIONS[potion.definition_id]
                targets = [i for i, e in enumerate(combat.enemies) if e.is_alive] if definition.targeted else [None]
                actions.extend(UsePotion(potion.instance_id, target) for target in targets)
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
        actions.append(LeaveRewards())
    elif state.phase is RunPhase.ROOM and state.pending.get("kind") == "rest_site":
        stage = state.pending["stage"]
        if stage == "options":
            actions.append(Rest())
            if rest_site.eligible_upgrades(state):
                actions.append(Smith())
        elif stage == "smith":
            actions.extend(ChooseUpgrade(c) for c in state.pending["eligible"])
            actions.append(ChooseUpgrade(None))
        elif stage == "resolved":
            actions.append(LeaveRest())
    if state.phase is RunPhase.ROOM and state.pending.get("kind") == "shop":
        actions.extend(shop.legal_actions(state))
        if state.pending["stage"] == "remove":
            return tuple(actions)
    actions.extend(DiscardPotion(p.instance_id) for p in state.potions if p is not None)
    return tuple(actions)


def apply(engine, action):
    if action not in legal_actions(engine):
        raise ValueError(f"Illegal run action: {action!r}")
    state = engine.state
    if isinstance(action, ChooseNode):
        # Resolve content before moving the cursor, so unsupported rooms cannot
        # strand an otherwise usable run or consume the launch RNG.
        node = engine.graph.node(action.node_id)
        if node.kind in ("combat", "elite", "boss"):
            if node.encounter_id not in ENCOUNTERS:
                raise ValueError("Unsupported encounter.")
            encounter = ENCOUNTERS[node.encounter_id]
            if encounter.room_kind != node.kind:
                raise ValueError("Map room and encounter kind disagree.")
        elif node.kind not in ("rest", "shop", "slice_end", "terminal"):
            raise ValueError("Unsupported room.")
        previous_node, previous_pending = state.current_node_id, state.pending
        engine.choose_node(action.node_id)
        if node.kind in ("combat", "elite", "boss", "shop"):
            try:
                if node.kind == "shop":
                    shop.begin(state, engine.cards)
                    return node
                return engine.start_combat(encounter_id=node.encounter_id)
            except Exception:
                # Room construction builds independently before committing. Restore
                # the preceding navigation too if encounter construction fails.
                state.current_node_id, state.pending = previous_node, previous_pending
                state.visited_nodes.pop()
                raise
        if node.kind == "rest":
            rest_site.begin_rest_site(state)
        return node
    if isinstance(action, (PlayCard, ChooseCombatCard, EndTurn, UsePotion)):
        if isinstance(action, UsePotion):
            slot = potion_slot(state, action.instance_id)
            POTIONS[state.potions[slot].definition_id].use(engine.combat, action.target_slot)
            state.potions[slot] = None
            result = engine.combat.resolve_external_effect()
        else:
            result = engine.combat.apply(action)
        if result.done:
            engine.finish_combat()
        return result
    if isinstance(action, DiscardPotion):
        return discard_potion(state, action.instance_id)
    if isinstance(action, BuyShopItem):
        return shop.buy(state, engine.cards, action.offer_id)
    if isinstance(action, BeginShopRemoval):
        return shop.begin_removal(state)
    if isinstance(action, ChooseShopRemoval):
        return shop.choose_removal(state, action.instance_id)
    if isinstance(action, LeaveShop):
        return shop.leave(state)
    if isinstance(action, ClaimGold):
        return rewards.claim_gold(state)
    if isinstance(action, ChooseRewardCard):
        return rewards.choose_card(state, engine.cards, action.definition_id)
    if isinstance(action, ClaimRelic):
        return rewards.claim_relic(state)
    if isinstance(action, ClaimPotion):
        return rewards.claim_potion(state)
    if isinstance(action, LeaveRewards):
        return rewards.leave_combat_rewards(state)
    if isinstance(action, Rest):
        return rest_site.heal(state)
    if isinstance(action, Smith):
        return rest_site.begin_smith(state)
    if isinstance(action, ChooseUpgrade):
        return rest_site.choose_upgrade(state, action.instance_id)
    if isinstance(action, LeaveRest):
        return rest_site.leave(state)
    raise ValueError("Unsupported run command.")
