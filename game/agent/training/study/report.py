"""Fight/seed paired study comparisons, coverage and local MLflow artifacts."""
from collections import defaultdict
import itertools
import json
from pathlib import Path
import time
import numpy as np

from .source import _read, _sha_file
from .spec import channels, digest


def metrics(report):
    rows = report['episodes']
    wins = [r for r in rows if (r.get('combat') or {}).get('outcome') == 'victory']
    decisions = sum(r['steps'] for r in rows)
    return dict(episodes=len(rows), decisions=decisions, wins=len(wins), win_rate=len(wins)/len(rows),
        cutoff_rate=sum(r['status'] == 'truncated' for r in rows)/len(rows),
        winning_hp_fraction=np.mean([r['combat']['hp']/r['combat']['max_hp'] for r in wins]).item() if wins else None,
        boss_hp=np.mean([r['boss_hp'] for r in rows if r.get('boss_hp') is not None]).item()
            if any(r.get('boss_hp') is not None for r in rows) else None,
        inference_seconds=sum(r.get('inference_seconds',r.get('timings', {}).get('policy_seconds', 0.)) for r in rows)/max(1, decisions),
        evaluation_seconds=report['seconds'])


def paired_interval(matrix, *, confidence=.95, seed=20261012, repetitions=10000):
    """Crossed resampling of learner seeds and source fights, preserving pairs.

    The matrix already averages repeats/continuations within a source fight.
    There are only three learner seeds: this exploratory interval is necessarily
    a coarse estimate of between-initialization uncertainty.
    """
    matrix = np.asarray(matrix, dtype=np.float64)
    if matrix.ndim != 2 or not matrix.size or not np.isfinite(matrix).all():
        raise ValueError('Expected a complete seed by source-fight outcome matrix')
    rng = np.random.default_rng(seed)
    seeds = rng.integers(matrix.shape[0], size=(repetitions, matrix.shape[0], 1))
    fights = rng.integers(matrix.shape[1], size=(repetitions, 1, matrix.shape[1]))
    values = matrix[seeds, fights].mean((1, 2))
    alpha = (1-confidence)/2
    return dict(mean=float(matrix.mean()), interval=np.quantile(values, [alpha, 1-alpha]).tolist(),
                confidence=confidence, seeds=matrix.shape[0], fights=matrix.shape[1],
                per_seed=matrix.mean(1).tolist(), bootstrap_repetitions=repetitions)


def outcomes(report, *, policy=None, mode=None, measure='win'):
    grouped = defaultdict(list)
    for row in report['episodes']:
        if policy is not None and row['policy'] != policy or mode is not None and row['mode'] != mode:
            continue
        fight = row['combat_id']
        # Preserve native fight identity, not the campaign source_group or UUID.
        value = float((row.get('combat') or {}).get('outcome') == 'victory') if measure == 'win' else row.get(measure)
        if value is not None:
            grouped[fight].append(value)
    return {k: float(np.mean(v)) for k, v in grouped.items()}


def compare(a, b, *, confidence=.95):
    seeds = sorted(a)
    if seeds != sorted(b) or not seeds:
        raise ValueError('Paired configurations need the same learner seeds')
    fights = sorted(a[seeds[0]])
    if any(sorted(a[s]) != fights or sorted(b[s]) != fights for s in seeds):
        raise ValueError('Paired configurations need exactly the same source fights')
    return paired_interval([[a[s][fight]-b[s][fight] for fight in fights] for s in seeds], confidence=confidence)


def common_outcome_health(a, b):
    """Condition on the same result within paired seed/fight/mode/repetition."""
    seeds=sorted(a)
    if seeds != sorted(b):
        raise ValueError('Health comparisons require paired learner seeds')
    pairs={}
    fights=set()
    for seed in seeds:
        def keyed(report):
            return {(r['combat_id'],r['mode'],r['repeat']):r for r in report['episodes']}
        left,right=keyed(a[seed]),keyed(b[seed])
        if set(left)!=set(right):
            raise ValueError('Health comparisons require identical fights and repeats')
        pairs[seed]=(left,right);fights.update(k[0] for k in left)
    fights=sorted(fights)
    result={}
    for measure in ('winning_player_hp','winning_player_hp_fraction','common_failure_boss_hp'):
        matrix=np.full((len(seeds),len(fights)),np.nan)
        repetitions=0
        for i,seed in enumerate(seeds):
            left,right=pairs[seed]
            values=defaultdict(list)
            for key,x in left.items():
                y=right[key]
                xo,yo=(x.get('combat') or {}).get('outcome'),(y.get('combat') or {}).get('outcome')
                if measure.startswith('winning'):
                    if xo!=yo or xo!='victory':continue
                    xv,yv=x['combat']['hp'],y['combat']['hp']
                    if measure.endswith('fraction'):
                        xv/=x['combat']['max_hp'];yv/=y['combat']['max_hp']
                else:
                    if xo!=yo or xo=='victory' or x['status']!=y['status']:continue
                    xv,yv=x.get('boss_hp'),y.get('boss_hp')
                    if xv is None or yv is None:continue
                values[key[0]].append(xv-yv);repetitions+=1
            for j,fight in enumerate(fights):
                if fight in values:matrix[i,j]=np.mean(values[fight])
        support=np.isfinite(matrix)
        row=dict(paired_repetitions=repetitions, seed_fight_pairs=int(support.sum()),
            source_fights=int(support.any(0).sum()), per_seed_support=support.sum(1).tolist(),
            mean=float(matrix[support].mean()) if support.any() else None, interval=None)
        if support.any():
            rng=np.random.default_rng(20261012)
            selected=matrix[rng.integers(len(seeds),size=(10000,len(seeds),1)),
                            rng.integers(len(fights),size=(10000,1,len(fights)))]
            counts=np.isfinite(selected).sum((1,2));usable=counts>0
            draws=np.nansum(selected,axis=(1,2))[usable]/counts[usable]
            row.update(interval=np.quantile(draws,[.025,.975]).tolist(),confidence=.95,
                bootstrap_draws_with_support=int(usable.sum()),
                interpretation='Conditional descriptive comparison; positive means more HP for A. Repeats averaged within fight.')
        result[measure]=row
    return result


def _training(learner):
    reports = [_read(Path(p)) for p in learner['reports']]
    totals = {k: sum(r['summary'][k] for r in reports) for k in (
        'accepted_decisions', 'trained_decisions', 'skipped_decisions', 'skipped_updates', 'wins', 'episode_attempts')}
    iterations = [i for r in reports for i in r['iterations']]
    for key in ('optimizer_unique_decisions', 'optimizer_decision_visits', 'kl_unvisited_decisions'):
        updates = [i['update'] for i in iterations if 'update' in i]
        totals[key] = sum(i[key] for i in updates) if all(key in i for i in updates) else None
    elapsed = sum(r['total_seconds'] for r in reports)
    first_reward, before = None, 0
    for iteration in iterations:
        within = 0
        for row in iteration['collection']['episodes']:
            within += row['steps']
            if row['task_return'] > 0 and first_reward is None:
                first_reward = before+within
        before += iteration['collection']['steps']
    totals.update(seconds=elapsed, decisions_per_second=totals['accepted_decisions']/elapsed,
        collection_seconds=sum(i['collection']['seconds'] for i in iterations),
        update_seconds=sum(i.get('update',{}).get('seconds',0) for i in iterations),
        first_reward_decision=first_reward, first_reward_clock='deterministic collected episode order; not worker wall order',
        peak_parent_rss_bytes=max(r['peak_process_rss_bytes'] for r in reports),
        iterations=[dict(iteration=i['iteration'], decisions=i['collection']['steps'],
            collection=i['collection'].get('timings'), update=i.get('update')) for i in iterations])
    return totals


def _coverage(report, learner):
    names = [name for _, name in channels(learner['configuration']['architecture']['features']['richness'])]
    audit = report.get('feature_audits', {}).get(learner['configuration_id'])
    if not audit or audit['minimum'] is None:
        return dict(status='unavailable')
    return dict(decisions=audit['decisions'], entity_rows=audit['entity_rows'],
        constant_channels=[name for name, lo, hi in zip(names, audit['minimum'], audit['maximum']) if lo == hi],
        missing_counter_rates={key: value/max(1, audit['decisions']) for key, value in audit['missing_counter_decisions'].items()},
        unknown_numeric_rates=audit.get('unknown_numeric_rates', {}),
        missing_enemy_history_rate=audit.get('missing_enemy_history_rate'),
        interpretation='Constant and unavailable features cannot support a feature-importance conclusion.')


def slices(report):
    buckets = defaultdict(list)
    for row in report['episodes']:
        values = row.get('slice', {})
        if not values:
            continue
        deck = values['deck_size']
        exposure = row.get('content_exposure')
        labels = ('hp/'+values['hp_band'], 'deck/'+('small' if deck <= 20 else 'medium' if deck <= 30 else 'large'),
                  'potions/'+('available' if values['potions'] else 'none'))
        if exposure:
            labels += ('content/'+('all_seen' if exposure['known']==exposure['total'] else 'contains_unseen'),)
        for label in labels:
            buckets[label].append(row)
    return {label: dict(fights=len({r['combat_id'] for r in rows}),
                        win_rate=float(np.mean([(r.get('combat') or {}).get('outcome')=='victory' for r in rows])))
            for label, rows in buckets.items()}


def inspector_examples(output, learners):
    """Publish a fixed DEV case at initialization and endpoint for each finalist.

    The first case and first registered seed are chosen without inspecting their
    outcomes. Copies contain public trajectories and verified public supplements.
    """
    selection_path=output/'selection.json'
    if not selection_path.exists():
        return None
    destination=output/'decision-inspector'
    binding_path=output/'inspector-examples.json'
    if binding_path.exists():
        binding=_read(binding_path)
        if binding['selection_sha256']!=_sha_file(selection_path) or not (destination/'report.json').is_file():
            raise ValueError('Decision-inspector example binding changed or is incomplete')
        return binding
    from game.agent.analysis.report import build_report as build_inspector
    from .recording import SUFFIX,read_history
    from game.agent.analysis.sources import discover,identity,public_path
    from game.agent.recording import COMPRESSED_SUFFIX,load_trajectory
    from game.agent.trace_storage import logical_path
    sources=output/'inspector-public-sources'
    sources.mkdir(exist_ok=True)
    chosen,rows=[],[]
    for name in _read(selection_path)['winners'].values():
        learner=min((r for r in learners if r['configuration_id']==name),key=lambda r:r['seed'])
        for step in ('0','100000'):
            path=Path(learner['evaluations'][step]);evaluation=_read(path)
            row=min(evaluation['episodes'],key=lambda r:r['case_id'])
            episode=identity(row['episode_id'])
            if row['trajectory']!=episode+COMPRESSED_SUFFIX:
                raise ValueError('Inspector requires the canonical public trajectory basename')
            originals=(path.parent/(episode+COMPRESSED_SUFFIX),path.parent/(episode+SUFFIX))
            discovered=set(discover([path.parent]))
            if (any(not public_path(p) for p in originals)
                    or logical_path(originals[0]) not in discovered or originals[1] not in discovered):
                raise ValueError('Inspector examples must be independently discovered public siblings')
            trajectory=load_trajectory(originals[0])
            read_history(originals[1],trajectory,row['public_history_sha256'])
            for original in originals:
                copied=sources/original.name
                if copied.exists() and _sha_file(copied)!=_sha_file(original):
                    raise ValueError('Decision-inspector public example changed')
                copied.write_bytes(original.read_bytes())
            rows.append(row)
            chosen.append(dict(configuration_id=name,seed=learner['seed'],decisions=int(step),
                case_id=row['case_id'],episode_id=row['episode_id'],
                evaluation=str(path),evaluation_sha256=_sha_file(path),
                checkpoint=learner['checkpoint'] if step=='100000' else str(
                    Path(learner['checkpoint']).parents[2]/'initialization'/'initial.sts-model')))
    (sources/'evaluation.json').write_text(json.dumps(dict(schema='sts_feature_study_evaluation_v1',
        episodes=rows,source_evaluations=chosen),sort_keys=True)+'\n')
    result=build_inspector([sources],destination,title='Vantom · Frozen DEV examples')
    binding=dict(selection_sha256=_sha_file(selection_path),directory=str(destination),examples=chosen,
        seconds=result['build_seconds'],selection_rule='First DEV case ID and lowest learner seed; no outcome filtering.')
    binding_path.write_text(json.dumps(binding,sort_keys=True,indent=2)+'\n')
    return binding


def build_report(output):
    output = Path(output)
    manifest = _read(output/'manifest.json')
    learners = [_read(path) for path in sorted((output/'learners').glob('*/*/learner.json'))]
    results, configurations, curves, wins, sampled = {}, {}, {}, {}, {}
    greedy_reports,sampled_reports={},{}
    for learner in learners:
        name, seed = learner['configuration_id'], learner['seed']
        configurations[name] = learner['configuration']
        checkpoints = {int(step): _read(Path(path)) for step, path in learner['evaluations'].items() if step.isdigit()}
        endpoint = checkpoints[100000]
        sampled_report = _read(Path(learner['evaluations']['sampled']))
        train = metrics(_read(Path(learner['evaluations']['training'])))
        development = metrics(endpoint)
        row = dict(seed=seed, development=development, sampled=metrics(sampled_report), training=train,
            improvement_from_initialization=development['win_rate']-metrics(checkpoints[0])['win_rate'],
            train_development_gap=train['win_rate']-development['win_rate'],
            learning=_training(learner), coverage=_coverage(endpoint, learner),
            slices=slices(endpoint),
            checkpoint=learner['checkpoint'], checkpoint_sha256=learner['checkpoint_sha256'])
        results.setdefault(name, []).append(row)
        wins.setdefault(name, {})[seed] = outcomes(endpoint)
        sampled.setdefault(name, {})[seed] = outcomes(sampled_report)
        greedy_reports.setdefault(name,{})[seed]=endpoint
        sampled_reports.setdefault(name,{})[seed]=sampled_report
        curves.setdefault(name, {})[seed] = {step: metrics(report)['win_rate'] for step, report in checkpoints.items()}
    complete = {name for name, rows in results.items() if len(rows) == 3}
    comparisons = []
    def add(family, a, b):
        if a in complete and b in complete:
            comparisons.append(dict(family=family, a=a, b=b,
                greedy=compare(wins[a], wins[b]), sampled=compare(sampled[a], sampled[b]),
                common_greedy_health=common_outcome_health(greedy_reports[a],greedy_reports[b]),
                common_sampled_health=common_outcome_health(sampled_reports[a],sampled_reports[b])))
    from .spec import ARCHITECTURES, RICHNESS
    for architecture in ARCHITECTURES:
        for richness in RICHNESS:
            add('identities', f'{architecture}-ids-{richness}', f'{architecture}-mechanical-{richness}')
        for identity in ('ids', 'mechanical'):
            for less, more in itertools.combinations(RICHNESS, 2):
                add('richness', f'{architecture}-{identity}-{more}', f'{architecture}-{identity}-{less}')
    for identity in ('ids', 'mechanical'):
        for richness in RICHNESS:
            for a, b in itertools.combinations(ARCHITECTURES, 2):
                add('architectures', f'{a}-{identity}-{richness}', f'{b}-{identity}-{richness}')
    followup_path = output/'followups.json'
    followups = _read(followup_path) if followup_path.exists() else None
    if followups:
        for name in followups['configurations']:
            add('feature_removal', followups['parent'], name)
    interactions = []
    for architecture in ARCHITECTURES:
        keys = [f'{architecture}-{identity}-{richness}' for identity, richness in
                (('ids', 'context'), ('mechanical', 'context'), ('ids', 'basic'), ('mechanical', 'basic'))]
        if all(k in complete for k in keys):
            a,b,c,d = (wins[k] for k in keys)
            diff1 = {s: {f:a[s][f]-b[s][f] for f in a[s]} for s in a}
            diff2 = {s: {f:c[s][f]-d[s][f] for f in c[s]} for s in c}
            interactions.append(dict(architecture=architecture, identity_by_context=compare(diff1, diff2)))
    test, confirmatory, test_results = None, [], {}
    if (output/'test'/'evaluation.json').exists():
        test = _read(output/'test'/'evaluation.json')
        matrix = {}
        for kind in ('identity', 'no_vocabulary'):
            matrix[kind] = {seed: outcomes(test, policy=f'{kind}-{seed}', mode='greedy')
                            for seed in manifest['configuration']['seeds']}
        control = outcomes(test, policy='heuristic', mode='greedy')
        matrix['heuristic'] = {s: control for s in manifest['configuration']['seeds']}
        for a,b in (('identity','no_vocabulary'), ('identity','heuristic'), ('no_vocabulary','heuristic')):
            confirmatory.append(dict(a=a,b=b,greedy=compare(matrix[a],matrix[b],confidence=1-.05/3),
                adjustment='Bonferroni family of three pre-registered paired greedy comparisons'))
        for policy in sorted({r['policy'] for r in test['episodes']}):
            test_results[policy]={}
            for mode in ('greedy','sampled'):
                subset=dict(test,episodes=[r for r in test['episodes'] if r['policy']==policy and r['mode']==mode])
                test_results[policy][mode]=dict(metrics=metrics(subset),slices=slices(subset),
                    source_fights=len(outcomes(subset)))
    total_decisions = sum(row['learning']['accepted_decisions'] for rows in results.values() for row in rows)
    report = dict(schema='sts_feature_study_report_v1', manifest_sha256=_sha_file(output/'manifest.json'),
        status='complete' if len(learners)==96 and test and test['status']=='complete' else 'in_progress',
        learners_completed=len(learners), collected_decisions=total_decisions, results=results,
        configurations=configurations,
        exploratory_comparisons=comparisons, interactions=interactions, confirmatory=confirmatory,
        test_results=test_results, inspector=inspector_examples(output,learners),
        limitations=[
            'Vantom only, random initialization and 100k collected decisions per learner.',
            'Three learner seeds; paired bootstrap uncertainty is coarse. Screening comparisons are exploratory.',
            'Sampled repetitions are averaged within source fight; they are not independent fights.',
            'Displayed pressure is not a prediction of actual future HP loss.',
            'Unknown mechanics and incomplete public history qualify feature-removal conclusions.',
            'Card, power and item removals also remove reconstructed turn counters to avoid leaking excluded mechanics through completeness flags; these are coupled interventions.',
            'Matched parameter counts do not imply matched computation or hidden widths.',
            'Peak RSS measures the parent process, not total collector memory; evaluation timings include instrumentation.',
            'The random-legal control samples in all three registered modes; the heuristic is deterministic.'],
        timings=dict(training_seconds=sum(row['learning']['seconds'] for rows in results.values() for row in rows),
            learner_evaluation_seconds=sum(sum(_read(Path(p))['seconds'] for p in l['evaluations'].values()) for l in learners),
            test_evaluation_seconds=test['seconds'] if test else 0.,
            evaluation_seconds=sum(sum(_read(Path(p))['seconds'] for p in l['evaluations'].values()) for l in learners)
                               +(test['seconds'] if test else 0.)))
    # Reports are derived and replaceable; canonical inputs/checkpoints are not.
    destination = output/'report'
    destination.mkdir(exist_ok=True)
    (destination/'comparisons.json').write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n')
    _plots(destination, results, curves, comparisons)
    ranking = sorted(complete, key=lambda n: (-np.mean([r['development']['win_rate'] for r in results[n]]), n))
    lines = ['# Vantom feature and architecture study', '',
        f'{len(learners)}/96 learners complete; {total_decisions:,}/9,600,000 collected decisions.', '',
        '| Configuration | DEV greedy | Sampled | Change from initialization |', '| --- | ---: | ---: | ---: |']
    for name in ranking:
        rows = results[name]
        lines.append(f'| {name} | {np.mean([r["development"]["win_rate"] for r in rows]):.1%} | '
            f'{np.mean([r["sampled"]["win_rate"] for r in rows]):.1%} | '
            f'{np.mean([r["improvement_from_initialization"] for r in rows]):+.1%} |')
    lines += ['', 'Selection uses the frozen endpoint tie-breaks in the manifest; this table is descriptive.', '']
    if ranking and all(np.mean([r['improvement_from_initialization'] for r in results[n]]) <= 0 for n in ranking):
        lines += ['No configuration improved its greedy mean over initialization. Architecture ranking is inconclusive under this reward and budget.', '']
    elif report['status'] != 'complete':
        lines += ['The study is incomplete. No final model recommendation or held-out claim is available.', '']
    else:
        selected = _read(output/'selection.json')['winners']
        lines += [f'The frozen development finalists are `{selected["identity"]}` and `{selected["no_vocabulary"]}`. '
                  'Use the registered test intervals in comparisons.json to assess whether either advantage is resolved; '
                  'do not tune or reselect after this confirmation.', '']
        from .run import endpoint_key
        by_name={name:[r for r in learners if r['configuration_id']==name] for name in selected.values()}
        preferred=min(by_name,key=lambda name:endpoint_key(name,by_name[name]))
        lines += [f'Pursue `{preferred}` as the development-selected model at this budget. '
            'This is a research candidate; the default model is unchanged.', '',
            '| Registered TEST comparison | Greedy difference | Family-adjusted interval |',
            '| --- | ---: | ---: |']
        for row in confirmatory:
            value=row['greedy'];lo,hi=value['interval']
            lines.append(f'| {row["a"]} − {row["b"]} | {value["mean"]:+.1%} | [{lo:+.1%}, {hi:+.1%}] |')
        if confirmatory and confirmatory[0]['greedy']['interval'][0] <= 0 <= confirmatory[0]['greedy']['interval'][1]:
            lines += ['', 'The registered test comparison does not resolve an advantage between the two finalists.']
        lines += ['', 'Feature evidence is exploratory and conditional on the selected rich no-vocabulary parent:', '']
        for row in comparisons:
            if row['family']!='feature_removal':continue
            lo,hi=row['greedy']['interval'];group=row['b'].split('-without-')[-1]
            conclusion=('positive evidence for retaining this group' if lo>0 else
                        'removal outperformed the parent' if hi<0 else 'effect unresolved')
            lines.append(f'- `{group}`: parent minus removal {row["greedy"]["mean"]:+.1%} '
                         f'[{lo:+.1%}, {hi:+.1%}]; {conclusion}.')
        lines.append('')
    lines.extend('- '+line for line in report['limitations'])
    (destination/'README.md').write_text('\n'.join(lines)+'\n')
    _track(output, report, curves)
    return report


def _plots(output, results, curves, comparisons):
    if not results:
        return
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), sharex=True, sharey=True, layout='constrained')
    from .spec import ARCHITECTURES
    for ax, kind in zip(axes.flat, ARCHITECTURES):
        for name, seeds in curves.items():
            if name.startswith(kind+'-') and '-without-' not in name:
                steps = sorted(next(iter(seeds.values())))
                values = np.array([[row[s] for s in steps] for row in seeds.values()])
                mean = values.mean(0)
                ax.plot(steps, mean, label=name[len(kind)+1:])
                ax.fill_between(steps, values.min(0), values.max(0), alpha=.1)
        ax.set(title=kind, xlabel='Collected training decisions', ylabel='DEV greedy win rate', ylim=(0,1))
        if ax.lines:
            ax.legend(fontsize=8)
    fig.savefig(output/'learning-curves.png', dpi=160)
    plt.close(fig)
    ablations = [c for c in comparisons if c['family']=='feature_removal']
    if ablations:
        fig, ax = plt.subplots(figsize=(10, 5), layout='constrained')
        y = np.arange(len(ablations))
        means = np.array([c['greedy']['mean'] for c in ablations])
        bounds = np.array([c['greedy']['interval'] for c in ablations])
        ax.errorbar(means, y, xerr=np.stack((means-bounds[:,0],bounds[:,1]-means)), fmt='o')
        ax.set(yticks=y, yticklabels=[c['b'].split('-without-')[-1] for c in ablations],
               xlabel='Parent minus ablated DEV win rate (paired 95% bootstrap)')
        ax.axvline(0, color='grey', linestyle='--')
        fig.savefig(output/'feature-ablations.png',dpi=160)
        plt.close(fig)


def _track(output, report, curves):
    from game.agent.tracking.store import TrackingStore
    with TrackingStore(output/'mlflow', experiment='Vantom feature study') as store:
        for name, rows in report['results'].items():
            for row in rows:
                seed = row['seed']
                run = store._run(digest([report['manifest_sha256'],name,seed]), f'{name} / {seed}',
                    {'sts.kind':'feature_study','sts.configuration':name,'sts.seed':seed})
                configuration=report['configurations'][name]
                architecture=configuration['architecture']
                store._params(run,dict(architecture=architecture['kind'],hidden_size=architecture['hidden_size'],
                    identities=architecture['features']['identities'],richness=architecture['features']['richness'],
                    removals=','.join(architecture['features']['ablations']),seed=seed,
                    parameters=configuration['parameters'],collected_budget=100000))
                if 'recipe' in configuration:
                    store._params(run,dict(recipe=configuration['recipe'],model_id=configuration['model_id'],
                        **{k:configuration['ppo']['ppo'][k] for k in
                           ('learning_rate','batch_size','entropy_weight','kl_check')}))
                for step, value in curves[name][seed].items():
                    store._metrics(run,step,{'development/greedy_win_rate':value})
                store._metrics(run,100000,dict(endpoint=row['development'],sampled=row['sampled'],
                    training=row['training'],improvement=row['improvement_from_initialization'],
                    generalization_gap=row['train_development_gap']))
                if 'recipe' in configuration:
                    store._metrics(run,100000,dict(optimizer={k:row['learning'][k] for k in
                        ('optimizer_unique_decisions','optimizer_decision_visits','kl_unvisited_decisions')}))
                step = 0
                for iteration in row['learning']['iterations']:
                    update = iteration.get('update') or {}
                    step += iteration['decisions']
                    store._metrics(run,step,{'ppo':update.get('mean_update',{})})
                store.client.set_terminated(run)
        parent = store._run(report['manifest_sha256'], 'Vantom study comparison', {'sts.kind':'feature_study_comparison'})
        for path in (output/'report').iterdir():
            if path.suffix in ('.json','.md','.png'):
                store.client.log_artifact(parent, str(path))
        if report['status']=='complete':
            store.client.set_terminated(parent)
