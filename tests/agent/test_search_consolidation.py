"""The same public planner and learning path for historical and campaign starts."""
from copy import deepcopy
from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path
import uuid

import pytest

from game.agent.contracts import full as f
from game.agent.headless import HeadlessAdapter
from game.agent.headless.declared_planning import DeclaredPlanning
from game.agent.search import SearchConfig, SearchPolicy
from game.agent.search.belief import BeliefBudget
from game.agent.search.combat import CombatBelief, MODEL, ANCHOR, normalize_anchor
from game.agent.search.public_keys import public_key
from game.agent.input_views import planning_view
from game.agent.training.scenarios import Scenario
from .test_campaign_search import fixture as campaign_fixture
from .test_observed_belief import fixture as observed_fixture, advance
from .test_search import UniformPolicy


@pytest.mark.parametrize('producer', ('historical', 'campaign', 'declared'))
def test_one_belief_is_public_and_preserves_real_rng(producer):
    if producer == 'historical':
        run, adapter, _, anchor = observed_fixture(('pillage', 'strike', 'defend', 'bash', 'anger', 'defend'))
    elif producer == 'campaign':
        run, adapter, anchor = campaign_fixture(relics=('burning_blood', 'maw_bank', 'venerable_tea_set'))
    else:
        receipt = DeclaredPlanning(Scenario('overgrowth_vantom', 'controlled'))
        run = receipt.make(5)
        adapter = HeadlessAdapter(run, decision_profile=f.PROFILE)
        anchor = receipt.anchor(adapter.observe().decision)
        assert not hasattr(run, '_combat_entry_observer') and not hasattr(run, '_combat_reveals')
        assert run.snapshot() == receipt.scenario.make(5).snapshot()
    root = adapter.observe().decision
    results = []
    for _ in range(2):
        run.combat.player.deck.draw_pile.reverse()
        run.state.rng.stream('niche').random()
        snapshot = run.snapshot()
        policy = SearchPolicy(UniformPolicy(), SearchConfig(model_version=MODEL, simulations=4,
                              belief_particles=1, time_limit=20, seed=71))
        policy.begin_campaign_combat(anchor, root)
        result = policy.choose(root)
        assert result.reason is None
        assert policy.planning_start['schema'] == ANCHOR
        sampled, public = policy.belief.sample(42)
        assert public_key(public) == public_key(planning_view(root))
        assert sampled._run.state.gold == run.state.gold  # entry effects run once
        assert run.snapshot() == snapshot
        results.append((result.action_ref, result.probabilities, result.values, result.visits))
    assert results[0] == results[1]


def test_setup_stage_and_history_are_explicit():
    _, adapter, anchor = campaign_fixture(deck=('guilty', 'strike', 'defend', 'bash', 'anger'))
    from game.headless.planning import UnsupportedSearch
    with pytest.raises(UnsupportedSearch, match='missing_card_history'):
        normalize_anchor(anchor)
    _, _, old = campaign_fixture()
    normalized = normalize_anchor(old)
    normalized['setup_stage'] = 'unknown'
    with pytest.raises(ValueError, match='setup stage'):
        normalize_anchor(normalized)
    normalized = normalize_anchor(old)
    initial = f.from_dict(normalized['initial'])
    normalized['initial'] = f.to_dict(replace(initial, context=replace(initial.context,
        fields=(f.Field('entry_action_kind', 'choose_event_option'),))))
    with pytest.raises(UnsupportedSearch, match='entry_context'):
        normalize_anchor(normalized)


def test_declared_generation_pool_matches_actual_rules():
    from game.agent.training.search_benchmark import DeclaredScenario
    from .test_belief import setup
    from game.agent.search.public_keys import action_key
    declared = DeclaredScenario('potion_pool', 'test', 'control',
        replace(setup(deck=('strike', 'defend', 'bash', 'anger', 'defend')), potions=('entropic_brew', None, None)))
    receipt = DeclaredPlanning(declared)
    run = receipt.make(12)
    assert run.snapshot() == declared.make(12).snapshot()
    root = HeadlessAdapter(run, decision_profile=f.PROFILE).observe().decision
    belief = CombatBelief(receipt.anchor(root), root, seed=2, budget=BeliefBudget(1, 64, 5))
    assert belief.recover().reason is None
    for seed in range(6):
        world, public = belief.sample(seed)
        assert world._run.combat.player.rules.potion_pool == run.combat.player.rules.potion_pool
        action = next(a for a in public.candidates if a.kind == 'use_potion')
        world.step(public, action_key(public, action))
        assert all(p is None or p.definition_id in run.combat.player.rules.potion_pool for p in world._run.state.potions)


def test_fresh_certificate_rejects_hidden_lifetime_and_relic_data():
    from game.agent.training.search_sources import _fresh_certificate
    run, adapter, _, anchor = observed_fixture(('guilty', 'strike', 'defend', 'bash', 'anger'))
    normalized = normalize_anchor(anchor)
    belief = CombatBelief(normalized, adapter.observe().decision, seed=2, budget=BeliefBudget(1, 64, 5))
    assert belief.recover().reason is None
    run.state.deck[0].combats_seen = 4
    with pytest.raises(ValueError, match='card history'):
        _fresh_certificate(run, normalized, belief)
    run.state.deck[0].combats_seen = 0
    run.state.relics[0].data['hidden'] = 1
    with pytest.raises(ValueError, match='native inventory'):
        _fresh_certificate(run, normalized, belief)


@pytest.fixture
def historical_source(tmp_path):
    """A tiny original corpus and public-prefix proof, including an unopened test."""
    from game.agent.training.combat_corpus import _describe, public_digest
    from game.agent.training.benchmark_suite import data
    from game.agent.training.checkpoint import publish
    from game.agent.runner import prepare_directories
    output, private = prepare_directories(tmp_path/'original', tmp_path/'original-private')
    directory = tmp_path/'prefixes'
    directory.mkdir()
    rows, registry, groups, seeds = [], {}, [], {}
    for split, seed in (('train', 3), ('validation', 4)):
        run, adapter, belief, anchor = observed_fixture(('pillage', 'strike', 'defend', 'bash', 'anger', 'defend'), seed=seed)
        group, combat = uuid.uuid4().hex, uuid.uuid4().hex
        seeds[group] = seed
        bindings = []
        for turn in (1, 2):
            key = uuid.uuid4().hex
            public = HeadlessAdapter(run, decision_profile=f.PROFILE).observe().decision
            row = dict(case_id=key, source_group=group, combat_id=combat, split=split, region='overgrowth',
                       start_kind='opening' if turn == 1 else 'continuation', scenario='overgrowth_vantom',
                       public_state_sha256=public_digest(public), **_describe(run, public))
            raw = json.dumps(run.snapshot(), separators=(',', ':')).encode()
            sha = publish(private/(key+'.start.json'), raw, private=True)
            registry[key] = dict(case=row, snapshot_sha256=sha)
            rows.append(row)
            filename = key+'.anchor.json.gz'
            prefix_sha = publish(directory/filename, gzip.compress(data(anchor), mtime=0))
            bindings.append(dict(case_id=key, source_group=group, split=split, file=filename,
                                 sha256=prefix_sha, prefix_decisions=len(anchor['transitions']), source_snapshot_sha256=sha))
            if turn == 1:
                action = next(a for a in adapter.observe().decision.candidates if a.kind == 'end_turn')
                advance(run, adapter, belief, action, anchor)
        groups.append(dict(source_group=group, split=split, bindings=bindings))
    # Deliberately no corresponding snapshot. Import must never read this case.
    rows.append(dict(case_id=uuid.uuid4().hex, split='test'))
    registry_sha = publish(private/'registry.json', data(dict(cases=registry, campaign_seeds=seeds)), private=True)
    source = output/'corpus.json'
    sha = publish(source, data(dict(schema='sts_act1_combat_corpus_v2', status='complete', cases=rows,
        registry_sha256=registry_sha, implementation=dict(build='historical', rules='historical'))))
    manifest = tmp_path/'prefixes.json.gz'
    publish(manifest, gzip.compress(data(dict(schema='sts_verified_combat_prefixes_v1', source_sha256=sha,
        heldout_test_opened=False, groups=groups, implementation=dict(build='historical', rules='historical'))), mtime=0))
    return dict(corpus_path=source, prefix_manifest=manifest, prefix_dir=directory)


def test_source_import_verifies_continuations_without_repinning_or_test_access(historical_source, tmp_path, monkeypatch):
    from game.agent.training.search_sources import prepare_search_source, open_search_source
    from game.agent.training.combat_corpus import CombatCorpus
    original = Path(historical_source['corpus_path']).read_bytes()
    path, report = prepare_search_source(**historical_source, output_dir=tmp_path/'prepared')
    assert report['status'] == 'complete' and len(report['cases']) == 4
    assert Path(historical_source['corpus_path']).read_bytes() == original
    with pytest.raises(ValueError, match='unchanged implementation'):
        CombatCorpus(historical_source['corpus_path'])
    source = open_search_source(path)
    for row in source.cases.values():
        run = source.restore(row['case_id'], split=row['split'])
        anchor = source.planning_start(row['case_id'], split=row['split'])
        root = HeadlessAdapter(run, decision_profile=f.PROFILE).observe().decision
        belief = CombatBelief(anchor, root, seed=4, budget=BeliefBudget(1, 64, 5))
        assert belief.recover().reason is None
    with pytest.raises(ValueError, match='held-out'):
        source.split('test')
    with pytest.raises(ValueError, match='another split'):
        source.restore(source.split('train')[0]['case_id'], split='validation')
    changed = deepcopy(report)
    changed['cases'].pop()
    from game.agent.training.benchmark_suite import data
    path.write_bytes(data(changed))
    with pytest.raises(ValueError, match='population'):
        open_search_source(path)
    path.write_bytes(data(report))
    historical_source['corpus_path'].with_name('search-test-opened.json').write_text('{}')
    with pytest.raises(ValueError, match='held-out'):
        open_search_source(path)


def test_import_rejects_private_or_public_replay_mismatch(historical_source, tmp_path):
    from game.agent.training.search_sources import prepare_search_source
    from game.agent.training.benchmark_suite import data
    manifest_path = historical_source['prefix_manifest']
    manifest = json.loads(gzip.decompress(manifest_path.read_bytes()))
    binding = manifest['groups'][0]['bindings'][1]
    prefix = historical_source['prefix_dir']/binding['file']
    value = json.loads(gzip.decompress(prefix.read_bytes()))
    # This receipt is still well formed, but contradicts the native replay.
    value['transitions'][0]['reveals'] = []
    prefix.write_bytes(gzip.compress(data(value), mtime=0))
    binding['sha256'] = hashlib.sha256(prefix.read_bytes()).hexdigest()
    manifest_path.write_bytes(gzip.compress(data(manifest), mtime=0))
    with pytest.raises(ValueError, match='reveals changed'):
        prepare_search_source(**historical_source, output_dir=tmp_path/'rejected')


def test_cli_default_uses_shared_model():
    import argparse
    from game.cli.search_args import add_search_arguments, search_config
    parser = argparse.ArgumentParser()
    add_search_arguments(parser)
    assert search_config(parser.parse_args(['--search'])).model_version == MODEL


from .test_search_training import checkpoint
from .test_training_model import cpu_threads
from .test_combat_diagnostics import corpus as campaign_corpus


@pytest.mark.parametrize('source_kind', ('historical', 'campaign'))
def test_common_collection_distillation_reanalysis_and_workers(source_kind, historical_source, campaign_corpus,
                                                              checkpoint, tmp_path):
    from game.agent.training.search_sources import prepare_search_source
    from game.agent.training.search_run import run_search, load_search_corpus, distill_search, reanalyse_search
    from game.agent.training.checkpoint import load_policy
    source = (prepare_search_source(**historical_source, output_dir=tmp_path/'prepared')[0]
              if source_kind == 'historical' else campaign_corpus.path)
    config = SearchConfig(model_version=MODEL, simulations=2, max_depth=3, belief_particles=1,
                          time_limit=20, belief_seconds=10, seed=11)
    path, report = run_search(checkpoint=checkpoint, corpus_path=source, output_dir=tmp_path/'collection',
        search=config, split='train', collect=True, cases=8, max_decisions=2, workers=2)
    assert report['status'] == 'complete', report
    assert report['start_kind'] == 'opening_continuation_mix'
    assert {r['start_kind'] for r in report['episodes']} == {'opening', 'continuation'}
    assert len({r['case_id'] for r in report['episodes']}) == 8
    assert len({v['seed'] for v in report['search_configs'].values()}) == 8
    assert set(report['summary']['gumbel']['search']['fallbacks']) <= {'forced_action'}
    from game.agent.tracking.records import evaluations
    tracked = list(evaluations(report))
    assert len(tracked) == 1 and tracked[0]['label'] == 'gumbel'
    assert tracked[0]['metrics']['search/searched'] == report['summary']['gumbel']['search']['searched']
    assert len(tracked[0]['population']['search']) == 8
    for row in report['episodes']:
        targets = json.loads(gzip.decompress((path.parent/row['targets']).read_bytes()))
        assert targets['planning']['start']['schema'] == ANCHOR
        assert targets['teacher'] == report['policies'][row['policy']]
    examples = load_search_corpus(path, load_policy(checkpoint))
    assert examples.examples
    completed = {r['task_return'] for r in report['episodes'] if r['status'] == 'terminated'}
    assert all(e.value_target is None or e.value_target in completed for e in examples.examples)
    if not completed:
        assert all(e.value_target is None for e in examples.examples)
    if completed:
        from game.agent.training.search_run import audit_critic
        _, audit = audit_critic(checkpoint=checkpoint, report_path=path, output_path=tmp_path/'audit.json',
                               positions=1, rollouts=1, depth=1)
        assert audit['status'] == 'complete' and audit['summary']['positions'] == 1
        assert audit['positions'][0]['search_policy'] in audit['search_configs']
    student, learned = distill_search(checkpoint=checkpoint, report_path=path, output_dir=tmp_path/'student', updates=1)
    if not completed:
        assert learned['updates'][0]['value_loss'] == 0
    refreshed, newer = reanalyse_search(checkpoint=student.parent/'final.sts-model', report_path=path,
        output_dir=tmp_path/'refreshed', search=config, max_episodes=2)
    assert newer['status'] == 'complete'
    assert load_search_corpus(refreshed, load_policy(student.parent/'final.sts-model')).examples
    for old, new in zip(report['episodes'], newer['episodes']):
        for key in ('trajectory', 'training'):
            assert (path.parent/old[key]).read_bytes() == (refreshed.parent/new[key]).read_bytes()


def test_unknown_anchor_counts_fallbacks_without_training_targets(checkpoint, tmp_path, monkeypatch):
    from game.agent.training.search_run import run_search, load_search_corpus
    from game.agent.training.checkpoint import load_policy
    monkeypatch.setattr(DeclaredPlanning, 'anchor', lambda *_: None)
    path, report = run_search(checkpoint=checkpoint, output_dir=tmp_path/'fallback',
        search=SearchConfig(model_version=MODEL, simulations=2), split='train', collect=True, cases=1, max_decisions=2)
    row = report['episodes'][0]
    assert report['status'] == 'complete' and row['steps'] == 2
    assert row['targets_omitted'] == 'missing_or_unsupported_public_anchor' and 'targets' not in row
    assert row['search']['searched'] == 0
    with pytest.raises(ValueError, match='No supported searched decisions'):
        load_search_corpus(path, load_policy(checkpoint))
