"""A deterministic reference chooser whose only input is the public contract.

This is an integration policy, not a win-rate claim or an RL encoding. It uses
only advertised candidates and never builds a backend command.
"""
from game.agent import contracts as c


def choose_action(decision: c.PublicDecision) -> c.Candidate:
    c.require_ready(decision)
    context, actions = decision.context, decision.candidates
    if isinstance(context, c.CardSelection):
        # Exercise optional selectors too, while guaranteeing a bounded choice.
        select = [a for a in actions if a.kind == 'select_card']
        if select and len(context.selected) < context.maximum:
            return select[0]
        return next(a for a in actions if a.kind == 'confirm_selection')
    if isinstance(context, c.Combat):
        hand = {card.ref: card for pile in context.piles if pile.kind == 'hand' for card in pile.cards.value}
        enemies = {enemy.ref: enemy for enemy in context.enemies}
        plays = [a for a in actions if a.kind == 'play_card']
        if plays:
            def score(action):
                values = {v.key: v.amount for v in hand[action.subject].values.value}
                # Resolve attack ties toward low HP, using public enemy refs.
                return (values.get('damage', 0) * values.get('hits', 1), values.get('block', 0),
                        -enemies[action.target].hp if action.target else 0)
            return max(plays, key=score)
        return next(a for a in actions if a.kind == 'end_turn')
    if isinstance(context, c.Rewards):
        rewards = {reward.ref: reward for reward in context.entries}
        # Potions introduce command families outside this first profile; the
        # integration policy leaves those optional drops for milestone 5.
        for kind in ('claim_reward', 'open_card_reward', 'choose_reward_card', 'skip_reward', 'leave_rewards'):
            options = [a for a in actions if a.kind == kind and
                       (kind != 'claim_reward' or rewards[a.subject].kind == 'gold')]
            if options:
                return options[0]
    return actions[0]
