"""Owned Spoils Map quest markers and chest completion, without resolver callbacks."""


def generate(state, graph):
    owners = [c.instance_id for c in state.deck if c.definition.definition_id == 'spoils_map']
    state.spoils_map = None
    if state.act_index != 1 or not owners:
        return graph
    from game.headless.core.rng import GameRandomService
    from game.headless.core.native_service import NativeRandomService
    from game.headless.map.standard import generate_map, SPOILS_PROFILE
    # Each native modifier constructs a fresh root-seeded map RNG. It does not
    # advance a persistent run stream, even with several copies in the deck.
    rng = NativeRandomService(state.seed) if getattr(state.rng, 'native', False) else GameRandomService(state.seed)
    root = graph.node('act2.ancient')
    graph = generate_map(rng, act='hive', event_pool=state.config.event_pool, ancient=root.event_id, profile=SPOILS_PROFILE)
    state.spoils_map = dict(card_ids=owners, target=first_treasure(graph))
    return graph


def first_treasure(graph):
    return min((n for n in graph.nodes if n.kind == 'treasure'), key=lambda n: (n.column, n.row)).node_id


def retarget(state, graph):
    if state.spoils_map is not None:
        state.spoils_map['target'] = first_treasure(graph)


def complete(state):
    quest = state.spoils_map
    copies = [c for c in state.deck if c.definition.definition_id == 'spoils_map']
    if quest is None or state.current_node_id != quest['target'] or not any(c.instance_id in quest['card_ids'] for c in copies):
        return
    from game.headless.relics.run_rules import gain_gold
    from game.headless.run.deck import remove_card
    for card in copies:
        gain_gold(state, 600)
        remove_card(state, card.instance_id)


def validate(state, graph):
    quest = state.spoils_map
    from game.headless.map.standard import SPOILS_PROFILE
    if quest is None:
        if graph is not None and SPOILS_PROFILE in (graph.generation, graph.replaced_generation):
            raise ValueError('Spoils map has no quest owner.')
        return
    from game.headless.map.golden_path import PROFILE as GOLDEN
    if (state.act_index != 1 or graph is None or graph.generation not in (SPOILS_PROFILE, GOLDEN)
            or not isinstance(quest, dict) or set(quest) != {'card_ids', 'target'}
            or quest['target'] != first_treasure(graph)):
        raise ValueError('Invalid Spoils Map quest target.')
    ids = quest['card_ids']
    if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Invalid Spoils Map quest owners.')
    for identity in ids:
        suffix = identity.removeprefix('run.card.')
        if not suffix.isdigit() or identity != f'run.card.{int(suffix)}' or int(suffix) >= state.next_card_id:
            raise ValueError('Unallocated Spoils Map quest owner.')
        card = next((c for c in state.deck if c.instance_id == identity), None)
        if card is not None and card.definition.definition_id != 'spoils_map':
            raise ValueError('Spoils Map marker belongs to another card.')
