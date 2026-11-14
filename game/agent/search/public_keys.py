"""Semantic keys derived only from public graphs and visible positions."""
from game.agent.contracts.full import remember, shared_height

# Keys of shared descriptions (a card's spec and mechanics). Such a node has no
# reference and no link, so its key involves no path and is the same wherever
# and whenever the node appears. Each entry keeps and confirms its node.
_DESCRIPTION_KEYS = {}


def public_key(decision):
    """Complete successor comparison, including persistent inventory and HUD.

    Live references are normalized to public positions. Gone history subjects
    retain their namespace; the session separately verifies every historical
    action against its original public decision, before that subject disappears.
    """
    paths = _paths(decision)
    def compute(node):
        return (node.kind, node.definition_id,
                tuple(sorted((v.key, v.value) for v in node.fields)),
                tuple(sorted((link.key, tuple(paths.get(ref, ('past', ref.split(':')[0]))
                                             for ref in link.targets)) for link in node.links)),
                tuple(visit(child) for child in node.children))
    def visit(node):
        if node.ref is not None:
            return compute(node)
        entry = _DESCRIPTION_KEYS.get(id(node))
        if entry is not None and entry[0] is node:
            return entry[1]
        key = compute(node)
        if shared_height(node) is not None:
            remember(_DESCRIPTION_KEYS, node, key)
        return key
    return visit(decision.run), visit(decision.context), tuple(action_key(decision, a, paths) for a in decision.candidates)


def end_key(value):
    # A settled run has no candidates/context. Reuse the same public reference
    # normalization for its persistent deck, relics, potions and history.
    from game.agent.contracts.full import PublicDecision, Node
    view = PublicDecision('sts_public_decision_v2', 'full_run_v2', value.run, Node('terminal', 'combat_complete'), ())
    return value.result, public_key(view)[0]

def _paths(decision):
    paths = {}
    def visit(node, path):
        if node.ref:
            paths[node.ref] = path
        elif node.children and shared_height(node) is not None:
            return  # A shared description holds no reference at any depth.
        for index, child in enumerate(node.children):
            visit(child, (*path, index))
    visit(decision.run, ('run',))
    visit(decision.context, ('context',))
    return paths


def action_key(decision, action, paths=None):
    """Visible positions, never physical IDs or private duplicate associations.

    `paths` is `_paths(decision)` when the caller keys several actions of one
    observation; it is derived here otherwise.
    """
    if paths is None:
        paths = _paths(decision)
    return action.kind, paths.get(action.subject), paths.get(action.target)


def action_keys(decision, actions=None):
    """action_key for each action (every candidate by default), walking the observation once."""
    paths = _paths(decision)
    return [action_key(decision, a, paths) for a in (decision.candidates if actions is None else actions)]


def observation_key(decision):
    paths = _paths(decision)
    def visit(node):
        children = [visit(c) for c in node.children]
        if node.kind in ('powers', 'enemy'):
            children.sort(key=repr)
        return (node.kind, node.definition_id,
                tuple(sorted((v.key, v.value) for v in node.fields)),
                tuple((l.key, tuple(paths.get(r, ('past', r.split(':')[0])) for r in l.targets)) for l in node.links),
                tuple(children))
    # History is represented by the path through the tree, not merged away.
    return (visit(decision.context),
            tuple(visit(n) for n in decision.run.children if n.kind in ('potions', 'relics')),
            tuple(action_key(decision, a, paths) for a in decision.candidates))
