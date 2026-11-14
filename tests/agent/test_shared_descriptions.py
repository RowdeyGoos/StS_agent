"""Readers reuse what they derive from shared card descriptions and change no result.

The oracle throughout is a private copy of the same observation: its nodes are
fresh objects, none of them registered, so every reader takes its full path.
"""
from dataclasses import replace

import numpy as np
import pytest

from game.agent.contracts import full as f
from game.agent.encoding import full_records
from game.agent.encoding.full import FullRunEncoder, FullRunProfile
from game.agent.encoding.schema import CapacityError
from game.agent.full_policy import choose_action
from game.agent.search import public_keys
from game.agent.search.public_keys import _paths, action_key, public_key
from game.agent.search.world import SimulationWorld
from game.agent.training import combat_features
from game.agent.training.combat_features import COMBAT, channels
from game.agent.training.features import FeatureEncoder, Vocabulary
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine

ARRAYS = ('nodes', 'parents', 'positions', 'fields', 'numbers', 'links', 'link_positions', 'candidates',
          'combat', 'roles')


def _fight(seed=0, steps=40):
    """(shared observation, its owner, private copy, the copy's owner) along one searched fight."""
    run = RunEngine(seed=seed, config=RunConfig(), card_ids=(
        'strike', 'strike', 'strike', 'defend', 'defend', 'bash', 'pommel_strike', 'shrug_it_off', 'inflame'))
    run.start_combat(cards_per_turn=3)
    world = SimulationWorld(run)
    observation = world.project()
    for _ in range(steps):
        owner = f.PreparedPublic(observation)
        assert owner.value == observation and owner.value is not observation
        yield observation, world.prepared, owner.value, owner
        observation = world.step(observation, action_key(observation, choose_action(observation)))
        if observation is None:
            break


def _shared(decision):
    return [n for root in (decision.run, decision.context) for n in f.walk(root) if f.shared_height(n) is not None]


def _same_features(left, right):
    for name in ARRAYS:
        a, b = getattr(left, name), getattr(right, name)
        if a is None or b is None:
            assert a is None and b is None, name  # The plain graph has no combat channels.
            continue
        assert a.dtype == b.dtype and a.shape == b.shape and np.array_equal(a, b), name
        assert not a.flags.writeable
    for name in ('vocabulary', 'roots', 'action_policy', 'policy_mask', 'candidate_refs', 'legal_mask',
                 'preview_mode', 'input_view'):
        assert getattr(left, name) == getattr(right, name), name


def _outcome(call):
    try:
        return call()
    except Exception as error:  # The comparison is the point: same value or same error.
        return type(error), error.args


def test_a_search_observation_shares_its_card_descriptions_and_a_copy_shares_none():
    seen = 0
    for observation, _, copy, _ in _fight():
        shared = _shared(observation)
        assert shared and {n.kind for n in shared} <= {'spec', 'mechanic'}
        assert all(n.ref is None and not n.links for n in shared)
        assert not _shared(copy)
        seen += 1
    assert seen >= 5


@pytest.mark.parametrize('seed', (0, 7))
def test_every_reader_agrees_between_shared_and_copied_observations(seed):
    observations = list(_fight(seed))
    vocabulary = Vocabulary.fit([copy for _, _, copy, _ in observations], split='train')
    small = Vocabulary.fit([observations[0][2]], split='train', include_catalog=False)
    encoders = [FeatureEncoder(vocabulary, representation=COMBAT), FeatureEncoder(small, representation=COMBAT),
                FeatureEncoder(vocabulary)]
    public = FullRunEncoder()
    for observation, owner, copy, copy_owner in observations:
        f.validate(observation)
        assert f._exact_decision(observation) and f.PreparedPublic.adopt(observation).value is observation
        # Twice: the first reading may fill what the second reuses.
        for _ in range(2):
            assert public_key(observation) == public_key(copy)
            assert _paths(observation) == _paths(copy)
            assert public.mapping_prepared(observation, owner) == public.mapping_prepared(copy, copy_owner)
            for encoder in encoders:
                _same_features(encoder.encode_prepared(observation, owner), encoder.encode_prepared(copy, copy_owner))
                _same_features(encoder.encode_inference(observation), encoder.encode_inference(copy))
    # The comparison above exercised reuse: every store holds this fight's descriptions.
    specs = {id(n) for observation, *_ in observations for n in _shared(observation) if n.kind == 'spec'}
    for store in (public_keys._DESCRIPTION_KEYS, full_records._DESCRIPTION_ROWS, combat_features._SPEC_VALUES,
                  combat_features._DESCRIPTION_VALUES, *(e._description_rows for e in encoders)):
        assert specs and specs <= set(store)


def test_the_channels_of_a_description_do_not_depend_on_which_reader_met_it_first():
    observation, _, copy, _ = next(iter(_fight(3)))
    for decision in (observation, copy):
        nodes, parents = [], []

        def visit(node, parent):
            index = len(nodes)
            nodes.append(node)
            parents.append(parent)
            for child in node.children:
                visit(child, index)

        visit(decision.run, -1)
        visit(decision.context, -1)
        values, roles = channels(nodes, parents)
        if decision is observation:
            expected = values, roles
    assert np.array_equal(values, expected[0]) and np.array_equal(roles, expected[1])
    assert values.any() and (roles >= 0).any()


def test_mapping_capacities_fail_exactly_as_the_row_by_row_traversal_does():
    observation, _, copy, _ = next(iter(_fight(1)))
    assert _shared(observation)
    reference = full_records.pack_records(FullRunEncoder(), copy, mapping_only=True)

    def fits(capacity):
        return type(_outcome(lambda: full_records.pack_records(
            FullRunEncoder(FullRunProfile(nodes=capacity)), copy, mapping_only=True))) is not tuple

    low, rows = 1, 131072  # The exact number of rows this observation needs.
    while low < rows:
        middle = (low + rows) // 2
        low, rows = (low, middle) if fits(middle) else (middle + 1, rows)
    assert rows > 2000 and fits(rows) and not fits(rows - 1)
    texts = {t for root in (copy.run, copy.context) for n in f.walk(root)
             for t in (n.kind, n.definition_id, *(v.key for v in n.fields), *(l.key for l in n.links),
                       *(v.value for v in n.fields if type(v.value) is str))}
    profiles = [FullRunProfile(nodes=n) for n in range(max(1, rows - 400), rows + 3)]
    profiles += [FullRunProfile(strings=n) for n in range(1, len(texts) + 3)]
    profiles += [FullRunProfile(string_bytes=n) for n in range(1, 40)]
    profiles += [FullRunProfile(references=n) for n in (1, 5, 50)]
    failures = 0
    for profile in profiles:
        encoder = FullRunEncoder(profile)
        expected = _outcome(lambda: full_records.pack_records(encoder, copy, mapping_only=True))
        failures += type(expected) is tuple
        for decision in (observation, copy):
            assert _outcome(lambda: full_records.pack_records(
                encoder, decision, mapping_only=True, descriptions=True)) == expected, profile
            assert _outcome(lambda: full_records.pack_records(encoder, decision, mapping_only=True)) == expected
    assert 0 < failures < len(profiles)
    assert full_records.pack_records(FullRunEncoder(), observation, mapping_only=True, descriptions=True) == reference


def _with_description(observation, description):
    """The observation with `description` as the first child of its first deck card."""
    deck = observation.run.children[0]
    card = deck.children[0]
    card = replace(card, children=(description, *card.children[1:]))
    return replace(observation, run=replace(observation.run, children=(
        replace(deck, children=(card, *deck.children[1:])), *observation.run.children[1:])))


def test_an_oversized_integer_in_a_description_is_still_refused():
    observation = next(iter(_fight(2)))[0]
    large = f.share_description(f.Node('mechanic', 'Enormous', fields=(f.Field('amount', 2 ** 40),)))
    assert f.shared_height(large) == 0
    changed = _with_description(observation, large)
    owner = f.PreparedPublic.adopt(changed)
    for _ in range(2):
        with pytest.raises(CapacityError) as error:
            FullRunEncoder().mapping_prepared(changed, owner)
        assert error.value.dimension == 'integer_magnitude'


@pytest.mark.parametrize('node', [
    f.Node('mechanic', 'Named', 'card:7'),
    f.Node('mechanic', 'Linked', links=(f.Link('next', ()),)),
    f.Node('mechanic', 'Pointing', fields=(f.Field('at', 'card:3'),)),
    f.Node('mechanic', 'Twice', fields=(f.Field('a', 1), f.Field('a', 2))),
    f.Node('mechanic', 'Unnamed', fields=(f.Field('', 1),)),
    f.Node('', 'Kindless'), f.Node('mechanic', ''),
    f.Node('mechanic', 'Float', fields=(f.Field('amount', 1.5),)),
    f.Node('mechanic', 'List', fields=[f.Field('amount', 1)]),
    f.Node('mechanic', 'Parent', children=(f.Node('parameters', 'p', 'card:9'),)),
    f.Node('mechanic', 'Parent', children=(f.Node('parameters', 'p', links=(f.Link('k', ('card:1',)),)),)),
])
def test_only_reference_free_valid_exact_records_are_registered(node):
    assert f.share_description(node) is node
    assert f.shared_height(node) is None


def test_registration_names_one_object_and_is_emptied_at_its_limit(monkeypatch):
    child = f.Node('parameters', 'amounts', fields=(f.Field('0', 1), f.Field('1', True)))
    node = f.Node('mechanic', 'Registered', fields=(f.Field('amount', 3), f.Field('name', 'x')), children=(child,))
    twin = f.Node('mechanic', 'Registered', fields=(f.Field('amount', 3), f.Field('name', 'x')), children=(child,))
    assert f.share_description(node) is node and f.share_description(node) is node
    assert f.shared_height(node) == 1 and f.shared_height(child) is None
    assert twin == node and f.shared_height(twin) is None
    # An entry found under an object's id counts only for that very object.
    late = f.Node('mechanic', 'Late')
    monkeypatch.setitem(f._DESCRIPTIONS, id(late), (node, 1))
    assert f.shared_height(late) is None and not f._exact_node(f.Node('x', 'y', fields=[1]), 0)
    # At the limit the registry starts again; a description is registered when it is next used.
    monkeypatch.setattr(f, 'DESCRIPTION_LIMIT', len(f._DESCRIPTIONS))
    assert f.share_description(late) is late and f.shared_height(late) == 0
    assert len(f._DESCRIPTIONS) == 1 and f.shared_height(node) is None
    assert f.share_description(node) is node and f.shared_height(node) == 1


def test_small_stores_are_emptied_and_refilled_without_changing_any_result(monkeypatch):
    import game.agent.headless.full_cards as cards
    monkeypatch.setattr(f, 'DESCRIPTION_LIMIT', 3)
    monkeypatch.setattr(cards, 'DESCRIPTION_LIMIT', 3)
    for module, name in ((f, '_DESCRIPTIONS'), (cards, '_STATIC_VALUES'), (public_keys, '_DESCRIPTION_KEYS'),
                         (full_records, '_DESCRIPTION_ROWS'), (combat_features, '_SPEC_VALUES'),
                         (combat_features, '_DESCRIPTION_VALUES')):
        monkeypatch.setattr(module, name, {})
    observations = list(_fight(4, steps=6))
    encoder = FeatureEncoder(Vocabulary.fit([copy for _, _, copy, _ in observations], split='train'), representation=COMBAT)
    public = FullRunEncoder()
    for observation, owner, copy, copy_owner in observations:
        assert copy == observation
        f.validate(observation)
        assert f._exact_decision(observation)
        assert public_key(observation) == public_key(copy)
        assert public.mapping_prepared(observation, owner) == public.mapping_prepared(copy, copy_owner)
        _same_features(encoder.encode_prepared(observation, owner), encoder.encode_prepared(copy, copy_owner))
    stores = (f._DESCRIPTIONS, cards._STATIC_VALUES, public_keys._DESCRIPTION_KEYS, full_records._DESCRIPTION_ROWS,
              combat_features._SPEC_VALUES, combat_features._DESCRIPTION_VALUES, encoder._description_rows)
    assert all(1 <= len(store) <= 3 for store in stores[:2]) and all(len(store) <= 3 for store in stores)


def test_definition_values_are_described_once_per_object_and_registered_on_every_use(monkeypatch):
    import game.agent.headless.full_cards as cards
    from game.headless.cards.catalog import DEFAULT_CARDS
    card = DEFAULT_CARDS.create('bash')
    spec = card.spec
    first = cards.cached_static(spec, 'spec', 'card_spec')
    assert cards.cached_static(spec, 'spec', 'card_spec') is first == cards.public_static(spec, 'spec', 'card_spec')
    assert f.shared_height(first) == 0
    assert cards.cached_static(spec, 'mechanic', 'card_spec') == cards.public_static(spec, 'mechanic', 'card_spec')
    # A description kept for another object under the same id is not used.
    other = DEFAULT_CARDS.create('strike').spec
    monkeypatch.setitem(cards._STATIC_VALUES, (id(spec), 'spec', 'card_spec'), (other, f.Node('spec', 'wrong')))
    described = cards.cached_static(spec, 'spec', 'card_spec')
    assert described == first  # Read again; an equal description, not necessarily the same object.
    first = described
    # After the registry is emptied, the next use registers the description again.
    monkeypatch.setattr(f, '_DESCRIPTIONS', {})
    assert f.shared_height(first) is None
    assert cards.cached_static(spec, 'spec', 'card_spec') is first and f.shared_height(first) == 0

    class Mutable:
        pass

    before = len(cards._STATIC_VALUES)
    assert cards.cached_static(Mutable(), 'mechanic', 'Mutable') == f.Node('mechanic', 'Mutable')
    assert len(cards._STATIC_VALUES) == before


def test_a_description_with_a_reference_shaped_name_is_packed_row_by_row():
    observation = next(iter(_fight(2)))[0]
    for odd in (f.Node('mechanic', 'card:3'), f.Node('card:4', 'Odd'), f.Node('mechanic', 'Odd', fields=(f.Field('card:5', 1),))):
        assert f.shared_height(f.share_description(odd)) == 0
        changed = _with_description(observation, odd)
        owner, copy_owner = f.PreparedPublic.adopt(changed), f.PreparedPublic(changed)
        expected = FullRunEncoder().mapping_prepared(copy_owner.value, copy_owner)
        for _ in range(2):
            assert FullRunEncoder().mapping_prepared(changed, owner) == expected
        assert full_records._DESCRIPTION_ROWS[id(odd)][2] is None
        assert public_key(changed) == public_key(copy_owner.value)


def test_a_summary_read_with_another_reference_pattern_is_not_used():
    import re
    observation = next(iter(_fight(2)))[0]
    spec = next(n for n in _shared(observation) if n.kind == 'spec')
    FullRunEncoder().mapping_prepared(observation, f.PreparedPublic.adopt(observation))
    assert full_records._DESCRIPTION_ROWS[id(spec)][1] is FullRunEncoder.reference_pattern
    assert full_records._description_rows(spec, re.compile(r'spec\Z')) is None  # Its kind is a reference there.


@pytest.mark.parametrize('kind', ['combat', 'enemy', 'card', 'potion', 'selection', 'mechanic'])
def test_channels_treat_a_shared_description_by_its_place_like_any_other_node(kind):
    observation = next(iter(_fight(8)))[0]
    spec = next(n for n in _shared(observation) if n.kind == 'spec')
    fields = (f.Field('hp', 30), f.Field('max_hp', 60), f.Field('alive', True), f.Field('block', 2), f.Field('amount', 4))
    children = (spec,) if kind == 'card' else ()
    shared = f.share_description(f.Node(kind, 'placed', fields=fields, children=children))
    plain = f.Node(kind, 'placed', fields=fields, children=(replace(spec),) if children else ())
    assert f.shared_height(shared) is not None and f.shared_height(plain) is None and plain == shared
    hand = next(i for i, n in enumerate(observation.context.children) if (n.kind, n.definition_id) == ('pile', 'hand'))
    potions = next(i for i, n in enumerate(observation.run.children) if n.kind == 'potions')

    def placed(node):
        context, run = observation.context, observation.run
        pile = replace(context.children[hand], children=(*context.children[hand].children, node))
        slot = f.Node('potion_slot', 'potion_slot', fields=(f.Field('index', 9),), children=(node,))
        belt = replace(run.children[potions], children=(*run.children[potions].children, slot))
        yield replace(observation, context=replace(context, children=(*context.children, node)))  # Under the combat root.
        yield replace(observation, context=replace(context, children=(*context.children[:hand], pile, *context.children[hand + 1:])))
        yield replace(observation, run=replace(run, children=(*run.children[:potions], belt, *run.children[potions + 1:])))
        yield replace(observation, context=node)  # As a root.
        yield replace(observation, run=node, context=node)

    def flat(decision):
        nodes, parents = [], []

        def visit(node, parent):
            index = len(nodes)
            nodes.append(node)
            parents.append(parent)
            for child in node.children:
                visit(child, index)

        visit(decision.run, -1)
        visit(decision.context, -1)
        return nodes, parents

    for with_shared, with_plain in zip(placed(shared), placed(plain)):
        for _ in range(2):
            values, roles = channels(*flat(with_shared))
            expected_values, expected_roles = channels(*flat(with_plain))
            assert np.array_equal(values, expected_values) and np.array_equal(roles, expected_roles)
    assert (id(shared) in combat_features._DESCRIPTION_VALUES) is (kind == 'mechanic')


def test_an_unknown_shared_entity_is_refused_on_every_encoding():
    observation, _, copy, _ = next(iter(_fight(9)))
    encoder = FeatureEncoder(Vocabulary.fit([copy], split='train'), representation=COMBAT)
    assert encoder.vocabulary.catalog is not None
    unknown = f.share_description(f.Node('enchantment', 'not_a_real_enchantment', fields=(f.Field('amount', 1),)))
    assert f.shared_height(unknown) == 0
    changed = _with_description(observation, unknown)
    owner = f.PreparedPublic.adopt(changed)
    for _ in range(2):
        with pytest.raises(ValueError, match='Unknown learned entity identity'):
            encoder.encode_prepared(changed, owner)
    assert id(unknown) not in encoder._description_rows


def test_an_altered_or_restored_encoder_does_not_use_rows_kept_before(monkeypatch):
    import pickle
    observation, owner, copy, copy_owner = next(iter(_fight(10)))
    encoder = FeatureEncoder(Vocabulary.fit([copy], split='train'), representation=COMBAT)
    expected = encoder.encode_prepared(copy, copy_owner)
    _same_features(encoder.encode_prepared(observation, owner), expected)
    assert encoder._description_rows
    restored = pickle.loads(pickle.dumps(encoder))
    assert not restored._description_rows
    _same_features(restored.encode_prepared(observation, owner), expected)
    # Other names give other rows: the kept ones are dropped, not reused.
    renamed = {name: index + 1 for name, index in encoder.names.items()}
    encoder.names = renamed
    after = encoder.encode_prepared(observation, owner)
    _same_features(after, encoder.encode_prepared(copy, copy_owner))
    assert not np.array_equal(after.fields, expected.fields)
    # A check patched onto the class is honoured for every node.
    seen = []
    monkeypatch.setattr(FeatureEncoder, 'validate_entity', lambda self, node: seen.append(node))
    _same_features(encoder.encode_prepared(observation, owner), after)
    assert len(seen) == sum(1 for root in (observation.run, observation.context) for _ in f.walk(root))


def _nested(leaf, depth):
    for level in range(depth):
        leaf = f.Node('group', f'level{level}', children=(leaf,))
    return leaf


@pytest.mark.parametrize('depth,accepted', [(23, True), (24, False)])
def test_a_description_is_checked_at_the_depth_where_it_stands(depth, accepted):
    observation = next(iter(_fight()))[0]
    child = f.Node('parameters', 'amounts', fields=(f.Field('0', 1),))
    shared = f.share_description(f.Node('mechanic', 'Deep', children=(child,)))
    plain = f.Node('mechanic', 'Deep', children=(child,))
    assert f.shared_height(shared) == 1 and f.shared_height(plain) is None
    for leaf in (shared, plain):
        # `depth` groups put the description at that depth below the context root.
        context = replace(observation.context, children=(*observation.context.children, _nested(leaf, depth - 1)))
        decision = replace(observation, context=context)
        assert f._exact_decision(decision) is accepted
        if accepted:
            f.validate(decision)
            assert f.PreparedPublic.adopt(decision).value is decision
        else:
            with pytest.raises(f.ContractError, match='Invalid public graph node'):
                f.validate(decision)
            with pytest.raises(f.ContractError):
                f.PreparedPublic.adopt(decision)


def test_a_result_kept_for_another_object_is_never_used(monkeypatch):
    observation, owner, copy, copy_owner = next(iter(_fight(5)))
    shared = _shared(observation)
    spec = next(n for n in shared if n.kind == 'spec')
    other = next(n for n in shared if n.kind == 'spec' and n != spec)
    encoder = FeatureEncoder(Vocabulary.fit([copy], split='train'), representation=COMBAT)
    expected_key, expected_mapping = public_key(copy), FullRunEncoder().mapping_prepared(copy, copy_owner)
    expected = encoder.encode_prepared(copy, copy_owner)
    _same_features(encoder.encode_prepared(observation, owner), expected)  # Fills this encoder's rows.
    # Every store now answers for `spec` with what belongs to `other`, as a stale
    # entry under a reused id would.
    wrong_rows = encoder._description_rows[id(other)]
    monkeypatch.setitem(encoder._description_rows, id(spec), wrong_rows)
    monkeypatch.setitem(public_keys._DESCRIPTION_KEYS, id(spec), (other, ('wrong',)))
    monkeypatch.setitem(full_records._DESCRIPTION_ROWS, id(spec), (other, (1, ('wrong',), 1, 0)))
    monkeypatch.setitem(combat_features._DESCRIPTION_VALUES, id(spec), (other, ((0, (9., 9., 9.)),)))
    monkeypatch.setitem(combat_features._SPEC_VALUES, id(spec), (other, {'spec.base_damage': 999}))
    assert public_key(observation) == expected_key
    assert FullRunEncoder().mapping_prepared(observation, owner) == expected_mapping
    _same_features(encoder.encode_prepared(observation, owner), expected)


def test_an_encoder_with_its_own_entity_check_reads_every_node():
    observation, owner, copy, copy_owner = next(iter(_fight(6)))
    vocabulary = Vocabulary.fit([copy], split='train')
    expected = FeatureEncoder(vocabulary, representation=COMBAT).encode_prepared(copy, copy_owner)
    count = sum(1 for root in (observation.run, observation.context) for _ in f.walk(root))

    class Checking(FeatureEncoder):
        def validate_entity(self, node):
            seen.append(node)

    hooked = FeatureEncoder(vocabulary, representation=COMBAT)
    hooked.validate_entity = lambda node: seen.append(node)
    for encoder in (Checking(vocabulary, representation=COMBAT), hooked):
        for _ in range(2):
            seen = []
            _same_features(encoder.encode_inference(observation), expected)
            assert len(seen) == count and not encoder._description_rows
