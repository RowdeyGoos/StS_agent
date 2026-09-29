"""Act progress measured only from the existing public campaign boundary."""
from game.agent.contracts import full as f


def completed_act(public):
    """Return the act whose boss rewards have been left, or no completion.

    A later floor, a won ordinary fight, and entering the Architect are not new
    act completions. Generated campaigns expose this decision before ContinueAct.
    """
    if type(public) is not f.PublicDecision or public.context.kind != 'act_transition':
        return None
    act = public.context.get('completed_act')
    if (type(act) is not int or act not in (1, 2, 3) or
            type(public.run.get('act')) is not int or public.run.get('act') != act):
        raise ValueError('Invalid public act completion')
    return act


def cleared_act(before, successor):
    current = completed_act(successor)
    return current if current is not None and current != completed_act(before) else None
