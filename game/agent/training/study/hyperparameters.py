"""Shared PPO calibration and fresh-seed transfer, using the study pipeline."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import zipfile

import numpy as np
import torch

from game.agent.provenance import implementation
from ..benchmark_suite import data
from ..checkpoint import publish
from ..features import Vocabulary
from ..ppo_config import PPOConfig, PPOExperiment
from ..search_sources import development_context
from .model import parameters
from .projection import study_catalog
from .report import metrics, outcomes, compare, _training, _coverage, slices, _track
from .run import train_one, schedule, MILESTONES, CHUNKS, LIMITS
from .source import StudySource, prepare_source, _read, _sha_file
from .spec import StudyArchitecture

SCHEMA = 'sts_vantom_shared_ppo_study_v1'
REFERENCE = 'reference'
RECIPE_FIELDS = {'learning_rate', 'batch_size', 'entropy_weight'}
SELECTION = dict(model_regression_floor=-.05, severe_kl_threshold=.06,
                 severe_kl_rate_tolerance=.05, bootstrap_confidence=.95)


def load_config(path):
    c = _read(Path(path))
    fields = {'schema', 'parent_manifest', 'hidden_size', 'seeds', 'transfer_seeds',
              'collectors', 'learner_threads', 'calibration_models', 'transfer_models', 'recipes'}
    if (set(c) != fields or c['schema'] != SCHEMA or c['hidden_size'] != 64
            or type(c['hidden_size']) is not int or c['collectors'] != 16
            or type(c['collectors']) is not int or c['learner_threads'] != 4
            or type(c['learner_threads']) is not int):
        raise ValueError('Expected the complete shared PPO study configuration')
    for key, count in (('seeds', 2), ('transfer_seeds', 3)):
        values = c[key]
        if (type(values) is not list or len(values) != count or len(set(values)) != count
                or any(type(s) is not int or not 0 <= s < 2**31 for s in values)):
            raise ValueError('Invalid independent study seeds')
    if set(c['seeds']) & set(c['transfer_seeds']):
        raise ValueError('Transfer requires fresh seeds')
    if (c['calibration_models'] != ['flat_mlp-ids-basic', 'graph-mechanical-context', 'attention-ids-context']
            or c['transfer_models'] != ['pooled_mlp-mechanical-context', 'compact_pooled_mlp-mechanical-context']):
        raise ValueError('The registered calibration and transfer models must be disjoint')
    if type(c['recipes']) is not dict or len(c['recipes']) != 4 or REFERENCE not in c['recipes']:
        raise ValueError('Expected four recipes including the current reference')
    for name, recipe in c['recipes'].items():
        if (not name or not name.isidentifier() or not name.isascii()
                or type(recipe) is not dict or set(recipe) != RECIPE_FIELDS):
            raise ValueError('Invalid recipe name or settings')
        PPOConfig(**recipe)
    if len({json.dumps(v, sort_keys=True) for v in c['recipes'].values()}) != 4:
        raise ValueError('Recipes must differ')
    if c['recipes'][REFERENCE] != dict(learning_rate=.0003, batch_size=16, entropy_weight=.01):
        raise ValueError('Reference recipe changed')
    c['parent_manifest'] = str(Path(c['parent_manifest']).expanduser().resolve())
    return c


def configurations(parent, config, source_identity):
    base = json.loads(json.dumps(parent['ppo']))
    base['source'], base['schema'] = source_identity, 'sts_ppo_experiment_v3'
    base['ppo']['kl_check'] = 'minibatch_v1'
    recipes, rows = {}, {}
    for recipe, settings in config['recipes'].items():
        experiment = json.loads(json.dumps(base))
        experiment['ppo'].update(settings)
        experiment = PPOExperiment.from_dict(experiment).to_dict()
        recipes[recipe] = experiment
        for name in config['calibration_models'] + config['transfer_models']:
            old_name = name.replace('compact_pooled_mlp', 'pooled_mlp')
            old = parent['configurations'][old_name]
            kind, identity, richness = name.rsplit('-', 2)
            model = StudyArchitecture(**old['architecture'])
            if (model.features['identities'] != (identity == 'ids') or model.features['richness'] != richness
                    or model.features['ablations'] or model.catalog != study_catalog().to_dict()):
                raise ValueError('Calibration feature semantics changed')
            model = replace(model, kind=kind, hidden_size=config['hidden_size'])
            vocab = Vocabulary.from_dict(old['vocabulary'])
            rows[recipe+'__'+name] = dict(architecture=asdict(model), vocabulary=vocab.to_dict(),
                parameters=parameters(model, vocab), recipe=recipe, model_id=name, ppo=experiment)
    return recipes, rows


def freeze(config, output, *, progress):
    path = output/'manifest.json'
    context = development_context(config['parent_manifest'])
    if path.exists():
        m = _read(path)
        if (m['schema'] != SCHEMA or m['configuration'] != config
                or m['implementation'] != asdict(implementation()) or m['development_context'] != context):
            raise ValueError('Frozen shared PPO study binding changed')
        StudySource(m['source'], expected=m['source_identity'])
        return m
    parent = _read(Path(config['parent_manifest']))
    if (parent['implementation']['rules'] != implementation().rules
            or any(config[k] != parent['configuration'][k] for k in ('collectors', 'learner_threads'))
            or parent['milestones'] != list(MILESTONES) or parent['chunks'] != list(CHUNKS)):
        raise ValueError('Shared PPO study must preserve rules, allocation and decision schedule')
    source_path = output/'source'/'source.json'
    if not source_path.exists():
        p = parent['configuration']
        prepare_source(corpus_path=p['corpus'], prefix_manifest=p['prefix_manifest'], prefix_dir=p['prefix_dir'],
            output_dir=source_path.parent, development_parent=config['parent_manifest'], progress=progress)
    source = StudySource(source_path)
    if not source.development_only or source.report['development_context'] != context:
        raise ValueError('Shared PPO study requires its verified TRAIN/DEV-only source')
    populations = {s: dict(starts=len(source.split(s)), openings=sum(r['start_kind']=='opening' for r in source.split(s)),
        fights=len({r['combat_id'] for r in source.split(s)})) for s in ('train', 'validation')}
    if any(populations[s] != parent['populations'][s] for s in populations):
        raise ValueError('Original TRAIN/DEV populations changed')
    recipes, rows = configurations(parent, config, source.identity)
    main = {k:v for k,v in rows.items() if v['model_id'] in config['calibration_models']}
    m = dict(schema=SCHEMA, configuration=config, implementation=asdict(implementation()),
        frozen_at=datetime.now(timezone.utc).isoformat(), development_context=context,
        source=str(source_path), source_identity=source.identity, populations=populations,
        opening_cases={s:{r['case_id']:r['combat_id'] for r in source.split(s) if r['start_kind']=='opening'}
                       for s in ('train','validation')},
        configurations=rows, recipes=recipes, ppo=recipes[REFERENCE], hidden_size=config['hidden_size'],
        capacities=parent['capacities'], training_content=parent['training_content'],
        train_slices=parent['train_slices'], reference_crosswalk=parent['reference_crosswalk'],
        alpha_revision=parent['alpha_revision'], milestones=MILESTONES, chunks=CHUNKS,
        schedule=schedule(main, config['seeds']), transfer_seeds=config['transfer_seeds'],
        total_learners=36, total_training_decisions=3600000, decisions_per_learner=100000,
        selection=SELECTION, reference=REFERENCE, primary_metric='100k DEV greedy; equal model weights',
        initialization='Fresh random; zero updates; no imitation, transfer, warmup or search',
        transfer='Reference versus the strongest alternative; fresh seeds on two excluded pooled models',
        interpretation='Exploratory TRAIN/DEV calibration after prior TEST exposure; no fresh held-out claim.',
        test_access=False, prior_test_exposure=True)
    publish(path, data(m))
    return _read(path)


def effective_manifest(manifest, name):
    return dict(manifest, ppo=manifest['configurations'][name]['ppo'])


def aggregate(wins, recipe, models, seeds):
    """Average fixed models within seed/fight; resample only seeds and fights."""
    rows = [wins[recipe+'__'+m] for m in models]
    fights = sorted(rows[0][seeds[0]])
    if any(set(row) != set(seeds) or any(sorted(row[s]) != fights for s in seeds) for row in rows):
        raise ValueError('Model panel requires complete paired seed/fight outcomes')
    return {s: {f: float(np.mean([row[s][f] for row in rows])) for f in fights} for s in seeds}


def recipe_statistics(manifest, results):
    models = manifest['configuration']['calibration_models']
    stats = {}
    for recipe in manifest['recipes']:
        rows = [results.get(recipe+'__'+m, []) for m in models]
        if any(len(rs) != len(manifest['configuration']['seeds']) for rs in rows):
            continue
        updates = [i['update'] for rs in rows for r in rs for i in r['learning']['iterations']]
        stats[recipe] = dict(mean_greedy=float(np.mean([r['development']['win_rate'] for rs in rows for r in rs])),
            mean_sampled=float(np.mean([r['sampled']['win_rate'] for rs in rows for r in rs])),
            per_model={m:float(np.mean([r['development']['win_rate'] for r in rs])) for m,rs in zip(models,rows)},
            mean_seed_std=float(np.mean([np.std([r['development']['win_rate'] for r in rs]) for rs in rows])),
            severe_kl_rate=float(np.mean([u['after']['approx_kl'] > SELECTION['severe_kl_threshold'] for u in updates])))
    if REFERENCE in stats:
        for row in stats.values():
            row['model_deltas'] = {m:row['per_model'][m]-stats[REFERENCE]['per_model'][m] for m in models}
            row['worst_model_delta'] = min(row['model_deltas'].values())
            row['eligible'] = row['worst_model_delta'] >= SELECTION['model_regression_floor']
    return stats


def select_challenger(stats):
    if len(stats) != 4 or any('eligible' not in r for r in stats.values()):
        raise ValueError('Recipe selection requires all calibration learners')
    # An ineligible alternative is still measured in transfer, never silently
    # replaced using transfer outcomes. It cannot become the recommended preset.
    return min((r for r in stats if r != REFERENCE), key=lambda r:(not stats[r]['eligible'],
        -stats[r]['mean_greedy'], -stats[r]['worst_model_delta'], stats[r]['severe_kl_rate'],
        stats[r]['mean_seed_std'], -stats[r]['mean_sampled'], r))


def transfer_schedule(manifest, challenger):
    rows = {k:v for k,v in manifest['configurations'].items()
            if v['model_id'] in manifest['configuration']['transfer_models'] and v['recipe'] in (REFERENCE, challenger)}
    return schedule(rows, manifest['transfer_seeds'])


def validate_model_header(header, row, implementation):
    architecture = StudyArchitecture(**row['architecture'])
    vocabulary = Vocabulary.from_dict(row['vocabulary'])
    if (header['architecture'] != row['architecture'] or header['vocabulary'] != row['vocabulary']
            or header['feature_identity'] != architecture.identity(vocabulary)
            or header['learner_config'] != row['ppo'] or header['implementation'] != implementation
            or header['algorithm'] != 'ppo' or header['action_policy'] != 'commit_decisions_v1'):
        raise ValueError('Checkpoint model, features or PPO recipe differ from the registered learner')


def validate_checkpoints(manifest, learner, folder):
    """Bind the complete bounded chain, including the initialization and milestones."""
    row = manifest['configurations'][learner['configuration_id']]
    path = folder/'initialization/initial.sts-model'
    def header(p):
        with zipfile.ZipFile(p) as bundle:
            result = json.loads(bundle.read('manifest.json'))
        validate_model_header(result,row,manifest['implementation'])
        return result
    previous_header = header(path)
    if previous_header['updates'] != 0:
        raise ValueError('Calibration learner did not start from zero updates')
    previous = _sha_file(path)
    checkpoints = {'0':(path,previous)}
    expected = [folder/'training'/f'{step:06}'/'ppo.json' for step in CHUNKS]
    if [Path(p) for p in learner['reports']] != expected:
        raise ValueError('Learner training reports do not follow the registered chunk schedule')
    start = 0
    for endpoint, report_path in zip(CHUNKS,expected):
        report = _read(report_path)
        initial = report_path.parent/'initial.sts-model'
        final = report_path.parent/'final.sts-model'
        current = _sha_file(final)
        if (report['status'] != 'complete' or report['experiment'] != row['ppo']
                or report['implementation'] != manifest['implementation']
                or report['initialization'] != dict(checkpoint='ppo_v1:'+previous,resumed=True)
                or report['initial_sha256'] != _sha_file(initial) or report['final_sha256'] != current
                or report['start_decisions'] != start
                or any(report['summary'][k] != endpoint-start for k in ('accepted_decisions','processed_decisions'))):
            raise ValueError('Bounded PPO chunk changed its checkpoint, recipe or decision binding')
        initial_header = header(initial)
        if any(initial_header[k] != previous_header[k] for k in ('updates','weights_sha256','resume_state_sha256')):
            raise ValueError('Bounded PPO chunk did not restore its exact preceding state')
        previous_header = header(final)
        if endpoint in MILESTONES:checkpoints[str(endpoint)] = (final,current)
        start,previous = endpoint,current
    if Path(learner['checkpoint']) != checkpoints['100000'][0] or learner['checkpoint_sha256'] != previous:
        raise ValueError('Final learner checkpoint does not follow its bounded training chain')
    return checkpoints


def validate_evaluation(evaluation, manifest, name, seed, key, checkpoint):
    split = 'train' if key=='training' else 'validation'
    modes = [('sampled',0),('sampled',1)] if key=='sampled' else [('greedy',0)]
    path,sha = checkpoint
    binding = dict(source=manifest['source_identity'],split=split,
        policies={name:dict(checkpoint=str(path),sha256=sha)},modes=[list(v) for v in modes],seed=seed,
        training_content=manifest['training_content'],limits=LIMITS)
    cases = manifest['opening_cases'][split]
    expected = {(case,name,mode,repeat) for case in cases for mode,repeat in modes}
    rows = evaluation['episodes']
    observed = [(r['case_id'],r['policy'],r['mode'],r['repeat']) for r in rows]
    if (evaluation['status'] != 'complete' or evaluation['binding'] != binding
            or len(observed) != len(expected) or set(observed) != expected
            or any(r['combat_id'] != cases[r['case_id']] or r['split'] != split
                   or r['status'] not in ('terminated','truncated') for r in rows)):
        raise ValueError('Evaluation differs from its learner, checkpoint, mode, limits or source fights')


def selection_record(manifest, report):
    challenger = select_challenger(report['recipe_statistics'])
    return dict(schema='sts_shared_ppo_selection_v1', manifest_sha256=report['manifest_sha256'],
        challenger=challenger, reference=REFERENCE, statistics=report['recipe_statistics'],
        calibration_checkpoints={k:{str(r['seed']):r['checkpoint_sha256'] for r in rows}
            for k,rows in report['results'].items() if manifest['configurations'][k]['model_id'] in manifest['configuration']['calibration_models']},
        transfer_schedule=transfer_schedule(manifest, challenger), frozen_before_transfer=True)


def freeze_selection(output, manifest, report):
    """Reuse either published boundary after interruption; never reselect."""
    selection = selection_record(manifest, report)
    path, snapshot = output/'selection.json', output/'calibration-report.json'
    if snapshot.exists():
        if data(selection_record(manifest, _read(snapshot))) != data(selection):
            raise ValueError('Frozen calibration snapshot changed')
    else:
        if path.exists():
            raise ValueError('Frozen selection is missing its calibration snapshot')
        publish(snapshot, data(report))
    if path.exists():
        if data(_read(path)) != data(selection):
            raise ValueError('Frozen calibration selection changed')
    else:
        publish(path, data(selection))
    return selection


def run(config_path, output_dir, *, phase='all', progress=print):
    if phase not in ('prepare', 'smoke', 'run', 'report', 'all'):
        raise ValueError('Shared PPO calibration has no TEST confirmation phase')
    output = Path(output_dir).resolve(); output.mkdir(parents=True, exist_ok=True)
    config = load_config(config_path)
    torch.set_num_threads(config['learner_threads']); torch.use_deterministic_algorithms(True)
    manifest = freeze(config, output, progress=lambda i,n:progress(dict(verified_starts=i,total=n)))
    if phase == 'prepare': return manifest
    if phase == 'report': return build_report(output)
    if phase in ('smoke', 'all'):
        results = [train_one(name, row, 193, effective_manifest(manifest,name), output, smoke=True, progress=progress)
                   for name,row in manifest['configurations'].items()]
        path = output/'smoke.json'
        if not path.exists():
            publish(path,data(dict(status='complete',implementation=manifest['implementation'],
                manifest_sha256=_sha_file(output/'manifest.json'),learners=results)))
        if phase == 'smoke': return _read(path)
    for name in ('smoke.json', 'semantic-review.json'):
        gate = _read(output/name)
        if gate.get('status') != 'complete' or gate.get('implementation') != manifest['implementation']:
            raise ValueError('Current-source smoke and independent semantic review required: '+name)
    if _read(output/'smoke.json')['manifest_sha256'] != _sha_file(output/'manifest.json'):
        raise ValueError('Smoke belongs to another calibration experiment')
    for name,seed in manifest['schedule']:
        train_one(name, manifest['configurations'][name], seed, effective_manifest(manifest,name), output, progress=progress)
        build_report(output)
    report = build_report(output)
    selection = freeze_selection(output,manifest,report)
    for name,seed in selection['transfer_schedule']:
        train_one(name, manifest['configurations'][name], seed, effective_manifest(manifest,name), output, progress=progress)
        build_report(output)
    return build_report(output)


def build_report(output):
    started = time.perf_counter(); output = Path(output)
    m = _read(output/'manifest.json'); config = m['configuration']
    selection = _read(output/'selection.json') if (output/'selection.json').exists() else None
    expected = {tuple(v) for v in m['schedule']}
    if selection:
        if selection['manifest_sha256'] != _sha_file(output/'manifest.json'):
            raise ValueError('Transfer selection belongs to another manifest')
        expected |= {tuple(v) for v in transfer_schedule(m,selection['challenger'])}
    results, curves, wins, sampled, seen = {}, {}, {}, {}, set()
    learners = [_read(path) for path in sorted((output/'learners').glob('*/*/learner.json'))]
    for l in learners:
        name,seed = l['configuration_id'],l['seed']; row = m['configurations'][name]
        if ((name,seed) not in expected or (name,seed) in seen or l['configuration'] != row or l['status'] != 'complete'
                or l['smoke'] or l['collected_decisions'] != 100000 or _sha_file(l['checkpoint']) != l['checkpoint_sha256']):
            raise ValueError('Learner differs from the shared PPO manifest')
        folder = output/'learners'/name/str(seed)
        checkpoints = validate_checkpoints(m,l,folder)
        seen.add((name,seed))
        ev = {k:_read(Path(v)) for k,v in l['evaluations'].items()}
        if set(ev) != {str(s) for s in MILESTONES} | {'sampled','training'}:
            raise ValueError('Missing evaluation milestones')
        for key,e in ev.items():
            validate_evaluation(e,m,name,seed,key,checkpoints[key if key.isdigit() else '100000'])
        dev,train = metrics(ev['100000']),metrics(ev['training'])
        r = dict(seed=seed,development=dev,sampled=metrics(ev['sampled']),training=train,
            improvement_from_initialization=dev['win_rate']-metrics(ev['0'])['win_rate'],
            train_development_gap=train['win_rate']-dev['win_rate'],learning=_training(l),coverage=_coverage(ev['100000'],l),
            slices=slices(ev['100000']),checkpoint=l['checkpoint'],checkpoint_sha256=l['checkpoint_sha256'])
        results.setdefault(name,[]).append(r)
        curves.setdefault(name,{})[seed] = {int(k):metrics(v)['win_rate'] for k,v in ev.items() if k.isdigit()}
        wins.setdefault(name,{})[seed] = outcomes(ev['100000'])
        sampled.setdefault(name,{})[seed] = outcomes(ev['sampled'])
    statistics = recipe_statistics(m,results)
    comparisons = []
    for stage,models,seeds,recipes in (
            ('calibration',config['calibration_models'],config['seeds'],[r for r in m['recipes'] if r!=REFERENCE]),
            ('transfer',config['transfer_models'],config['transfer_seeds'],[selection['challenger']] if selection else [])):
        for recipe in recipes:
            if any(len(wins.get(r+'__'+model,{})) != len(seeds) for r in (recipe,REFERENCE) for model in models):continue
            for model in models+['aggregate']:
                left,right = ([aggregate(wins,r,models,seeds) for r in (recipe,REFERENCE)] if model=='aggregate'
                    else [wins[r+'__'+model] for r in (recipe,REFERENCE)])
                sl,sr = ([aggregate(sampled,r,models,seeds) for r in (recipe,REFERENCE)] if model=='aggregate'
                    else [sampled[r+'__'+model] for r in (recipe,REFERENCE)])
                family = (3 if model=='aggregate' else 9) if stage=='calibration' else (1 if model=='aggregate' else 2)
                comparisons.append(dict(stage=stage,recipe=recipe,model=model,greedy=compare(left,right),sampled=compare(sl,sr),
                    interval_family=f'{stage}_{"aggregate" if model=="aggregate" else "per_model"}_{family}',
                    greedy_family_adjusted=compare(left,right,confidence=1-.05/family)))
    complete = selection is not None and seen == expected and len(seen)==36
    report = dict(schema=SCHEMA,status='complete' if complete else 'in_progress',manifest_sha256=_sha_file(output/'manifest.json'),
        learners_completed=len(seen),total_learners=36,configurations=m['configurations'],results=results,curves=curves,
        recipe_statistics=statistics,comparisons=comparisons,selection=selection,
        collected_decisions=sum(r['learning']['accepted_decisions'] for rs in results.values() for r in rs),
        optimizer_coverage={k:sum(r['learning'][k] for rs in results.values() for r in rs)
            for k in ('optimizer_unique_decisions','optimizer_decision_visits','kl_unvisited_decisions')},
        prior_test_exposure=True,test_access=False,
        limitations=[m['interpretation'],'Two screening seeds and three fresh transfer seeds; paired bootstrap estimates are coarse.',
            'Models have equal weight, and stay fixed during resampling; architecture-wide generality is not established.',
            'All recipes use the new KL guard, so this does not estimate the guard effect against historical PPO.',
            'trained_decisions counts decisions in updated rollouts; optimizer_unique_decisions counts actual gradient coverage.',
            'Minibatch KL estimates are noisy and are not a hard trust-region bound.'],
        timings=dict(training_seconds=sum(r['learning']['seconds'] for rs in results.values() for r in rs),
            evaluation_seconds=sum(_read(Path(p))['seconds'] for l in learners for p in l['evaluations'].values())))
    if selection and selection_record(m,report) != selection:
        # JSON normalizes schedule tuples, so compare canonical payloads.
        if data(selection_record(m,report)) != data(selection):
            raise ValueError('Calibration outcomes changed after transfer selection')
    if complete:
        report['recommendation'] = recommend(m,report)
    destination = output/'report'; destination.mkdir(exist_ok=True)
    write_summary(destination,m,report)
    report['timings']['report_seconds'] = time.perf_counter()-started
    (destination/'comparisons.json').write_bytes(data(report))
    if complete:
        (destination/'shared-preset.json').write_bytes(data(dict(schema='sts_shared_ppo_preset_v1',
            evidence_manifest_sha256=report['manifest_sha256'],recommendation=report['recommendation'],
            experiment=m['recipes'][report['recommendation']['recipe']],automatic_default_change=False)))
    if curves:
        plots(destination,m,report)
        _track(output,report,curves)
    return report


def recommend(manifest, report):
    recipe = report['selection']['challenger']
    comparisons = report['comparisons']
    get = lambda stage: next(c for c in comparisons if c['stage']==stage and c['recipe']==recipe and c['model']=='aggregate')
    transfer = [c for c in comparisons if c['stage']=='transfer' and c['model']!='aggregate']
    severe = {}
    for r in (recipe,REFERENCE):
        updates = [i['update'] for model in manifest['configuration']['transfer_models']
                   for row in report['results'][r+'__'+model] for i in row['learning']['iterations']]
        severe[r] = float(np.mean([u['after']['approx_kl'] > SELECTION['severe_kl_threshold'] for u in updates]))
    checks = dict(calibration_model_floor=report['recipe_statistics'][recipe]['eligible'],
        calibration_gain=get('calibration')['greedy_family_adjusted']['interval'][0] > 0,
        transfer_gain=get('transfer')['greedy']['interval'][0] > 0,
        transfer_model_floor=min(c['greedy']['mean'] for c in transfer)>=SELECTION['model_regression_floor'],
        severe_kl_rate=severe[recipe] <= severe[REFERENCE]+SELECTION['severe_kl_rate_tolerance'])
    return dict(recipe=recipe if all(checks.values()) else REFERENCE,challenger=recipe,checks=checks,
        severe_kl_rates=severe,rule='Prefer reference unless positive paired aggregate gains replicate without a material model regression or increased severe KL rate.',
        scope='Opt-in combat research preset; no production model or default change; TRAIN/DEV exploratory evidence.')


def write_summary(destination,manifest,report):
    lines = ['# Vantom shared PPO calibration','',
        f"{report['learners_completed']}/36 learners; {report['collected_decisions']:,}/3,600,000 collected decisions.",'',
        'Every recipe uses minibatch KL stopping, width 64 and fresh 100k training. TRAIN/DEV only.','',
        '| Recipe | LR | Minibatch | Entropy | Calibration greedy | Worst model change |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for name,settings in manifest['configuration']['recipes'].items():
        row=report['recipe_statistics'].get(name,{})
        score=f"{row['mean_greedy']:.1%}" if row else 'pending'
        worst=f"{100*row['worst_model_delta']:+.1f} pp" if 'worst_model_delta' in row else 'pending'
        lines.append(f"| {name} | {settings['learning_rate']} | {settings['batch_size']} | {settings['entropy_weight']} | {score} | {worst} |")
    lines += ['', '| Model / recipe | Seed | Greedy DEV | Sampled DEV | TRAIN | Zero-signal skipped | Optimizer unique decisions |',
              '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name,rows in report['results'].items():
        for row in rows:
            lines.append(f"| {name} | {row['seed']} | {row['development']['win_rate']:.1%} | {row['sampled']['win_rate']:.1%} | {row['training']['win_rate']:.1%} | {row['learning']['skipped_decisions']} | {row['learning']['optimizer_unique_decisions']} |")
    if report.get('recommendation'):
        lines += ['', 'Recommended opt-in recipe: **'+report['recommendation']['recipe']+'**.',json.dumps(report['recommendation']['checks'],sort_keys=True)]
    lines += ['',*report['limitations'],'']
    (destination/'README.md').write_text('\n'.join(lines))


def plots(destination,manifest,report):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    models=manifest['configuration']['calibration_models']+manifest['configuration']['transfer_models']
    fig,axes=plt.subplots(2,3,figsize=(15,8),sharey=True,layout='constrained')
    for ax,model in zip(axes.flat,models):
        for recipe in manifest['recipes']:
            rows=report['curves'].get(recipe+'__'+model,{})
            if not rows:continue
            steps=sorted(next(iter(rows.values())))
            values=np.asarray([[r[s] for s in steps] for r in rows.values()])
            ax.plot(steps,values.mean(0),label=recipe)
            ax.fill_between(steps,values.min(0),values.max(0),alpha=.1)
        ax.set(title=model,xlabel='Collected decisions',ylabel='DEV greedy win rate',ylim=(0,1))
        if ax.lines:ax.legend(fontsize=8)
    axes.flat[-1].axis('off')
    fig.suptitle('Shared PPO recipes; bands show seed ranges; pooled models reserved for transfer')
    fig.savefig(destination/'learning-curves.png',dpi=160);plt.close(fig)
