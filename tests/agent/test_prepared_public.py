"""Owned public observations retain validation, isolation and exact wire data."""
from dataclasses import FrozenInstanceError, dataclass, replace

import pytest

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.recording import Metadata, TrajectoryError, TrajectoryWriter, load_trajectory


def decision(hp=50):
    return f.PublicDecision(f.SCHEMA, f.PROFILE,
        f.Node('run', 'run', fields=(f.Field('hp', hp), f.Field('max_hp', 80))),
        f.Node('combat', 'combat', children=(f.Node('enemy', 'jaw_worm', 'enemy:0'),)),
        (f.Candidate('action:0', 'end_turn'),))


def test_preparation_owns_canonical_values_and_independent_wire_copies():
    @dataclass
    class InputField:
        value: int
        key: str
    field = InputField(50, 'hp')
    # The existing wire codec accepts structurally matching dataclasses. The
    # parsed result must never retain a caller's mutable record instance.
    source = replace(decision(), run=f.Node('run', 'run', fields=(field,),
                     links=(f.Link('target', ('enemy:0',)),)))
    expected = f.to_dict(source)
    prepared = f.PreparedPublic(source)
    public = prepared.value
    assert public == f.from_dict(expected) and public is not source
    assert type(public.run.fields) is type(public.run.links) is type(public.candidates) is tuple
    assert type(public.run.links[0].targets) is tuple
    field.value = 999
    wire = prepared.wire_for(public)
    assert wire == expected
    assert list(wire['run']['fields'][0]) == ['key', 'value']
    wire['run']['fields'][0]['value'] = False
    wire['run']['links'][0]['targets'].clear()
    wire['candidates'].clear()
    assert prepared.wire_for(public) == expected == f.to_dict(public)
    for other in (source, replace(public), decision(hp=40)):
        with pytest.raises(c.ContractError, match='belong'):
            prepared.wire_for(other)
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        prepared.value = decision()


@pytest.mark.parametrize('bad', [
    replace(decision(), candidates=list(decision().candidates)),
    replace(decision(), run=f.Node('run', 'run', fields=[f.Field('hp', 50)])),
    replace(decision(), run=f.Node('run', 'run', links=(f.Link('target', ['enemy:0']),))),
    replace(decision(), profile='full_run_v99'),
    replace(decision(), candidates=()),
    replace(decision(), candidates=decision().candidates * 2),
    replace(decision(), run=f.Node('run', 'run', fields=(f.Field('hp', 1.5),))),
    replace(decision(), run=f.Node('run', 'run', fields=(f.Link('hp', ()),))),
    replace(decision(), run=f.Node('run', 'run', links=(f.Link('target', ('enemy:99',)),))),
    replace(decision(), run=f.Node('run', 'run', fields=(f.Field('leak', 'card:99'),))),
])
def test_preparation_rejects_malformed_public_values(bad):
    with pytest.raises(c.ContractError):
        f.PreparedPublic(bad)


def test_prepared_outcomes_are_validated_and_detached():
    value = c.RunOutcome('sts_run_outcome_v1', 'defeat', 'none')
    prepared = f.PreparedPublic(value)
    assert prepared.value == value
    wire = prepared.wire_for(prepared.value)
    wire['kind'] = 'victory'
    assert prepared.wire_for(prepared.value) == f.to_dict(value)
    with pytest.raises(c.ContractError):
        f.PreparedPublic(replace(value, kind='invalid'))


def test_prepared_encoding_matches_and_preserves_custom_hooks():
    np = pytest.importorskip('numpy')
    from game.agent.encoding.full import FullRunEncoder, FullRunProfile
    from game.agent.encoding import CapacityError
    @dataclass
    class ReorderedField:
        value: int
        key: str
    source = replace(decision(), run=f.Node('run', 'run', fields=(ReorderedField(50, 'hp'),)))
    prepared = f.PreparedPublic(source)
    public = prepared.value
    encoder = FullRunEncoder()
    expected = encoder.encode(public)
    actual = encoder.encode_prepared(public, prepared)
    for key in expected.observation:
        assert np.array_equal(actual.observation[key], expected.observation[key])
    assert actual.candidate_refs == expected.candidate_refs
    assert actual.reference_refs == expected.reference_refs
    for other in (replace(public), decision(hp=40)):
        with pytest.raises(c.ContractError, match='belong'):
            encoder.encode_prepared(other, prepared)
    with pytest.raises(CapacityError):
        FullRunEncoder(FullRunProfile(nodes=1)).encode_prepared(public, prepared)

    calls = []
    class CustomEncoder(FullRunEncoder):
        def encode(self, value):
            calls.append(('encode', value))
            return super().encode(value)

        def _ready_wire(self, value):
            calls.append(('wire', value))
            return super()._ready_wire(value)

    CustomEncoder().encode_prepared(public, prepared)
    assert calls == [('encode', public), ('wire', public)]


def rich_decision():
    from game.agent.encoding.schema import INTEGER_MAX
    children = tuple(f.Node('card', 'shared', f'card:{i}') for i in range(3))
    branch = f.Node('leaf', 'leaf', fields=(
        f.Field('null', None), f.Field('false', False), f.Field('true', True),
        f.Field('zero', 0), f.Field('negative', -INTEGER_MAX),
        f.Field('positive', INTEGER_MAX), f.Field('text', '火🔥'), f.Field('empty', '')),
        links=(f.Link('empty', ()), f.Link('ordered', ('card:2', 'card:0', 'card:2')),
               f.Link('history_subject', ('enemy:91',))))
    for _ in range(24):
        branch = f.Node('branch', 'branch', children=(branch,))
    return replace(decision(), run=f.Node('run', 'run', children=children), context=branch,
                   candidates=(f.Candidate('action:8', 'play_card', 'card:2'),
                               f.Candidate('action:1', 'end_turn'),
                               f.Candidate('action:3', 'play_card', 'card:0')))


def test_direct_preparation_matches_wire_validation_without_serialization(monkeypatch):
    source = rich_decision()
    expected = f.from_dict(f.to_dict(source))
    def forbidden(*args):
        pytest.fail('Preparing public records performed a wire round trip')
    with monkeypatch.context() as patch:
        patch.setattr(f, '_wire', forbidden)
        patch.setattr(f, 'from_dict', forbidden)
        owner = f.PreparedPublic(source)
    assert owner.value == expected and owner.value is not source
    assert all(a is not b for a, b in zip(f.walk(source.run), f.walk(owner.value.run)))
    assert all(a is not b for a, b in zip(f.walk(source.context), f.walk(owner.value.context)))
    assert owner.wire_for(owner.value) == f.to_dict(expected)


@pytest.mark.parametrize('value', [1.0, float('nan'), {}, [], object(), f.Field])
def test_direct_record_and_wire_paths_reject_the_same_invalid_scalar_types(value):
    source = replace(decision(), run=f.Node('run', 'run', fields=(f.Field('hp', value),)))
    for prepare in (f.PreparedPublic, f.to_dict):
        with pytest.raises(c.ContractError):
            prepare(source)


def test_prepared_packing_needs_no_wire_copy_and_owns_its_arrays(monkeypatch):
    np = pytest.importorskip('numpy')
    from game.agent.encoding.full import FullRunEncoder
    owner = f.PreparedPublic(rich_decision())
    public, encoder = owner.value, FullRunEncoder()
    expected = encoder.pack(public)
    expected_wire = owner.wire_for(public)

    def forbidden(*args):
        pytest.fail('Prepared encoding copied the wire or revalidated its owner')
    with monkeypatch.context() as patch:
        patch.setattr(f.PreparedPublic, 'wire_for', forbidden)
        patch.setattr(f, 'to_dict', forbidden)
        patch.setattr(f, 'from_dict', forbidden)
        actual = encoder._pack_prepared(public, owner)
        again = encoder._pack_prepared(public, owner)
        with pytest.raises(c.ContractError, match='belong'):
            encoder._pack_prepared(replace(public), owner)
    assert actual.candidate_refs == expected.candidate_refs
    assert actual.reference_refs == expected.reference_refs
    for key, value in expected.observation.items():
        assert np.array_equal(value, actual.observation[key])
        assert not np.shares_memory(actual.observation[key], again.observation[key])
        actual.observation[key].fill(0)
        assert np.array_equal(value, again.observation[key])
    assert f.to_dict(public) == owner.wire_for(public) == expected_wire


@pytest.mark.parametrize('dimension', (
    'nodes', 'references', 'strings', 'string_bytes', 'candidates', 'integer_magnitude'))
def test_prepared_packing_preserves_exact_capacity_failures(dimension):
    pytest.importorskip('numpy')
    from game.agent.encoding.full import FullRunEncoder, FullRunProfile
    from game.agent.encoding.schema import CapacityError, INTEGER_MAX
    source = rich_decision()
    profile = FullRunProfile()
    if dimension == 'integer_magnitude':
        source = replace(source, run=replace(source.run,
                         fields=(f.Field('overflow', INTEGER_MAX + 1),)))
    else:
        profile = replace(profile, **{dimension: 1})
    owner, encoder = f.PreparedPublic(source), FullRunEncoder(profile)
    errors = []
    for encode in (lambda: encoder.pack(owner.value),
                   lambda: encoder._pack_prepared(owner.value, owner)):
        with pytest.raises(CapacityError) as error:
            encode()
        errors.append((error.value.dimension, error.value.required, error.value.capacity))
    assert errors[0] == errors[1]
    assert errors[0][0] == dimension


def test_prepared_terminal_packing_matches_without_a_wire_copy(monkeypatch):
    np = pytest.importorskip('numpy')
    from game.agent.encoding.full import FullRunEncoder
    encoder = FullRunEncoder()
    owner = f.PreparedPublic(c.RunOutcome('sts_run_outcome_v1', 'truncated', 'act_complete'))
    expected = encoder.pack(owner.value)
    def forbidden(*args):
        pytest.fail('Terminal packing copied the wire')
    monkeypatch.setattr(f.PreparedPublic, 'wire_for', forbidden)
    actual = encoder._pack_prepared(owner.value, owner)
    assert actual.candidate_refs == actual.reference_refs == ()
    assert all(np.array_equal(value, actual.observation[key])
               for key, value in expected.observation.items())


def test_specialized_packing_matches_reference_looking_metadata_and_repeated_links():
    np = pytest.importorskip('numpy')
    from game.agent.encoding.full import FullRunEncoder
    # Metadata strings can resemble references too; the lossless encoder must
    # retain its existing reference-table ordering, even before a definition.
    source = replace(decision(), context=f.Node('card:77', 'enemy:9', children=(
        f.Node('card', 'strike', 'card:3', fields=(f.Field('potion:8', '火🔥'),),
               links=(f.Link('card:22', ('enemy:9', 'enemy:9')),)),
        f.Node('enemy', 'jaw_worm', 'enemy:9'))),
        candidates=(f.Candidate('action:8', 'play_card', 'card:3', 'enemy:9'),
                    f.Candidate('action:1', 'end_turn')))
    owner, encoder = f.PreparedPublic(source), FullRunEncoder()
    expected = encoder.pack(owner.value)
    actual = encoder._pack_prepared(owner.value, owner)
    assert actual.candidate_refs == expected.candidate_refs
    assert actual.reference_refs == expected.reference_refs
    assert all(np.array_equal(value, actual.observation[key])
               for key, value in expected.observation.items())


def test_specialized_packing_preserves_competing_capacity_failures():
    pytest.importorskip('numpy')
    from game.agent.encoding.full import FullRunEncoder, FullRunProfile
    from game.agent.encoding.schema import CapacityError
    owner = f.PreparedPublic(rich_decision())
    for nodes in range(1, 85):
        for strings, references in ((1, 1), (6, 2), (12, 8)):
            encoder = FullRunEncoder(FullRunProfile(nodes=nodes, strings=strings,
                                                   references=references, string_bytes=6))
            errors = []
            for call in (lambda: encoder.pack(owner.value),
                         lambda: encoder._pack_prepared(owner.value, owner)):
                with pytest.raises(CapacityError) as error:
                    call()
                errors.append((error.value.dimension, error.value.required, error.value.capacity))
            assert errors[0] == errors[1]


@pytest.mark.parametrize('failure', ('identity', 'owner_type', 'capacity', 'padding', 'terminal'))
def test_rollout_prepared_owner_is_released_after_every_failed_or_terminal_encode(failure, monkeypatch):
    pytest.importorskip('torch')
    from game.agent.encoding import CapacityError
    from game.agent.encoding.full import FullRunProfile
    from game.agent.training.features import FeatureEncoder, Vocabulary, _RolloutEncoder
    owner = f.PreparedPublic(decision())
    public = owner.value
    encoder = _RolloutEncoder(FeatureEncoder(Vocabulary.fit([public], split='train')))
    encoder.encode_prepared(public, owner)
    assert encoder.prepared_for(public) is owner
    assert encoder.prepared_for(replace(public)) is None
    if failure == 'terminal':
        encoder.encode(c.RunOutcome('sts_run_outcome_v1', 'defeat', 'none'))
    else:
        value, token, error = public, owner, c.ContractError
        if failure == 'identity':
            value = replace(public)
        elif failure == 'owner_type':
            token = object()
        elif failure == 'capacity':
            encoder.profile = FullRunProfile(nodes=1)
            error = CapacityError
        else:
            def fail():
                raise RuntimeError('padding failed')
            monkeypatch.setattr(encoder, 'empty', fail)
            error = RuntimeError
        with pytest.raises(error):
            encoder.encode_prepared(value, token)
    assert encoder._prepared is encoder._decision is encoder._graph is None
    assert encoder.prepared_for(public) is None


def test_prepared_consumers_do_not_repeat_public_parsing_but_loader_does(tmp_path, monkeypatch):
    pytest.importorskip('numpy')
    from game.agent.encoding.full import FullRunEncoder
    owner = f.PreparedPublic(decision())
    public = owner.value
    calls, parse = [], f.from_dict
    def counted(wire):
        if wire.get('schema') == f.SCHEMA:
            calls.append(wire)
        return parse(wire)
    monkeypatch.setattr(f, 'from_dict', counted)
    FullRunEncoder().encode_prepared(public, owner)
    metadata = Metadata('a'*32, 'test', 'b'*64, 'c'*64, 'test', 'test', 'train', 'controlled_fixture')
    execution = c.ExecutionReport('sts_execution_report_v1', 'reconciled', 'applied', 'none')
    path = tmp_path/'prepared.trajectory.jsonl'
    with TrajectoryWriter(path, metadata, public, prepared=owner) as writer:
        writer.append(public.candidates[0], execution, public, prepared=owner)
        writer.finish(c.RunOutcome('sts_run_outcome_v1', 'truncated', 'decision_budget'))
    assert not calls
    assert load_trajectory(path).initial == public
    assert len(calls) == 2


@pytest.mark.parametrize('boundary', ('terminal', 'cutoff'))
def test_prepared_and_ordinary_writers_have_identical_bytes(tmp_path, boundary):
    first, second = f.PreparedPublic(decision()), f.PreparedPublic(decision(hp=40))
    outcome = c.RunOutcome('sts_run_outcome_v1', 'victory', 'none') if boundary == 'terminal' else c.RunOutcome('sts_run_outcome_v1', 'truncated', 'decision_budget')
    if boundary == 'terminal':
        second = f.PreparedPublic(outcome)
    metadata = Metadata('a'*32, 'test', 'b'*64, 'c'*64, 'test', 'test', 'train', 'controlled_fixture')
    execution = c.ExecutionReport('sts_execution_report_v1', 'reconciled', 'applied', 'none')
    paths = []
    for use_prepared in (False, True):
        path = tmp_path/f'{use_prepared}.trajectory.jsonl'
        with TrajectoryWriter(path, metadata, first.value,
                              prepared=first if use_prepared else None) as writer:
            writer.append(first.value.candidates[0], execution, second.value,
                          prepared=second if use_prepared else None)
            writer.finish(outcome)
        paths.append(path)
    assert paths[0].read_bytes() == paths[1].read_bytes()
    loaded = load_trajectory(paths[1], split='train')
    assert loaded.initial == first.value and loaded.transitions[0].successor == second.value
    assert loaded.transitions[0].reward == int(boundary == 'terminal')


@pytest.mark.parametrize('bad', ('identity', 'action', 'execution', 'sequence'))
def test_prepared_writer_rejects_invalid_transitions_before_writing(tmp_path, bad):
    first, second = f.PreparedPublic(decision()), f.PreparedPublic(decision(hp=40))
    metadata = Metadata('a'*32, 'test', 'b'*64, 'c'*64, 'test', 'test', 'train', 'controlled_fixture')
    execution = c.ExecutionReport('sts_execution_report_v1', 'reconciled', 'applied', 'none')
    with TrajectoryWriter(tmp_path/'bad.trajectory.jsonl', metadata, first.value, prepared=first) as writer:
        before = writer.partial.read_bytes()
        action, successor = first.value.candidates[0], second.value
        if bad == 'identity':
            successor = replace(successor)
        elif bad == 'action':
            action = replace(action, kind='play_card')
        elif bad == 'execution':
            execution = replace(execution, status='uncertain', mutation='unknown')
        else:
            writer.count = True
        with pytest.raises((TrajectoryError, c.ContractError)):
            writer.append(action, execution, successor, prepared=second)
        assert writer.partial.read_bytes() == before
        assert writer.current is first.value


def test_adapter_owner_is_bound_to_current_frame_and_keeps_stale_guard():
    from game.agent.headless import HeadlessAdapter
    from game.headless.run.engine import RunEngine
    run = RunEngine.ironclad_slice(seed=2)
    adapter = HeadlessAdapter(run, decision_profile='full_run_v2')
    frame = adapter.observe()
    owner = adapter.prepared_for(frame.decision)
    assert owner.value is frame.decision
    assert owner.wire_for(frame.decision) == f.to_dict(frame.decision)
    assert adapter.prepared_for(replace(frame.decision)) is None
    run.state.hp -= 1
    assert adapter.step(frame.binding, frame.decision.candidates[0].ref).reason == 'stale_decision'
    following = adapter.observe()
    assert adapter.prepared_for(frame.decision) is None
    assert adapter.prepared_for(following.decision).value is following.decision
    adapter.reset(run)
    assert adapter.prepared_for(following.decision) is None
