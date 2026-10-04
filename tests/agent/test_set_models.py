"""Non-graph candidate identities, batch isolation, gradients and native resumes."""
from dataclasses import replace

import pytest

torch = pytest.importorskip('torch')
np = pytest.importorskip('numpy')
pytest.importorskip('gymnasium')

from game.agent.training.combat_features import COMBAT, SET_MLP, SET_ATTENTION
from game.agent.training.features import FeatureEncoder, Vocabulary
from game.agent.training.model import ActorCritic, Architecture, collate, log_probabilities
from game.agent.training.checkpoint import load_policy, save_ppo_checkpoint, restore_ppo
from .test_training_model import cpu_threads, decision, renamed
from .test_ppo import owner, controlled_env, comparable


@pytest.mark.parametrize('schema', (SET_MLP, SET_ATTENTION))
def test_sets_ignore_edges_preserve_candidate_identity_and_do_not_mix_batch_rows(schema):
    public = decision()
    vocab = Vocabulary.fit([public], split='train')
    encoder = FeatureEncoder(vocab, representation=schema)
    assert encoder.identity == FeatureEncoder(vocab, representation=COMBAT).identity
    before = torch.get_rng_state().clone()
    model = ActorCritic(vocab, Architecture(16, 2, schema), seed=17)
    assert torch.equal(before, torch.get_rng_state())
    assert not hasattr(model, 'messages') and not hasattr(model, 'namespace')
    state = encoder.encode(public)
    batch = collate([state], vocabulary=vocab)
    model.eval()
    expected = model(batch)
    # Connectivity is deliberately invalid here: set processing cannot use it.
    mutated = {**batch, 'parents': torch.full_like(batch['parents'], 10**6),
               'links': torch.full_like(batch['links'], 10**6),
               'link_positions': torch.full_like(batch['link_positions'], 1000)}
    assert all(torch.equal(a, b) for a, b in zip(expected, model(mutated)))
    model.train()
    assert all(torch.equal(a, b) for a, b in zip(expected, model(batch)))
    changed, mapping = renamed(public)
    changed = replace(changed, candidates=changed.candidates[:-1])
    alternate = encoder.encode(changed)
    other = encoder.encode(decision(hp=1, left=1000, right=2000))
    combined = collate([alternate, state, other], vocabulary=vocab)
    logits, values = model(combined)
    assert torch.allclose(logits[1], expected[0][0], atol=2e-6, rtol=1e-6)
    assert float(values[1].detach()) == pytest.approx(float(expected[1][0].detach()), abs=2e-6)
    renamed_state = encoder.encode(renamed(public)[0])
    renamed_logits, _ = model(collate([renamed_state], vocabulary=vocab))
    by_ref = dict(zip(renamed_state.graph.candidate_refs, renamed_logits[0].tolist()))
    assert all(by_ref[mapping[ref]] == pytest.approx(float(value.detach()), abs=1e-6)
               for ref, value in zip(state.graph.candidate_refs, expected[0][0]))
    (logits.square().mean() + values.square().mean()).backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
    assert all(sum(float(p.grad.abs().sum()) for p in layer.parameters()) > 0 for layer in model.entities)


@pytest.mark.parametrize('schema', (SET_MLP, SET_ATTENTION))
def test_sets_parallel_ppo_checkpoint_exact_resume(tmp_path, schema):
    with owner(seed=17, workers=2, architecture=Architecture(16, 1, schema)) as left:
        left.update(left.collect())
        bundle, state = tmp_path / 'public/model.sts-model', tmp_path / 'private/model.resume.pt'
        save_ppo_checkpoint(bundle, left, resume_path=state)
        policy = load_policy(bundle)
        assert policy.model.architecture.schema == schema
        with restore_ppo(bundle, state, env_factory=controlled_env) as right:
            a, b = left.collect(), right.collect()
            assert comparable(a) == comparable(b)
            left.update(a)
            right.update(b)
            assert all(torch.equal(v, right.model.state_dict()[k]) for k, v in left.model.state_dict().items())
            assert torch.equal(left.action_generator.get_state(), right.action_generator.get_state())
            assert torch.equal(left.update_generator.get_state(), right.update_generator.get_state())


def test_attention_width_is_explicit():
    with pytest.raises(ValueError, match='divisible'):
        Architecture(15, 2, SET_ATTENTION)
    assert Architecture(15, 2, SET_MLP).hidden_size == 15
