"""Compact inference retains the lossless path's public meaning and failures."""
from dataclasses import fields, make_dataclass, replace

import pytest

torch = pytest.importorskip('torch')
np = pytest.importorskip('numpy')
from game.agent.contracts import full as f
from game.agent.encoding.full import FullRunEncoder, FullRunProfile
from game.agent.encoding.schema import CapacityError, INTEGER_MAX
from game.agent.input_views import RAW, DETACHED_HISTORY
from game.agent.action_policy import COMMIT_DECISIONS
from game.agent.training.combat_features import REPRESENTATIONS
from game.agent.training.features import FeatureEncoder
from game.agent.training.model import ActorCritic, Architecture, collate
from .test_training_model import decision, renamed, cpu_threads, Vocabulary


def same_features(expected, actual):
    assert not hasattr(actual, 'graph')
    for field in fields(expected):
        left, right = getattr(expected, field.name), getattr(actual, field.name)
        if isinstance(left, np.ndarray):
            assert left.dtype == right.dtype and np.array_equal(left, right), field.name
            assert not right.flags.writeable
        else:
            assert left == right, field.name


@pytest.mark.parametrize('representation', REPRESENTATIONS)
@pytest.mark.parametrize('view', (RAW, DETACHED_HISTORY))
def test_inference_inputs_and_forward_outputs_match_lossless_path(representation, view):
    from .test_input_views import historical_decision
    public = historical_decision()
    vocabulary = Vocabulary.fit([public], split='train')
    encoder = FeatureEncoder(vocabulary, representation=representation,
                             action_policy=COMMIT_DECISIONS, input_view=view)
    model = ActorCritic(vocabulary, Architecture(16, 1, representation), seed=7,
                       action_policy=COMMIT_DECISIONS, input_view=view)
    for observation in (public, renamed(public)[0]):
        wire = f.to_dict(observation)
        expected = encoder.encode(observation).for_rollout()
        actual = encoder.encode_inference(observation)
        same_features(expected, actual)
        left, right = (collate([value], vocabulary=vocabulary) for value in (expected, actual))
        assert all(torch.equal(left[k], right[k]) for k in left)
        with torch.inference_mode():
            assert all(torch.equal(a, b) for a, b in zip(model(left), model(right)))
        assert f.to_dict(observation) == wire


def test_inference_omits_lossless_tables_but_still_revalidates(monkeypatch):
    public = decision()
    encoder = FeatureEncoder(Vocabulary.fit([public], split='train'))
    expected = encoder.encode(public).for_rollout()
    def forbidden(*args, **kwargs):
        pytest.fail('Compact inference constructed lossless tables')
    monkeypatch.setattr(FullRunEncoder, '_finish_pack', forbidden)
    same_features(expected, encoder.encode_inference(public))
    with pytest.raises(f.ContractError):
        encoder.encode_inference(replace(public, candidates=()))
    same_features(expected, encoder.encode_inference(public))


@pytest.mark.parametrize('dimension', ('nodes', 'references', 'strings', 'string_bytes',
                                      'candidates', 'integer_magnitude'))
def test_inference_enforces_lossless_capacity_contract(dimension):
    public = decision()
    encoder = FeatureEncoder(Vocabulary.fit([public], split='train'))
    if dimension == 'integer_magnitude':
        public = replace(public, run=replace(public.run, fields=(f.Field('hp', INTEGER_MAX + 1),)))
    else:
        encoder.public.profile = FullRunProfile(**{dimension: 1})
    errors = []
    for encode in (encoder.encode, encoder.encode_inference):
        with pytest.raises(CapacityError) as error:
            encode(public)
        errors.append((error.value.dimension, error.value.required, error.value.capacity))
    assert errors[0] == errors[1] and errors[0][0] == dimension


def test_structural_record_fallback_preserves_noncanonical_reference_order():
    public = decision()
    context = replace(public.context, links=(f.Link('order', ('card:1', 'card:0')),))
    keys = ('children', 'links', 'kind', 'definition_id', 'ref', 'fields')
    custom_type = make_dataclass('ReorderedNode', [(key, object) for key in keys],
        frozen=True, namespace={'get': f.Node.get, 'linked': f.Node.linked})
    public = replace(public, context=custom_type(**{key: getattr(context, key) for key in keys}))
    encoder = FeatureEncoder(Vocabulary.fit([public], split='train'))
    expected = encoder.encode(public).for_rollout()
    canonical = encoder.encode(f.PreparedPublic(public).value).for_rollout()
    assert expected.candidate_refs != canonical.candidate_refs
    same_features(expected, encoder.encode_inference(public))


def test_custom_encoder_hooks_and_prepared_ownership_remain_enforced(monkeypatch):
    public = decision()
    encoder = FeatureEncoder(Vocabulary.fit([public], split='train'))
    calls = []
    class CustomEncoder(FullRunEncoder):
        def pack(self, value):
            calls.append(value)
            return super().pack(value)
    encoder.public = CustomEncoder()
    expected = encoder.encode(public).for_rollout()
    same_features(expected, encoder.encode_inference(public))
    assert calls == [public, public]
    encoder.public = FullRunEncoder()
    pack = encoder.public.pack
    def instance_hook(value):
        calls.append(value)
        return pack(value)
    monkeypatch.setattr(encoder.public, 'pack', instance_hook)
    same_features(expected, encoder.encode_inference(public))
    assert calls == [public, public, public]
    owner = f.PreparedPublic(public)
    codec = FullRunEncoder()
    for value, token in ((public, owner), (replace(owner.value), owner), (owner.value, object())):
        with pytest.raises(f.ContractError):
            codec.mapping_prepared(value, token)
    mapping = codec.mapping_prepared(owner.value, owner)
    assert mapping.candidate_refs == expected.candidate_refs
    assert mapping.legal_mask == expected.legal_mask
    terminal = f.PreparedPublic(f.RunOutcome('sts_run_outcome_v1', 'defeat', 'none'))
    with pytest.raises(f.ContractError, match='Terminal'):
        codec.mapping_prepared(terminal.value, terminal)


@pytest.mark.parametrize('hook', ('encode', '_features'))
def test_instance_feature_hooks_keep_original_calling_convention(hook, monkeypatch):
    public = decision()
    encoder = FeatureEncoder(Vocabulary.fit([public], split='train'))
    expected = encoder.encode(public).for_rollout()
    calls, original = [], getattr(encoder, hook)
    if hook == 'encode':
        def custom(value):
            calls.append(value)
            return original(value)
    else:
        def custom(value, graph):
            calls.append(value)
            return original(value, graph)
    monkeypatch.setattr(encoder, hook, custom)
    same_features(expected, encoder.encode_inference(public))
    assert calls == [public]
