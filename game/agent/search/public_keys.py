"""Semantic keys derived only from public graphs and visible positions."""


def public_key(decision):
    """Complete successor comparison, including persistent inventory and HUD.

    Live references are normalized to public positions. Gone history subjects
    retain their namespace; the session separately verifies every historical
    action against its original public decision, before that subject disappears.
    """
    paths = _paths(decision)
    def visit(node):
        return (node.kind, node.definition_id,
                tuple(sorted((v.key, v.value) for v in node.fields)),
                tuple(sorted((link.key, tuple(paths.get(ref, ('past', ref.split(':')[0]))
                                             for ref in link.targets)) for link in node.links)),
                tuple(visit(child) for child in node.children))
    return visit(decision.run), visit(decision.context), tuple(action_key(decision, a) for a in decision.candidates)


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
        for index, child in enumerate(node.children):
            visit(child, (*path, index))
    visit(decision.run, ('run',))
    visit(decision.context, ('context',))
    return paths


def action_key(decision, action):
    """Visible positions, never physical IDs or private duplicate associations."""
    paths = _paths(decision)
    return action.kind, paths.get(action.subject), paths.get(action.target)


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
            tuple(action_key(decision, a) for a in decision.candidates))
