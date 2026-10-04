"""Inference/restart contracts, corpus splits and combat-owned hybrid routing."""
from dataclasses import asdict
import io
import json
from pathlib import Path
import zipfile

import pytest

torch = pytest.importorskip('torch')
pytest.importorskip('gymnasium')
from game.agent.full_policy import choose_action
from game.agent.runner import RunConfig, run_episode
from game.agent.training.checkpoint import save_checkpoint, load_policy, restore_learner, publish
from game.agent.training.features import FeatureEncoder
from game.agent.training.learner import ImitationLearner, LearnerConfig, load_corpus
from game.agent.training.model import ActorCritic, Architecture
from game.agent.training.rewards import RewardSpec
from .test_training_model import tiny_corpus, decision, cpu_threads
from .test_training_records import record
from .test_combat_training import fixture


def learner():
    corpus = tiny_corpus()
    return ImitationLearner(ActorCritic(corpus.vocabulary, Architecture(24, 2), seed=17), corpus,
                            LearnerConfig(batch_size=3, learning_rate=.002), seed=5)


@pytest.fixture
def bundle(tmp_path):
    owner = learner()
    for _ in range(3):
        owner.step()
    public, private = tmp_path/'public/model.sts-model', tmp_path/'private/model.resume.pt'
    save_checkpoint(public, owner, resume_path=private)
    return owner, public, private


def test_reload_reproduces_inference_and_private_state_is_separate(bundle):
    owner, public, private = bundle
    policy = load_policy(public)
    for p in (decision(30, 6, 3), decision(70, 8, 3)):
        from game.agent.training.model import collate, log_probabilities
        encoded = FeatureEncoder(owner.model.vocabulary).encode(p)
        batch = collate([encoded], vocabulary=owner.model.vocabulary)
        with torch.inference_mode():
            logits, values = owner.model(batch)
            expected = dict(zip(encoded.graph.candidate_refs, log_probabilities(logits, batch['mask']).exp()[0].tolist()))
        actual, value = policy.probabilities(p)
        assert actual == expected and value == values.item()
        assert policy(p) in p.candidates
    with zipfile.ZipFile(public) as archive:
        assert sorted(archive.namelist()) == ['manifest.json', 'weights.pt']
        manifest = json.loads(archive.read('manifest.json'))
        # Public catalog tokens may include words such as "order". They are
        # content names, not a serialized private sampling order or RNG state.
        def keys(value):
            if type(value) is dict:
                return set(value).union(*(keys(v) for v in value.values()))
            if type(value) is list:
                return set().union(*(keys(v) for v in value))
            return set()
        assert not keys(manifest) & {'optimizer', 'learner_rng', 'seed', 'cursor', 'order'}
    assert private.stat().st_mode & 0o777 == 0o600
    assert private.parent.stat().st_mode & 0o777 == 0o700
    with pytest.raises(FileExistsError):
        save_checkpoint(public, owner, resume_path=private)


def test_cpu_resume_matches_uninterrupted_updates_and_sampling_cursor(bundle):
    owner, public, private = bundle
    resumed = restore_learner(public, private, owner.corpus)
    for _ in range(7):
        a, b = owner.step(), resumed.step()
        assert {k:v for k,v in a.items() if k != 'seconds'} == {k:v for k,v in b.items() if k != 'seconds'}
    assert owner.cursor == resumed.cursor and owner.updates == resumed.updates
    assert torch.equal(owner.order, resumed.order)
    assert torch.equal(owner.generator.get_state(), resumed.generator.get_state())
    assert all(torch.equal(v, resumed.model.state_dict()[k]) for k,v in owner.model.state_dict().items())


@pytest.mark.parametrize('edit', [
    lambda m: m.update(schema='future'), lambda m: m.update(contract='combat_reward_map_v1'),
    lambda m: m.update(encoding='unknown'), lambda m: m.update(feature_identity='unknown'),
    lambda m: m.update(reward_identity='unknown'), lambda m: m.update(weights_sha256='0'*64),
    lambda m: m['architecture'].update(hidden_size=900), lambda m: m['vocabulary'].update(unknown_id=99),
    lambda m: m.update(seed=123),
])
def test_incompatible_or_corrupt_inference_bundles_reject(bundle, tmp_path, edit):
    _, original, _ = bundle
    with zipfile.ZipFile(original) as archive:
        manifest, weights = json.loads(archive.read('manifest.json')), archive.read('weights.pt')
    edit(manifest)
    path = tmp_path/'bad.sts-model'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('manifest.json', json.dumps(manifest))
        archive.writestr('weights.pt', weights)
    with pytest.raises(ValueError):
        load_policy(path)


def test_partial_wrong_objective_wrong_digest_and_resume_bindings_reject(bundle, tmp_path):
    owner, path, private = bundle
    with pytest.raises(ValueError, match='published'):
        load_policy(path.with_name(path.name+'.partial'))
    with pytest.raises(ValueError, match='objective'):
        load_policy(path, reward_spec=RewardSpec({'combat_loss': -1}))
    with pytest.raises(ValueError, match='frozen'):
        load_policy(path, expected_sha256='0'*64)
    data = torch.load(private, weights_only=True)
    for key, value in (('bundle_sha256', 'other'), ('boundary', 'mid_combat'), ('corpus', 'different'), ('cursor', 999)):
        bad = dict(data)
        bad[key] = value
        location = private.parent/(key+'.resume.pt')
        buffer = io.BytesIO()
        torch.save(bad, buffer)
        publish(location, buffer.getvalue(), private=True)
        with pytest.raises(ValueError):
            restore_learner(path, location, owner.corpus)


def test_nonfinite_weights_reject_even_with_a_matching_digest(bundle, tmp_path):
    import hashlib
    _, original, _ = bundle
    with zipfile.ZipFile(original) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        state = torch.load(io.BytesIO(archive.read('weights.pt')), weights_only=True)
    next(iter(state.values())).flatten()[0] = torch.nan
    buffer = io.BytesIO()
    torch.save(state, buffer)
    manifest['weights_sha256'] = hashlib.sha256(buffer.getvalue()).hexdigest()
    path = tmp_path/'nan.sts-model'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('manifest.json', json.dumps(manifest))
        archive.writestr('weights.pt', buffer.getvalue())
    with pytest.raises(ValueError, match='nonfinite'):
        load_policy(path)


def test_partial_publication_is_exclusive_and_resume_requires_private_permissions(bundle, tmp_path):
    owner, public, private = bundle
    target = tmp_path/'report.json'
    partial = target.with_name(target.name+'.partial')
    partial.write_bytes(b'incomplete')
    with pytest.raises(FileExistsError):
        publish(target, b'new')
    assert not target.exists() and partial.read_bytes() == b'incomplete'
    private.chmod(0o644)
    with pytest.raises(ValueError, match='owner-only'):
        restore_learner(public, private, owner.corpus)


def test_recorded_corpus_uses_task_return_and_excludes_cutoffs_from_value_labels(tmp_path):
    victory = record(tmp_path, spec=RewardSpec({'win_hp_fraction': .25}))
    cutoff = record(tmp_path, mode='cutoff', spec=RewardSpec({'win_hp_fraction': .25}))
    corpus = load_corpus([victory, cutoff], split='train')
    assert len(corpus.examples) == 2
    assert corpus.examples[0].value_target == 1 + .25*46/80
    assert corpus.examples[1].value_target is None
    with pytest.raises(ValueError):
        load_corpus([victory], split='validation', vocabulary=corpus.vocabulary)
    with pytest.raises(ValueError, match='frozen'):
        load_corpus([victory], split='validation')


@pytest.mark.parametrize('edit', [
    lambda s: s['optimizer']['param_groups'][0].update(lr=.3),
    lambda s: s['optimizer']['param_groups'][0].update(betas=(.1, .2)),
    lambda s: s['optimizer']['state'].pop(0),
    lambda s: s['optimizer']['state'][0].update(step=torch.tensor(1.)),
    lambda s: s['optimizer']['state'][0].update(exp_avg=torch.zeros(1)),
    lambda s: s['optimizer']['state'][0]['exp_avg_sq'].fill_(-1),
    lambda s: s['optimizer']['state'][0]['exp_avg'].fill_(torch.nan),
    lambda s: s['config'].update(batch_size=99),
])
def test_resume_rejects_changed_options_missing_moments_and_invalid_counters(bundle, edit):
    owner, public, private = bundle
    data = torch.load(private, weights_only=True)
    edit(data)
    buffer = io.BytesIO()
    torch.save(data, buffer)
    path = private.parent/'corrupt.resume.pt'
    publish(path, buffer.getvalue(), private=True)
    with pytest.raises(ValueError):
        restore_learner(public, path, owner.corpus)


def test_exact_resume_requires_same_sources_but_inference_can_read_prior_schema(bundle, monkeypatch):
    from dataclasses import replace
    from game.agent.provenance import implementation
    owner, public, private = bundle
    modified = replace(implementation(), build='0'*64)
    monkeypatch.setattr('game.agent.training.checkpoint.implementation', lambda:modified)
    assert load_policy(public)(decision()) in decision().candidates
    with pytest.raises(ValueError, match='unchanged implementation'):
        restore_learner(public, private, owner.corpus)


def test_hybrid_uses_owned_combat_for_nested_selector_and_then_hands_back(tmp_path):
    run = fixture(3, enemy_hp=6, cards=('armaments', 'strike', 'defend'))
    learned, other = [], []
    def combat_policy(public):
        from game.agent.contracts import full as f
        learned.append('selection' if any(n.kind == 'selection' for n in f.walk(public.context)) else public.context.kind)
        cards = {n.ref:n for n in f.walk(public.context) if n.kind == 'card'}
        armaments = next((a for a in public.candidates if a.kind == 'play_card' and
                         cards[a.subject].definition_id == 'armaments'), None)
        if armaments:
            return armaments
        return choose_action(public)
    def fallback(public):
        other.append(public.context.kind)
        return choose_action(public)
    # Stop after the first reward action: this fixture authors a fight, not a map.
    result = run_episode(RunConfig(seed=3, max_decisions=4, evidence='controlled_fixture'),
        output_dir=tmp_path/'public', audit_dir=tmp_path/'private', engine_factory=lambda seed:run,
        policy=fallback, combat_policy=combat_policy, policy_identity='controlled_hybrid_v1')
    assert 'selection' in learned and 'combat' in learned
    assert other and all(kind != 'combat' for kind in other)
    assert result.timings.steps > len(learned)


def test_synthetic_controller_routing_uses_owner_result_without_context_label():
    from types import SimpleNamespace
    from game.agent.runner import _chooser
    from game.agent.headless.combat_summary import CombatSummary
    fallback, combat = object(), object()
    owner = SimpleNamespace(combat_summary=CombatSummary('combat:1', 'ongoing', 40, 80, 1))
    assert _chooser(owner, fallback, combat) is combat
    owner.combat_summary = CombatSummary('combat:1', 'victory', 46, 80, 1)
    assert _chooser(owner, fallback, combat) is fallback
    owner.combat_summary = None
    assert _chooser(owner, fallback, combat) is fallback
