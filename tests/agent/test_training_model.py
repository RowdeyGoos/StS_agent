"""Learnable public features, masked candidates and a deliberately tiny overfit."""
from dataclasses import replace

import pytest

torch = pytest.importorskip('torch')
np = pytest.importorskip('numpy')
from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.encoding.full import FullRunEncoder, FullRunProfile
from game.agent.encoding.schema import CapacityError
from game.agent.full_policy import choose_action
from game.agent.training.features import Vocabulary, FeatureEncoder
from game.agent.training.learner import Corpus, Example, LearnerConfig, ImitationLearner, evaluate_imitation
from game.agent.training.model import ActorCritic, Architecture, collate, log_probabilities, policy_statistics, sample_actions
from game.agent.training.rewards import RewardSpec


@pytest.fixture(autouse=True)
def cpu_threads():
    before = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(before)


def decision(hp=70, left=6, right=3):
    def node(kind, ref, damage):
        return f.Node('card', kind, ref, children=(f.Node('spec', 'spec', fields=(f.Field('base_damage', damage),)),))
    run = f.Node('run', 'run', fields=(f.Field('hp', hp), f.Field('max_hp', 80)),
                 children=(f.Node('potion', 'blood_potion', 'potion:0'),))
    context = f.Node('combat', 'combat', fields=(f.Field('round', 1),), children=(
        f.Node('hand', 'hand', children=(node('strike', 'card:0', left), node('strike', 'card:1', right))),
        f.Node('enemy', 'nibbit', 'enemy:0', fields=(f.Field('hp', 20),))))
    actions = (f.Candidate('action:0', 'play_card', 'card:0', 'enemy:0'),
               f.Candidate('action:1', 'play_card', 'card:1', 'enemy:0'),
               f.Candidate('action:2', 'use_potion', 'potion:0'), f.Candidate('action:3', 'end_turn'))
    return f.PublicDecision(f.SCHEMA, f.PROFILE, run, context, actions)


def tiny_corpus():
    decisions = (decision(30, 6, 3), decision(70, 3, 8), decision(70, 8, 3), decision(30, 8, 3))
    vocab = Vocabulary.fit(decisions, split='train')
    encoder = FeatureEncoder(vocab)
    examples = []
    for public in decisions:
        features = encoder.encode(public)
        examples.append(Example(features, features.graph.candidate_refs.index(choose_action(public).ref), None))
    return Corpus(tuple(examples), vocab, RewardSpec(), 'controlled-tiny-corpus', 'train', 4, 0)


def test_frozen_vocabulary_identity_survives_wire_and_worker_round_trips():
    from dataclasses import FrozenInstanceError
    import hashlib
    import json
    import pickle
    from game.agent.training.features import SCHEMA

    vocabulary = Vocabulary(('hp', 'énergie'))
    wire = vocabulary.to_dict()
    expected = SCHEMA + ':' + hashlib.sha256(json.dumps(wire, sort_keys=True,
        separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    for copy in (vocabulary, Vocabulary.from_dict(wire), pickle.loads(pickle.dumps(vocabulary))):
        assert copy.identity == expected and copy.to_dict() == wire
        assert copy == vocabulary
    changed = replace(vocabulary, names=('block', *vocabulary.names))
    assert changed.identity != expected and vocabulary.identity == expected
    wire['names'].append('external mutation')
    assert vocabulary.identity == expected and vocabulary.names == ('hp', 'énergie')
    with pytest.raises(FrozenInstanceError):
        vocabulary.names = ()


def renamed(public):
    mapping = {'card:0':'card:91', 'card:1':'card:7', 'enemy:0':'enemy:142', 'potion:0':'potion:38',
               'action:0':'action:99', 'action:1':'action:4', 'action:2':'action:217', 'action:3':'action:83'}
    def visit(value):
        if type(value) is str:
            return mapping.get(value, value)
        if type(value) is list:
            return [visit(v) for v in value]
        if type(value) is dict:
            return {k:visit(v) for k,v in value.items()}
        return value
    wire = visit(f.to_dict(public))
    wire['candidates'].reverse()
    return f.from_dict(wire), mapping


def test_fixed_and_packed_tables_match_without_padded_allocation(monkeypatch):
    public, encoder = decision(), FullRunEncoder()
    fixed = encoder.encode(public)
    def forbidden():
        pytest.fail('Packed encoding allocated a padded observation')
    monkeypatch.setattr(encoder, 'empty', forbidden)
    packed = encoder.pack(public)
    for key, value in packed.observation.items():
        assert np.array_equal(fixed.observation[key][:len(value)], value)
        assert not fixed.observation[key][len(value):].any()
    assert packed.candidate_refs == fixed.candidate_refs
    assert sum(v.nbytes for v in packed.observation.values()) < 100000
    terminal = encoder.pack(c.RunOutcome('sts_run_outcome_v1', 'defeat', 'none'))
    assert not len(terminal.candidate_refs) and terminal.observation['nodes'].shape == (0, 5)
    with pytest.raises(CapacityError):
        FullRunEncoder(FullRunProfile(candidates=2)).pack(public)


def test_rollout_reuses_only_its_exact_prepared_graph(monkeypatch):
    from game.agent.training.features import _RolloutEncoder
    public, next_public = decision(), decision(hp=42)
    features = FeatureEncoder(Vocabulary.fit([public], split='train'))
    expected = features.encode(public)
    fixed_expected = features.public.encode(public)
    prepared = _RolloutEncoder(features)
    calls, pack = [], prepared.pack
    def counted(value):
        calls.append(value)
        return pack(value)
    monkeypatch.setattr(prepared, 'pack', counted)
    fixed = prepared.encode(public)
    actual = prepared.features_for(public)
    assert calls == [public]
    for key, value in fixed.observation.items():
        assert np.array_equal(value, fixed_expected.observation[key])
        assert not np.shares_memory(value, actual.graph.observation[key])
    for key, value in actual.graph.observation.items():
        assert np.array_equal(value, expected.graph.observation[key])
    for key in ('nodes', 'parents', 'positions', 'fields', 'numbers', 'links', 'link_positions', 'candidates'):
        assert np.array_equal(getattr(actual, key), getattr(expected, key))
    assert actual.graph.candidate_refs == expected.graph.candidate_refs
    assert actual.graph.reference_refs == expected.graph.reference_refs
    assert actual.roots == expected.roots and actual.vocabulary == expected.vocabulary
    fixed.observation['candidates'][:] = -1
    assert np.array_equal(actual.graph.observation['candidates'], expected.graph.observation['candidates'])
    with pytest.raises(c.ContractError, match='belong'):
        prepared.features_for(replace(public))
    prepared.encode(next_public)
    with pytest.raises(c.ContractError, match='belong'):
        prepared.features_for(public)
    assert np.array_equal(actual.graph.observation['nodes'], expected.graph.observation['nodes'])
    prepared.clear()
    with pytest.raises(c.ContractError, match='belong'):
        prepared.features_for(next_public)


@pytest.mark.parametrize('failure', ('invalid', 'capacity', 'padding', 'terminal'))
def test_rollout_prepared_graph_is_cleared_on_every_encoding_attempt(failure, monkeypatch):
    from game.agent.training.features import _RolloutEncoder
    public = decision()
    prepared = _RolloutEncoder(FeatureEncoder(Vocabulary.fit([public], split='train')))
    prepared.encode(public)
    if failure == 'terminal':
        prepared.encode(c.RunOutcome('sts_run_outcome_v1', 'defeat', 'none'))
    else:
        value, error = public, c.ContractError
        if failure == 'invalid':
            value = replace(public, candidates=())
        elif failure == 'capacity':
            prepared.profile = FullRunProfile(candidates=2)
            error = CapacityError
        else:
            def fail():
                raise RuntimeError('padding failed')
            monkeypatch.setattr(prepared, 'empty', fail)
            error = RuntimeError
        with pytest.raises(error):
            prepared.encode(value)
    with pytest.raises(c.ContractError, match='belong'):
        prepared.features_for(public)


@pytest.mark.parametrize('kind', ('primitive', 'record_shape', 'profile', 'empty_actions',
                                  'duplicate_action', 'unresolved_link', 'reference_text'))
def test_full_encoding_revalidates_every_input_after_warming(kind):
    public = decision()
    features = FeatureEncoder(Vocabulary.fit([public], split='train'))
    fixed = FullRunEncoder()
    for encode in (fixed.pack, fixed.encode, features.encode):
        encode(public)
        if kind == 'primitive':
            bad = replace(public, run=replace(public.run, fields=(f.Field('hp', 1.5),)))
        elif kind == 'record_shape':
            bad = replace(public, run=replace(public.run, fields=(f.Link('hp', ()),)))
        elif kind == 'profile':
            bad = replace(public, profile='full_run_v99')
        elif kind == 'empty_actions':
            bad = replace(public, candidates=())
        elif kind == 'duplicate_action':
            bad = replace(public, candidates=(*public.candidates, public.candidates[0]))
        elif kind == 'unresolved_link':
            bad = replace(public, run=replace(public.run, links=(f.Link('owner', ('enemy:999',)),)))
        else:
            bad = replace(public, run=replace(public.run, fields=(f.Field('hidden', 'card:999'),)))
        with pytest.raises(c.ContractError):
            encode(bad)
        encode(public)
    with pytest.raises(c.ContractError):
        features.encode(c.RunOutcome('sts_run_outcome_v1', 'defeat', 'none'))


def test_reference_and_candidate_permutations_preserve_corresponding_probabilities():
    public = decision()
    other, mapping = renamed(public)
    vocab = Vocabulary.fit([public], split='train')
    features = FeatureEncoder(vocab)
    a, b = features.encode(public), features.encode(other)
    model = ActorCritic(vocab, seed=12)
    for field in ('nodes', 'parents', 'positions', 'fields', 'numbers', 'links', 'link_positions', 'candidates'):
        assert np.array_equal(getattr(a, field), getattr(b, field))
    with torch.inference_mode():
        batch = collate([a, b], vocabulary=vocab)
        logits, values = model(batch)
        p = log_probabilities(logits, batch['mask']).exp()
    assert torch.equal(p[0], p[1]) and values[0] == values[1]
    original = dict(zip(a.graph.candidate_refs, p[0].tolist()))
    changed = dict(zip(b.graph.candidate_refs, p[1].tolist()))
    assert all(original[k] == changed[v] for k,v in mapping.items() if k.startswith('action:'))
    # Equal content is still two physical cards with distinct legal dispatches.
    assert a.candidates[0, 1] != a.candidates[1, 1]
    assert len(a.graph.candidate_refs) == 4


def test_typed_availability_links_child_order_and_unknown_names_are_preserved():
    base = decision()
    vocab = Vocabulary.fit([base], split='train')
    encoder = FeatureEncoder(vocab)
    variants = [replace(base, context=replace(base.context,
        fields=base.context.fields+(f.Field('new_field', value),))) for value in (None, False, 0, 'unseen_name')]
    encoded = [encoder.encode(p) for p in variants]
    rows = [e.fields[np.where(e.fields[:, 1] == 0)[0][0]].tolist() for e in encoded]
    assert [r[2] for r in rows] == [0, 1, 2, 3]
    assert rows[-1][-1] == 0 and encoder.vocabulary == vocab
    with pytest.raises(ValueError, match='training'):
        Vocabulary.fit([base], split='validation')
    linked = replace(base, context=replace(base.context, links=(f.Link('selected', ('card:1', 'card:0')),)))
    graph = encoder.encode(linked)
    assert graph.links[0, 2] != graph.links[1, 2]
    assert not np.array_equal(graph.link_positions[0], graph.link_positions[1])
    empty = encoder.encode(replace(base, context=replace(base.context, links=(f.Link('selected', ()),))))
    assert len(empty.links) == 1 and empty.links[0, 2] == -1 and empty.link_positions[0, 2] == 0
    assert len(encoder.encode(base).links) == 0
    moved = replace(base, context=replace(base.context, children=tuple(reversed(base.context.children))))
    assert not np.array_equal(encoder.encode(base).nodes, encoder.encode(moved).nodes)


def test_model_initialization_does_not_touch_global_rng_and_fixed_batch_backpropagates():
    public = decision()
    vocabulary = Vocabulary.fit([public], split='train')
    before = torch.get_rng_state().clone()
    model = ActorCritic(vocabulary, seed=55)
    assert torch.equal(before, torch.get_rng_state())
    encoder = FeatureEncoder(vocabulary)
    fixed = encoder.public.encode(public)
    batch = collate([encoder.from_fixed(fixed.observation)], vocabulary=vocabulary)
    logits, value = model(batch)
    logp, entropy = policy_statistics(logits, batch['mask'], torch.tensor([0]))
    loss = -logp.mean() + value.square().mean() - 0.01*entropy.mean()
    loss.backward()
    assert torch.isfinite(loss)
    assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
    with pytest.raises(c.ContractError):
        encoder.encode(c.RunOutcome('sts_run_outcome_v1', 'victory', 'none'))


def test_one_legal_mask_governs_sampling_log_probability_entropy_and_greedy():
    logits = torch.tensor([[1., 1000., 3.], [99., 2., 88.]], requires_grad=True)
    mask = torch.tensor([[True, False, True], [False, True, False]])
    generator = torch.Generator().manual_seed(4)
    for _ in range(30):
        actions = sample_actions(logits, mask, generator=generator)
        assert mask.gather(1, actions[:, None]).all()
    logs, entropy = policy_statistics(logits, mask, torch.tensor([2, 1]))
    assert logs[0].item() == pytest.approx(torch.log_softmax(torch.tensor([1., 3.]), 0)[1].item())
    assert logs[1] == entropy[1] == 0
    (-logs.mean()+entropy.mean()).backward()
    assert torch.isfinite(logits.grad).all() and not logits.grad[~mask].any()
    for bad_mask in (torch.zeros_like(mask), mask.to(torch.int64)):
        with pytest.raises(ValueError):
            log_probabilities(logits, bad_mask)
    with pytest.raises(ValueError):
        policy_statistics(logits, mask, torch.tensor([1, 1]))


def test_tiny_distinguishable_public_choices_can_be_overfit():
    corpus = tiny_corpus()
    learner = ImitationLearner(ActorCritic(corpus.vocabulary, Architecture(32, 2), seed=2), corpus,
                               LearnerConfig(batch_size=4, learning_rate=.01, value_weight=0), seed=4)
    before = evaluate_imitation(learner.model, corpus)
    for _ in range(160):
        learner.step()
    after = evaluate_imitation(learner.model, corpus)
    assert after['accuracy'] == 1 and after['imitation_loss'] < .03
    assert after['imitation_loss'] < before['imitation_loss']/10
