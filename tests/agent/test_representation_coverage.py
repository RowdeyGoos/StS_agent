"""Catalog knowledge, legacy isolation, semantic differences and bounded audits."""
from dataclasses import FrozenInstanceError, replace
import json
import pickle
from types import SimpleNamespace
import zipfile

import pytest

torch = pytest.importorskip('torch')
np = pytest.importorskip('numpy')
pytest.importorskip('gymnasium')
from game.agent.contracts import full as f
from game.agent.training.catalog import public_catalog, PublicCatalog
from game.agent.training.coverage import CoverageAudit, audit_paths, catalog_coverage
from game.agent.training.features import Vocabulary, FeatureEncoder, _FEATURE_ARRAYS
from game.agent.training.model import ActorCritic, Architecture, collate
from game.agent.training.combat_features import REPRESENTATIONS
from game.agent.training.run_corpus import transfer_catalog
from .test_training_model import cpu_threads, decision
from .test_training_records import record


def potion_decision(swapped=False):
    public = decision()
    ids = ('droplet_of_precognition', 'liquid_memories') if swapped else ('liquid_memories', 'droplet_of_precognition')
    return replace(public, run=replace(public.run, children=tuple(
        f.Node('potion', name, f'potion:{i}') for i, name in enumerate(ids))),
        candidates=(*public.candidates, f.Candidate('action:4', 'use_potion', 'potion:1')))


def entries():
    return {(e.kind, e.definition_id): e for e in public_catalog().entries}


def test_catalog_covers_registries_without_game_or_dataset_construction(monkeypatch):
    from game.headless.run.engine import RunEngine
    from game.headless.core.combat import CombatEngine
    from game.headless.cards.catalog import DEFAULT_CARDS
    from game.headless.monsters.catalog import DEFAULT_MONSTERS
    from game.headless.potions.base import POTIONS
    from game.headless.relics.base import RELICS
    def forbidden(*args, **kwargs):
        pytest.fail('Catalog construction created a game')
    monkeypatch.setattr(RunEngine, '__init__', forbidden)
    monkeypatch.setattr(CombatEngine, '__init__', forbidden)
    public_catalog.cache_clear()
    before = torch.get_rng_state().clone()
    known = entries()
    assert torch.equal(before, torch.get_rng_state())
    for kind, identifiers in (('card', [c.definition_id for c in DEFAULT_CARDS.definitions]),
                              ('potion', POTIONS), ('relic', RELICS), ('enemy', DEFAULT_MONSTERS)):
        assert set(identifiers) == {name for k, name in known if k == kind}
    vocabulary = Vocabulary.fit((), split='train')
    assert vocabulary.catalog == public_catalog()
    assert catalog_coverage(vocabulary)['identity_coverage_complete']
    with pytest.raises(ValueError, match='training'):
        Vocabulary.fit([potion_decision()], split='validation')


def test_catalog_effects_are_public_base_descriptions_with_honest_limits():
    known = entries()
    fields = lambda k, n: {v.key.removeprefix('catalog.'): v.value for v in known[k, n].fields}
    memories, droplet = fields('potion', 'liquid_memories'), fields('potion', 'droplet_of_precognition')
    assert memories['selection_pile'] == 'discard_pile' and memories['selection_cost_modifier'] == 'free_this_turn'
    assert droplet['selection_pile'] == 'draw_pile' and droplet['selection_cost_modifier'] == ''
    assert fields('potion', 'block_potion')['effect.0.arg.0'] == 12
    assert fields('potion', 'energy_potion')['effect.0.arg.0'] == 2
    assert 'selection_destination' not in fields('potion', 'ashwater')
    assert fields('relic', 'burning_blood')['victory_heal'] == 6
    assert fields('relic', 'anchor')['effect.0.amount'] == 10
    assert fields('relic', 'anchor')['description_complete'] is False
    assert known['relic', 'anchor'].coverage == 'partial'
    assert all(not any(word in field.key for word in ('rng', 'seed', 'instance', 'memory'))
               for entry in known.values() for field in entry.fields)


def test_frozen_catalog_round_trips_detached_wire_and_binds_semantics(monkeypatch):
    vocabulary = Vocabulary.fit([potion_decision()], split='train')
    for clone in (Vocabulary.from_dict(vocabulary.to_dict()), pickle.loads(pickle.dumps(vocabulary))):
        assert clone == vocabulary and clone.identity == vocabulary.identity
    wire = vocabulary.to_dict()
    anchor = next(e for e in wire['catalog']['entries'] if (e['kind'], e['definition_id']) == ('relic', 'anchor'))
    next(v for v in anchor['fields'] if v['key'] == 'catalog.effect.0.amount')['value'] = 11
    changed = Vocabulary.from_dict(wire)
    assert changed.identity != vocabulary.identity
    assert entries()['relic', 'anchor'].fields == next(e for e in vocabulary.catalog.entries
        if (e.kind, e.definition_id) == ('relic', 'anchor')).fields
    with pytest.raises(FrozenInstanceError):
        vocabulary.catalog.entries[0].fields = ()
    # Loading/encoding uses the saved metadata, even if today's builder cannot run.
    import game.agent.training.catalog as module
    monkeypatch.setattr(module, 'public_catalog', lambda: pytest.fail('Consulted current catalog during inference'))
    saved = Vocabulary.from_dict(vocabulary.to_dict())
    assert all(np.array_equal(getattr(FeatureEncoder(saved).encode(potion_decision()), key),
                              getattr(FeatureEncoder(vocabulary).encode(potion_decision()), key)) for key in _FEATURE_ARRAYS)


@pytest.mark.parametrize('damage', ('mutable_value', 'missing_name', 'duplicate_entry', 'extra_field', 'huge_integer'))
def test_invalid_catalog_payload_rejected(damage):
    wire = public_catalog().to_dict()
    entry = next(e for e in wire['entries'] if e['fields'])
    if damage == 'mutable_value':
        entry['fields'][0]['value'] = []
    elif damage == 'missing_name':
        wire['names'].remove(entry['fields'][0]['key'])
    elif damage == 'duplicate_entry':
        wire['entries'].append(wire['entries'][0])
    elif damage == 'extra_field':
        entry['private_state'] = {}
    else:
        entry['fields'][0]['value'] = 2**64
    with pytest.raises(ValueError):
        PublicCatalog.from_dict(wire)


@pytest.mark.parametrize('schema', REPRESENTATIONS)
def test_potion_identity_and_effects_distinguishable_for_every_model_without_dispatch_changes(schema):
    public, swapped = potion_decision(), potion_decision(True)
    frozen = Vocabulary.fit([decision()], split='train', include_catalog=False)
    legacy = FeatureEncoder(frozen, representation=schema)
    before, after = legacy.encode(public), legacy.encode(swapped)
    assert all(np.array_equal(getattr(before, key), getattr(after, key)) for key in _FEATURE_ARRAYS)
    vocabulary = Vocabulary.fit([decision()], split='train')
    encoder = FeatureEncoder(vocabulary, representation=schema)
    a, b = encoder.encode(public), encoder.encode(swapped)
    assert not np.array_equal(a.nodes, b.nodes)
    assert not np.array_equal(a.fields, b.fields)
    assert a.graph.candidate_refs == before.graph.candidate_refs
    assert a.policy_mask == before.policy_mask
    assert np.array_equal(a.candidates, before.candidates)
    assert all(np.array_equal(a.graph.observation[k], before.graph.observation[k]) for k in a.graph.observation)
    model = ActorCritic(vocabulary, Architecture(16, 1, schema), seed=7)
    logits, values = model(collate([a, b], vocabulary=vocabulary))
    assert torch.isfinite(logits).all() and torch.isfinite(values).all()
    assert not torch.equal(logits[0], logits[1])
    (logits.square().mean() + values.square().mean()).backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())


def test_missing_entity_fails_new_encoder_and_audit_explains_it():
    vocabulary = Vocabulary.fit([decision()], split='train')
    public = replace(decision(), run=replace(decision().run,
        children=(f.Node('potion', 'future_potion', 'potion:0'),)))
    with pytest.raises(ValueError, match='Unknown learned entity identity: potion/future_potion'):
        FeatureEncoder(vocabulary).encode(public)
    audit = CoverageAudit(vocabulary)
    audit.add(public)
    assert audit.report()['unknown_tokens']['entity_identity'] == {'potion/future_potion': 1}
    assert audit.report()['observed_identity_coverage_complete'] is False
    assert catalog_coverage(Vocabulary(()))['by_kind']['potion']['known'] == 0


def test_audits_use_bounded_validated_public_traces_and_cannot_expand_vocabulary(tmp_path, monkeypatch):
    paths = [record(tmp_path)[0] for _ in range(2)]
    vocabulary = Vocabulary.fit([decision()], split='train')
    monkeypatch.setattr(Vocabulary, 'fit', lambda *a, **k: pytest.fail('Audit fitted data'))
    report = audit_paths(vocabulary, paths, max_decisions=1)
    assert report['observed_decisions'] == 1 and len(report['sources']) == 1
    with pytest.raises(ValueError, match='not test'):
        audit_paths(vocabulary, paths, split='test')
    with pytest.raises(ValueError, match='split mismatch'):
        audit_paths(vocabulary, paths, split='validation')
    private = tmp_path/'source-private'
    private.mkdir()
    with pytest.raises(ValueError, match='public paths'):
        audit_paths(vocabulary, [private])
    link = tmp_path/'linked.trajectory.jsonl'
    link.symlink_to(paths[0])
    with pytest.raises(ValueError, match='symlinks'):
        audit_paths(vocabulary, [link])


def test_catalog_transfer_remaps_weights_by_name_and_is_not_exact_resume(tmp_path):
    from game.agent.training.rewards import RewardSpec
    from game.agent.training.ppo_config import PPOExperiment
    from game.agent.training.ppo_run import run_ppo
    vocabulary = Vocabulary.fit([decision()], split='train', include_catalog=False)
    old = ActorCritic(vocabulary, Architecture(16, 1), seed=5)
    policy = SimpleNamespace(model=old, identity='test-bundle', reward_spec=RewardSpec())
    model, lineage = transfer_catalog(policy, seed=7)
    assert model.vocabulary.catalog is not None and lineage['predictions_preserved'] is False
    ids = {name: i+1 for i, name in enumerate(model.vocabulary.names)}
    assert all(torch.equal(model.name.weight[ids[name]], old.name.weight[i])
               for i, name in enumerate(vocabulary.names, 1))
    assert all(torch.equal(tensor, model.state_dict()[key]) for key, tensor in old.state_dict().items()
               if key != 'name.weight' and not key.startswith('value.'))
    assert not torch.count_nonzero(model.value[-1].weight) and not torch.count_nonzero(model.value[-1].bias)
    for settings in ({'resume_state': 'unused'}, {'reset_objective': True}, {'reset_action_policy': True}):
        with pytest.raises(ValueError, match='Representation reset'):
            run_ppo(checkpoint='unused', experiment=PPOExperiment(), output_dir=tmp_path,
                    reset_representation=True, **settings)
    with pytest.raises(ValueError, match='already uses'):
        transfer_catalog(SimpleNamespace(model=model, identity='new'))


def test_catalog_metadata_tamper_breaks_checkpoint_identity(tmp_path):
    from .test_training_checkpoint import learner
    from game.agent.training.checkpoint import save_checkpoint, load_policy
    original, changed = tmp_path/'original.sts-model', tmp_path/'changed.sts-model'
    save_checkpoint(original, learner())
    with zipfile.ZipFile(original) as archive:
        manifest, weights = json.loads(archive.read('manifest.json')), archive.read('weights.pt')
    anchor = next(e for e in manifest['vocabulary']['catalog']['entries'] if e['definition_id'] == 'anchor')
    next(v for v in anchor['fields'] if v['key'] == 'catalog.effect.0.amount')['value'] += 1
    with zipfile.ZipFile(changed, 'w') as archive:
        archive.writestr('manifest.json', json.dumps(manifest))
        archive.writestr('weights.pt', weights)
    with pytest.raises(ValueError, match='identity'):
        load_policy(changed)


def test_explicit_catalog_fork_runs_parallel_ppo_with_fresh_counters_and_resumable_state(tmp_path):
    from .test_ppo import controlled_env
    from game.agent.training.ppo import PPOLearner
    from game.agent.training.ppo_config import PPOExperiment, PPOConfig
    from game.agent.training.ppo_run import run_ppo
    from game.agent.training.checkpoint import save_ppo_checkpoint, load_policy, restore_ppo
    experiment = PPOExperiment(ppo=PPOConfig(rollout_steps=16, batch_size=8, epochs=1),
        encounters=('strike_or_die',), source='controlled_strike_or_die_v1')
    with controlled_env(encounter='strike_or_die') as env:
        env.reset(seed=0)
        vocabulary = Vocabulary.fit([env.public_state], split='train', include_catalog=False)
    old_bundle = tmp_path/'old/old.sts-model'
    with PPOLearner(ActorCritic(vocabulary, Architecture(16, 1)), experiment,
                   env_factory=controlled_env) as old:
        old.update(old.collect())
        assert old.decisions == 16
        save_ppo_checkpoint(old_bundle, old, resume_path=tmp_path/'old-private/old.resume.pt')
    output = tmp_path/'fork'
    _, report = run_ppo(checkpoint=old_bundle, experiment=experiment, output_dir=output,
        decisions=16, workers=2, reset_representation=True, env_factory=controlled_env)
    assert report['status'] == 'complete'
    assert report['start_decisions'] == report['start_iteration'] == 0
    assert report['summary']['processed_decisions'] == 16
    assert not report['initialization']['resumed']
    assert report['initialization']['representation_transfer']['optimizer_rng_cursor'] == 'fresh'
    bundle = output/'final.sts-model'
    assert load_policy(bundle).model.vocabulary.catalog == public_catalog()
    with restore_ppo(bundle, tmp_path/'fork-private/final.resume.pt', experiment=experiment,
                     env_factory=controlled_env) as resumed:
        assert resumed.decisions == 16 and resumed.collection_settings['workers'] == 2


def test_audit_command_publishes_catalog_report(tmp_path, capsys):
    from game.cli.agent_train import main
    output = tmp_path/'coverage.json'
    assert main(['audit-representation', '--output', str(output)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report == json.loads(output.read_text())
    assert report['catalog']['identity_coverage_complete']
    assert report['observed_decisions'] == 0
