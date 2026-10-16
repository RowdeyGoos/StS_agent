"""TRAIN/DEV-only fixed-width follow-up using the existing study learner."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import numpy as np
import torch

from game.agent.provenance import implementation
from ..benchmark_suite import data
from ..checkpoint import publish
from ..features import Vocabulary
from ..search_sources import development_context
from .model import parameters
from .projection import study_catalog
from .report import metrics, outcomes, compare, _training, _coverage, slices, _track
from .run import train_one, schedule, MILESTONES, CHUNKS
from .source import StudySource, prepare_source, _read, _sha_file
from .spec import StudyArchitecture, RICHNESS

SCHEMA = 'sts_vantom_flat_width_study_v1'
ENTITY_SCHEMA = 'sts_vantom_entity_encoding_study_v1'


def load_config(path):
    config = _read(Path(path))
    fields = {'schema', 'parent_manifest', 'hidden_size', 'seeds', 'collectors', 'learner_threads'}
    if (set(config) != fields or config['schema'] not in (SCHEMA, ENTITY_SCHEMA)
            or type(config['hidden_size']) is not int or not 8 <= config['hidden_size'] <= 1024
            or len(config['seeds']) != 3 or len(set(config['seeds'])) != 3
            or any(type(s) is not int or not 0 <= s < 2**31 for s in config['seeds'])
            or type(config['collectors']) is not int or not 1 <= config['collectors'] <= 16
            or config['learner_threads'] != 4):
        raise ValueError('Expected the complete three-seed flat-width study configuration')
    config['parent_manifest'] = str(Path(config['parent_manifest']).expanduser().resolve())
    return config


def configurations(parent, width):
    """Change only flat hidden width; preserve the three nested feature specs."""
    result = {}
    for identity in ('ids', 'mechanical'):
        for richness in RICHNESS:
            name = f'flat_mlp-{identity}-{richness}'
            old = parent['configurations'][name]
            model = StudyArchitecture(**old['architecture'])
            if (model.kind != 'flat_mlp' or model.features['richness'] != richness
                    or model.features['identities'] != (identity == 'ids')
                    or model.features['ablations']):
                raise ValueError('Unexpected parent flat MLP features')
            model = replace(model, hidden_size=width)
            vocabulary = Vocabulary.from_dict(old['vocabulary'])
            result[name] = dict(architecture=asdict(model), vocabulary=vocabulary.to_dict(),
                                parameters=parameters(model, vocabulary))
    return result


def freeze(config, output, *, progress):
    path = output/'manifest.json'
    context = development_context(config['parent_manifest'])
    if path.exists():
        manifest = _read(path)
        if (manifest['schema'] != config['schema'] or manifest['configuration'] != config
                or manifest['implementation'] != asdict(implementation())
                or manifest['development_context'] != context):
            raise ValueError('Frozen fixed-width study binding changed')
        StudySource(manifest['source'], expected=manifest['source_identity'])
        return manifest
    parent = _read(Path(config['parent_manifest']))
    if (parent['implementation']['rules'] != implementation().rules
            or any(config[k] != parent['configuration'][k] for k in ('seeds', 'collectors', 'learner_threads'))
            or parent['milestones'] != list(MILESTONES) or parent['chunks'] != list(CHUNKS)):
        raise ValueError('Fixed-width follow-up must preserve rules, allocation, seeds and schedule')
    if config['schema'] == ENTITY_SCHEMA:
        from .entity_study import configurations as configure_entities
        rows = configure_entities(parent, config['hidden_size'])
    else:
        rows = configurations(parent, config['hidden_size'])
    if any(row['architecture']['catalog'] != study_catalog().to_dict() for row in rows.values()):
        raise ValueError('Feature mechanics changed from the parent experiment')
    source_path = output/'source'/'source.json'
    if not source_path.exists():
        previous = parent['configuration']
        prepare_source(corpus_path=previous['corpus'], prefix_manifest=previous['prefix_manifest'],
                       prefix_dir=previous['prefix_dir'], output_dir=source_path.parent,
                       development_parent=config['parent_manifest'], progress=progress)
    source = StudySource(source_path)
    if not source.development_only or source.report['development_context'] != context:
        raise ValueError('Fixed-width follow-up requires its bound TRAIN/DEV-only source')
    populations = {split: dict(starts=len(source.split(split)),
        openings=sum(r['start_kind'] == 'opening' for r in source.split(split)),
        fights=len({r['combat_id'] for r in source.split(split)})) for split in ('train', 'validation')}
    if any(populations[s] != parent['populations'][s] for s in populations):
        raise ValueError('Original TRAIN/DEV populations changed')
    ppo = json.loads(json.dumps(parent['ppo']))
    ppo['source'] = source.identity
    manifest = dict(schema=config['schema'], configuration=config, implementation=asdict(implementation()),
        frozen_at=datetime.now(timezone.utc).isoformat(), development_context=context,
        source=str(source_path), source_identity=source.identity, populations=populations,
        configurations=rows, hidden_size=config['hidden_size'], processing_layers=2,
        capacities=parent['capacities'], training_content=parent['training_content'],
        train_slices=parent['train_slices'], reference_crosswalk=parent['reference_crosswalk'],
        alpha_revision=parent['alpha_revision'], ppo=ppo, milestones=MILESTONES, chunks=CHUNKS,
        schedule=schedule(rows, config['seeds']), decisions_per_learner=100000,
        total_learners=18, total_training_decisions=1800000,
        initialization='fresh random; zero updates; no demonstrations, transfer or warmup',
        primary_comparisons=[(f'flat_mlp-{identity}-{richness}', f'flat_mlp-{identity}-basic')
                             for identity in ('ids', 'mechanical') for richness in ('mechanics', 'context')],
        primary_metric='mean 100k DEV greedy wins across three seeds',
        intervals='paired source fights and learner seeds; 95% exploratory and Bonferroni family of four',
        test_access=False, prior_test_exposure=True,
        interpretation='Exploratory fixed-width comparison; richer inputs intentionally have more parameters. '
                       'Original TEST locks and held-out ownership remain unchanged.')
    if config['schema'] == ENTITY_SCHEMA:
        from .entity_study import comparisons, secondary_comparisons
        manifest.update(total_learners=24,total_training_decisions=2400000,
            primary_comparisons=comparisons(),secondary_comparisons=secondary_comparisons(),
            intervals='Paired source fights and seeds; 95% exploratory and Bonferroni family of six',
            interpretation='Exploratory comparison of flat, original pooled, compact pooled and hierarchical pooled. '
                'Basic/context, no vocabulary, common width; parameters and frontend depth differ. '
                'Original TEST ownership/reservations remain unchanged.')
    publish(path, data(manifest))
    return _read(path)


def run(config_path, output_dir, *, phase='all', progress=print):
    if phase not in ('prepare', 'smoke', 'run', 'report', 'all'):
        raise ValueError('Fixed-width follow-up has no TEST confirmation phase')
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    config = load_config(config_path)
    torch.set_num_threads(config['learner_threads'])
    torch.use_deterministic_algorithms(True)
    manifest = freeze(config, output, progress=lambda i, n: progress(dict(verified_starts=i, total=n)))
    if phase == 'prepare':
        return manifest
    if phase == 'report':
        return build_report(output)
    if phase in ('smoke', 'all'):
        results = [train_one(name, row, 193, manifest, output, smoke=True, progress=progress)
                   for name, row in manifest['configurations'].items()]
        path = output/'smoke.json'
        if not path.exists():
            publish(path, data(dict(status='complete', implementation=manifest['implementation'],
                                    manifest_sha256=_sha_file(output/'manifest.json'), learners=results)))
        if phase == 'smoke':
            return _read(path)
    for name in ('smoke.json', 'semantic-review.json'):
        gate = _read(output/name)
        if gate.get('status') != 'complete' or gate.get('implementation') != manifest['implementation']:
            raise ValueError('Current-source smoke and independent semantic review required: '+name)
    if _read(output/'smoke.json')['manifest_sha256'] != _sha_file(output/'manifest.json'):
        raise ValueError('Smoke belongs to another fixed-width experiment')
    for name, seed in manifest['schedule']:
        train_one(name, manifest['configurations'][name], seed, manifest, output, progress=progress)
        build_report(output)
    return build_report(output)


def build_report(output):
    started = time.perf_counter()
    output = Path(output)
    manifest = _read(output/'manifest.json')
    entity = manifest['schema'] == ENTITY_SCHEMA
    family = len(manifest['primary_comparisons'])
    results, curves, wins, sampled = {}, {}, {}, {}
    learners = [_read(path) for path in sorted((output/'learners').glob('*/*/learner.json'))]
    expected = {tuple(pair) for pair in manifest['schedule']}
    seen = set()
    for learner in learners:
        name, seed = learner['configuration_id'], learner['seed']
        key = (name, seed)
        if (key not in expected or key in seen or learner['configuration'] != manifest['configurations'][name]
                or learner['status'] != 'complete' or learner['collected_decisions'] != 100000
                or learner['smoke'] or _sha_file(learner['checkpoint']) != learner['checkpoint_sha256']):
            raise ValueError('Learner differs from the fixed-width manifest')
        seen.add(key)
        evaluations = {k: _read(Path(v)) for k, v in learner['evaluations'].items()}
        for mode, evaluation in evaluations.items():
            split = 'train' if mode == 'training' else 'validation'
            if (evaluation['status'] != 'complete' or evaluation['binding']['source'] != manifest['source_identity']
                    or evaluation['binding']['split'] != split):
                raise ValueError('Evaluation differs from the TRAIN/DEV-only experiment')
        endpoint, sample = evaluations['100000'], evaluations['sampled']
        dev, training = metrics(endpoint), metrics(evaluations['training'])
        row = dict(seed=seed, development=dev, sampled=metrics(sample), training=training,
            improvement_from_initialization=dev['win_rate']-metrics(evaluations['0'])['win_rate'],
            train_development_gap=training['win_rate']-dev['win_rate'], learning=_training(learner),
            coverage=_coverage(endpoint, learner), slices=slices(endpoint),
            checkpoint=learner['checkpoint'], checkpoint_sha256=learner['checkpoint_sha256'])
        results.setdefault(name, []).append(row)
        curves.setdefault(name, {})[seed] = {int(k): metrics(v)['win_rate'] for k, v in evaluations.items() if k.isdigit()}
        wins.setdefault(name, {})[seed] = outcomes(endpoint)
        sampled.setdefault(name, {})[seed] = outcomes(sample)
    comparisons = []
    for a, b in manifest['primary_comparisons']:
        if len(wins.get(a, {})) == 3 and len(wins.get(b, {})) == 3:
            comparisons.append(dict(a=a, b=b, greedy=compare(wins[a], wins[b]),
                greedy_family_adjusted=compare(wins[a], wins[b], confidence=1-.05/family),
                sampled=compare(sampled[a], sampled[b])))
    secondary = [dict(a=a,b=b,greedy=compare(wins[a],wins[b]),sampled=compare(sampled[a],sampled[b]))
        for a,b in manifest.get('secondary_comparisons',()) if len(wins.get(a,{}))==3 and len(wins.get(b,{}))==3]
    report = dict(schema=manifest['schema'], status='complete' if seen == expected else 'in_progress',
        manifest_sha256=_sha_file(output/'manifest.json'), learners_completed=len(learners),
        total_learners=manifest['total_learners'], collected_decisions=sum(r['learning']['accepted_decisions'] for rs in results.values() for r in rs),
        results=results, configurations=manifest['configurations'], comparisons=comparisons, curves=curves,
        prior_test_exposure=True, test_access=False, hidden_size=manifest['hidden_size'],
        limitations=[manifest['interpretation'], 'Three seeds and 42 DEV source fights; intervals are coarse.',
            'This compares the richer representation with its larger input matrices, at fixed hidden width.',
            'Incomplete mechanics/history and constant features limit conclusions.',
            'Recorded memory covers the parent process, not all collectors.'],
        timings=dict(training_seconds=sum(r['learning']['seconds'] for rs in results.values() for r in rs),
            evaluation_seconds=sum(sum(_read(Path(p))['seconds'] for p in l['evaluations'].values()) for l in learners)))
    if entity:
        report['secondary_comparisons']=secondary
        report['limitations'][2]='Common width; feature frontend and parameter counts differ. Secondary comparisons are exploratory.'
    destination = output/'report'
    destination.mkdir(exist_ok=True)
    lines = ['# Vantom '+('entity encoding comparison' if entity else 'flat MLPs at equal hidden width'), '',
        f"{len(learners)}/{manifest['total_learners']} learners complete; {report['collected_decisions']:,}/{manifest['total_training_decisions']:,} collected decisions.", '',
        f"Common hidden width {manifest['hidden_size']}; 100k decisions and unchanged PPO.",
        'All learners are freshly initialized. TRAIN/DEV only; previous TEST exposure is acknowledged.', '',
        '| Configuration | Parameters | Seeds complete | DEV greedy | DEV sampled | TRAIN greedy |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for name, config in manifest['configurations'].items():
        rows = results.get(name, [])
        rates = [f"{np.mean([r[k]['win_rate'] for r in rows]):.1%}" if rows else '—'
                 for k in ('development', 'sampled', 'training')]
        lines.append(f"| {name} | {config['parameters']['total']:,} | {len(rows)}/3 | {' | '.join(rates)} |")
    lines += ['', 'Primary endpoint comparisons: '+('hierarchical minus comparator at matched richness.' if entity else 'richer minus basic within identity setting.'), '',
        f'| Comparison | Difference | Paired 95% interval | Family-adjusted {100*(1-.05/family):.3f}% interval |',
        '| --- | ---: | ---: | ---: |']
    for row in comparisons:
        g, a = row['greedy'], row['greedy_family_adjusted']
        interval = lambda v: '['+', '.join(f'{100*x:+.1f}' for x in v['interval'])+'] pp'
        lines.append(f"| {row['a']} − {row['b']} | {100*g['mean']:+.1f} pp | {interval(g)} | {interval(a)} |")
    lines += ['', *report['limitations'], '']
    for row in secondary:
        lines += [f"Secondary: {row['a']} − {row['b']}: {100*row['greedy']['mean']:+.1f} pp; "
                  f"paired 95% interval {row['greedy']['interval']}."]
    (destination/'README.md').write_text('\n'.join(lines))
    report['timings']['report_seconds'] = time.perf_counter()-started
    (destination/'comparisons.json').write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n')
    if curves:
        _plots(destination, manifest, curves, comparisons)
        _track(output, report, curves)
    return report


def _plots(output, manifest, curves, comparisons):
    if manifest['schema'] == ENTITY_SCHEMA:
        from .entity_study import plots
        return plots(output,manifest,curves,comparisons)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), sharey=True, layout='constrained')
    for ax, identity in zip(axes, ('ids', 'mechanical')):
        for richness in RICHNESS:
            rows = curves.get(f'flat_mlp-{identity}-{richness}', {})
            if not rows:
                continue
            steps = sorted(next(iter(rows.values())))
            values = np.asarray([[r[s] for s in steps] for r in rows.values()])
            ax.plot(steps, values.mean(0), label=richness)
            ax.fill_between(steps, values.min(0), values.max(0), alpha=.12)
        ax.set(title='Content identities' if identity == 'ids' else 'No vocabulary',
               xlabel='Collected training decisions', ylabel='DEV greedy win rate', ylim=(0, 1))
        if ax.lines:
            ax.legend()
    fig.suptitle(f"Flat MLPs: two {manifest['hidden_size']}-unit hidden layers; bands show seed ranges")
    fig.savefig(output/'learning-curves.png', dpi=160)
    plt.close(fig)
    if comparisons:
        fig, ax = plt.subplots(figsize=(10, 4), layout='constrained')
        means = np.asarray([r['greedy']['mean']*100 for r in comparisons])
        bounds = np.asarray([r['greedy_family_adjusted']['interval'] for r in comparisons])*100
        ax.errorbar(means, range(len(means)), xerr=np.stack((means-bounds[:,0], bounds[:,1]-means)), fmt='o')
        ax.set(yticks=range(len(means)), yticklabels=[r['a'].removeprefix('flat_mlp-') for r in comparisons],
               xlabel='DEV win-rate difference from basic (percentage points; paired 98.75% intervals)')
        ax.axvline(0, color='grey', linestyle='--')
        fig.savefig(output/'richness-comparisons.png', dpi=160)
        plt.close(fig)
