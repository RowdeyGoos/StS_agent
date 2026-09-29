"""Paired genuine-start campaigns with a published plan before the first action."""
from dataclasses import asdict
import json
from pathlib import Path
import time
import uuid

from game.agent.provenance import implementation
from game.agent.runner import RunCancelled, RunConfig, prepare_directories, run_episode
from .checkpoint import load_policy, publish, runtime
from .comparison import interval
from .config import RUN_SCENARIO_SET
from .rewards import RewardSpec
from .run_demonstrations import describe
from .run_task import campaign_seed


def _won(row, goal='full_run'):
    return row['status']=='terminated' and (row.get('act1_cleared') is True if goal == 'act1' else
                                          row.get('outcome',{}).get('kind')=='victory')


def compare(values, baseline, *, goal, baseline_name='heuristic'):
    base = {r['case_id']:r for r in baseline}
    if (not values or len(base)!=len(baseline) or len(base)!=len(values) or
            {r['case_id'] for r in values} != set(base)):
        raise ValueError('Campaign comparison requires identical unique paired cases')
    if any(r['source_group'] != base[r['case_id']]['source_group'] for r in values):
        raise ValueError('Paired run source groups differ')
    gain = sum(_won(r, goal) and not _won(base[r['case_id']], goal) for r in values)
    loss = sum(not _won(r, goal) and _won(base[r['case_id']], goal) for r in values)
    delta = (gain-loss)/len(values)
    bounds = interval(delta, values, paired=True)
    complete = all(r['status'] in ('terminated','truncated') for r in (*values,*baseline))
    metric = 'act1_clears' if goal=='act1' else 'wins'
    return {'cases':len(values), metric+'_only_candidate':gain, metric+'_only_'+baseline_name:loss,
        ('act1_clear_rate_difference' if goal=='act1' else 'win_rate_difference'):delta,
        'difference_group_hoeffding_95':bounds,
        'conclusion':'incomplete' if not complete else 'improved' if bounds[0]>0 else 'worse' if bounds[1]<0 else 'inconclusive'}


def summarize(rows, *, goal='full_run'):
    if goal not in ('act1', 'full_run'):
        raise ValueError('Unsupported evaluation goal')
    result, paired = {}, {}
    names = tuple(dict.fromkeys(r['policy'] for r in rows))
    if set(names) not in ({'heuristic','hybrid','learned'}, {'heuristic','reference','learned'}):
        raise ValueError('Expected heuristic, learned and hybrid/reference policies')
    by_policy = {name:[r for r in rows if r['policy']==name] for name in names}
    for name, values in by_policy.items():
        if not values:
            raise ValueError('Missing planned policy rows')
        wins = sum(_won(r, goal) for r in values)
        seconds = sum(r.get('timings',{}).get('total_seconds',0.) for r in values)
        steps = sum(r.get('steps',0) for r in values)
        rate = wins/len(values)
        result[name] = {'planned':len(values), 'attempted':sum(r['status']!='unattempted' for r in values),
            'defeats':sum(r.get('outcome',{}).get('kind')=='defeat' for r in values),
            'abandoned':sum(r.get('outcome',{}).get('kind')=='abandoned' for r in values),
            'cutoffs':sum(r['status']=='truncated' for r in values),
            'failures':sum(r['status'] in ('failed','interrupted') for r in values),
            'unattempted':sum(r['status']=='unattempted' for r in values),
            'steps':steps, 'total_seconds':seconds, 'decisions_per_second':steps/seconds if seconds else None,
            'policy_seconds':sum(r.get('timings',{}).get('policy_seconds',0.) for r in values)}
        result[name].update({'act1_clears':wins, 'act1_clear_rate':rate,
            'act1_clear_rate_group_hoeffding_95':interval(rate, values),
            'run_wins':sum(r.get('outcome',{}).get('kind')=='victory' for r in values)} if goal == 'act1' else
            {'wins':wins, 'win_rate':rate, 'win_rate_group_hoeffding_95':interval(rate, values)})
        if goal == 'act1':
            floors = [r['last_public_hud']['floor'] for r in values if r.get('last_public_hud')]
            result[name]['mean_last_observed_floor'] = sum(floors)/len(floors) if floors else None
        if name != 'heuristic':
            paired[name] = compare(values, by_policy['heuristic'], goal=goal)
    return result, paired


def evaluate_full_run(*, checkpoint, combat_checkpoint=None, reference_checkpoint=None, output_dir,
                      cases=8, split='test', start_index=0, max_decisions=1024,
                      time_limit_seconds=120., cancel=None, goal='full_run'):
    if split not in ('validation','test') or type(cases) is not int or not 1 <= cases <= 100:
        raise ValueError('Choose 1–100 held-out development/test campaigns')
    if goal not in ('act1','full_run') or (combat_checkpoint is None) == (reference_checkpoint is None):
        raise ValueError('Choose a campaign goal and exactly one combat/reference checkpoint')
    campaign_seed(split, start_index+cases-1)
    RunConfig(max_decisions=max_decisions, time_limit_seconds=time_limit_seconds).validate()
    if max_decisions > 4096 or time_limit_seconds > 300:
        raise ValueError('Evaluation limits are at most 4096 decisions/300 seconds per policy/case')
    learned = load_policy(checkpoint, task='full_run')
    combat = load_policy(combat_checkpoint, task='combat') if combat_checkpoint is not None else None
    reference = load_policy(reference_checkpoint, task='full_run') if reference_checkpoint is not None else None
    identity = implementation()
    other = 'hybrid' if combat is not None else 'reference'
    other_identity = 'hybrid_v1:'+combat.identity.split(':')[-1]+':'+identity.policy if combat is not None else reference.identity
    output = Path(output_dir).resolve()
    output, private = prepare_directories(output, output.with_name(output.name+'-private'))
    prefix = 'act1' if goal == 'act1' else 'full-run'
    path = output/(prefix+'.json')
    if path.exists() or (output/(prefix+'-plan.json')).exists():
        raise FileExistsError(output)
    rows, seeds = [], {}
    for index in range(cases):
        case = uuid.uuid4().hex
        seeds[case] = campaign_seed(split, start_index+index)
        for name in ('heuristic',other,'learned'):
            rows.append({'case_id':case, 'source_group':case, 'episode_id':uuid.uuid4().hex,
                'first_act':('overgrowth','underdocks')[index%2], 'policy':name, 'status':'unattempted'})
    report = {'schema':'sts_act1_evaluation_v1' if goal=='act1' else 'sts_full_run_evaluation_v1',
        'status':'running', 'split':split,
        'implementation':asdict(identity), 'runtime':runtime(), 'evidence':'headless_rollout',
        'start':'Genuine Ironclad A0 campaign; identical Gym-derived engine seed per policy/case; all-seen/unlocked profile.',
        'policies':{'heuristic':identity.policy, other:other_identity, 'learned':learned.identity},
        'reward_spec':(RewardSpec.with_act_rewards({'run_victory':0.,'act_cleared':1.},goal='act1')
                       if goal=='act1' else RewardSpec.full_run()).to_dict(),
        'training_reward_spec':learned.reward_spec.to_dict(),
        'limits':{'max_decisions':max_decisions, 'time_limit_seconds':time_limit_seconds}, 'episodes':rows}
    publish(private/'cases.json', json.dumps(seeds,sort_keys=True).encode(), private=True)
    if goal == 'act1':
        report.update(goal=goal, primary_metric='act1_clear_rate')
    report['plan_sha256'] = publish(output/(prefix+'-plan.json'), json.dumps(report,sort_keys=True).encode())
    before = time.perf_counter()
    report['status'] = 'complete'
    for row in rows:
        try:
            config = RunConfig(seed=seeds[row['case_id']], first_act=row['first_act'], split=split,
                scenario=RUN_SCENARIO_SET+':'+row['first_act'], max_decisions=max_decisions,
                time_limit_seconds=time_limit_seconds, goal=goal)
            kwargs = ({'policy':learned, 'policy_identity':learned.identity} if row['policy']=='learned' else
                      {'combat_policy':combat, 'policy_identity':other_identity} if row['policy']=='hybrid' else
                      {'policy':reference, 'policy_identity':reference.identity} if row['policy']=='reference' else {})
            result = run_episode(config, output_dir=output, audit_dir=private,
                episode_id=row['episode_id'], cancel=cancel, **kwargs)
            row.update(describe(result, split=split, goal=goal))
        except (Exception, KeyboardInterrupt) as error:
            row.update(status='interrupted' if isinstance(error,(RunCancelled,KeyboardInterrupt)) else 'failed',
                       failure=getattr(error,'reason',type(error).__name__))
            report['status'] = 'interrupted' if row['status']=='interrupted' else 'failed'
            break
    report['total_seconds'] = time.perf_counter()-before
    report['summary'], report['paired_vs_heuristic'] = summarize(rows, goal=goal)
    if reference is not None:
        report['paired_vs_reference'] = compare([r for r in rows if r['policy']=='learned'],
            [r for r in rows if r['policy']=='reference'], goal=goal, baseline_name='reference')
    publish(path, (json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n').encode())
    return path, report
