"""Deterministic integration chooser over the v2 public contract only.

It exercises every decision family; it is neither an optimal player nor a
victory guarantee. The environment owns rollout budgets and terminal outcomes.
"""
from game.agent.contracts import full as f


def choose_action(decision):
    f.require_ready(decision)
    actions, context = decision.candidates, decision.context
    entities = {n.ref: n for root in (decision.run, context) for n in f.walk(root) if n.ref}
    def of(*kinds):
        return [a for a in actions if a.kind in kinds]
    if context.kind == 'combat':
        selections = [n for n in f.walk(context) if n.kind == 'selection']
        if selections:
            selected = len(selections[0].linked('selected'))
            if selected >= selections[0].get('minimum') and of('confirm_selection'):
                return of('confirm_selection')[0]
            return of('select_card')[0]
        uses = of('use_potion')
        if uses and decision.run.get('hp') * 2 < decision.run.get('max_hp'):
            return uses[0]
        plays = of('play_card')
        if plays:
            def score(action):
                card = entities[action.subject]
                # Native values are displayed previews, while the headless
                # descriptor exposes static specifications. Keep that distinction
                # in the contract and use either for this demonstration score.
                preview = next((n for n in card.children if n.kind == 'preview'), None)
                spec = next((n for n in card.children if n.kind == 'spec'), None)
                damage = preview.get('damage', 0) if preview else spec.get('base_damage', 0) if spec else 0
                block = preview.get('block', 0) if preview else spec.get('block_gain', 0) if spec else 0
                target_hp = (entities[action.target].get('hp') or 0) if action.target else 0
                return (damage, block, -target_hp)
            return max(plays, key=score)
        return of('end_turn')[0]
    if context.kind == 'relic_choice':
        confirms = of('confirm_relic_selection')
        selected = len(context.linked('selected'))
        if confirms and (selected or context.definition_id != 'card_grid'):
            return confirms[0]
        choices = of('choose_relic_card', 'choose_relic_reward')
        if choices:
            return choices[0]
    if context.kind == 'rest':
        selections = [n for n in f.walk(context) if n.kind == 'selection']
        if selections and of('confirm_selection') and len(selections[0].linked('selected')) >= selections[0].get('minimum'):
            return of('confirm_selection')[0]
        if of('confirm_cook'):
            return of('confirm_cook')[0]
        choices = of('choose_cook_card', 'choose_upgrade')
        if choices:
            return choices[0]
        rest = of('rest')
        if rest and decision.run.get('hp') * 3 < decision.run.get('max_hp') * 2:
            return rest[0]
        for kind in ('smith', 'rest', 'hatch', 'lift', 'dig', 'use_rest_relic', 'leave_rest'):
            if of(kind):
                return of(kind)[0]
    for kind in ('choose_event_card', 'choose_shop_removal', 'claim_gold', 'claim_relic', 'claim_potion',
                 'choose_reward_card', 'choose_extra_reward', 'choose_ancient_relic', 'open_chest',
                 'claim_treasure_relic', 'buy_shop_item', 'continue_act', 'open_reward', 'open_shop'):
        if of(kind):
            return of(kind)[0]
    events = of('choose_event_option')
    if events:
        def score(action):
            label = entities[action.subject].definition_id
            # Claim current offers before leaving; exit repeated risk pages and
            # avoid deliberate abandonment in ordinary demonstration rollouts.
            if label.startswith(('reward_', 'claim', 'card_')):
                return 3
            if label in ('leave', 'exit_baths', 'proceed', 'accept', 'finish_rewards', 'give_up'):
                return 2
            if label.startswith(('skip', 'small_')) or label in ('double_down', 'reject'):
                return 0
            return 1
        return max(events, key=score)
    for kind in ('leave_rewards', 'leave_event', 'leave_treasure', 'leave_shop', 'skip_reward',
                 'confirm_selection', 'confirm_relic_selection', 'close_shop', 'cancel_selection'):
        if of(kind):
            return of(kind)[0]
    maps = of('choose_map_node')
    if maps:
        preference = {'rest': 5, 'treasure': 4, 'event': 3, 'unknown': 2, 'combat': 1, 'elite': -1}
        return max(maps, key=lambda a: preference.get(entities[a.subject].definition_id, 0))
    # Every candidate is legal, including otherwise unused optional alternatives.
    return actions[0]
