"""Planned-case denominators and conservative uncertainty over source groups."""
from collections import Counter
import math


def won(row):
    return row['status']=='terminated' and (row.get('combat') or {}).get('outcome')=='victory'


def interval(mean, rows, *, paired=False, alpha=.05):
    """Hoeffding bound for independent source groups, arbitrary within-group dependence.

    Each group's contribution spans its size/N (win rate), or twice that
    (paired win difference). Case weights and group membership are fixed before
    evaluation. Bounds refer only to the declared start-generating population.
    """
    if not rows or not 0 < alpha < 1:
        raise ValueError('Expected planned cases and a confidence level')
    sizes = Counter(r['source_group'] for r in rows)
    width = (2 if paired else 1)*math.sqrt(math.log(2/alpha)*sum(n*n for n in sizes.values())/2)/len(rows)
    return [max(-1 if paired else 0, mean-width), min(1, mean+width)]


def summary(rows):
    if not rows:
        raise ValueError('Cannot summarize an empty population')
    wins = [r for r in rows if won(r)]
    observed = [r for r in rows if r.get('start_hp') is not None and r.get('end_hp') is not None]
    rate = len(wins)/len(rows)
    return {'planned':len(rows), 'attempted':sum(r['status']!='unattempted' for r in rows),
        'wins':len(wins), 'losses':sum(r['status']=='terminated' and
            (r.get('combat') or {}).get('outcome')=='defeat' for r in rows),
        'cutoffs':sum(r['status']=='truncated' for r in rows),
        'failures':sum(r['status'] in ('failed','interrupted') for r in rows),
        'unattempted':sum(r['status']=='unattempted' for r in rows),
        'win_rate':rate, 'win_rate_group_hoeffding_95':interval(rate, rows),
        'source_groups':len({r['source_group'] for r in rows}),
        'mean_hp_on_win':sum(r['combat']['hp'] for r in wins)/len(wins) if wins else None,
        'mean_hp_fraction_on_win':sum(r['combat']['hp']/r['combat']['max_hp'] for r in wins)/len(wins) if wins else None,
        'mean_hp_change_observed':sum(r['end_hp']-r['start_hp'] for r in observed)/len(observed) if observed else None,
        'hp_change_observations':len(observed),
        'potion_use_actions':sum(r.get('potion_use_actions',0) for r in rows),
        'mean_final_turn_observed':sum(r['combat']['turn'] for r in rows if r.get('combat'))/
            sum(bool(r.get('combat')) for r in rows) if any(r.get('combat') for r in rows) else None,
        'steps':sum(r.get('steps',0) for r in rows),
        'mean_task_return':sum(r.get('task_return',0.) for r in rows)/len(rows)}


def paired(rows, baseline, *, baseline_name='heuristic'):
    left, right = {r['case_id']:r for r in rows}, {r['case_id']:r for r in baseline}
    if len(left)!=len(rows) or len(right)!=len(baseline) or set(left)!=set(right):
        raise ValueError('Paired comparison requires the same unique planned cases')
    if any(left[k]['source_group']!=right[k]['source_group'] for k in left):
        raise ValueError('Paired source groups disagree')
    gain=sum(won(left[k]) and not won(right[k]) for k in left)
    loss=sum(won(right[k]) and not won(left[k]) for k in left)
    delta=(gain-loss)/len(rows)
    return {'cases':len(rows), 'wins_only_candidate':gain, 'wins_only_'+baseline_name:loss,
            'win_rate_difference':delta, 'difference_group_hoeffding_95':interval(delta, rows, paired=True)}


BALANCED_DRAWS = 2000
BALANCED_SEED = 20261017


def balanced(rows, names, *, kinds=('elite', 'boss'), draws=BALANCED_DRAWS, seed=BALANCED_SEED):
    """Equal-encounter win rates within room kinds, with source-campaign bootstrap intervals.

    Every encounter present in the planned population has equal weight, so a
    frequent elite cannot dominate a rare one. Each draw resamples whole source
    campaigns for all policies at once, so paired differences keep their
    correlation. Failed, cut-off and unattempted fights count as non-wins.
    """
    import numpy as np
    groups = sorted({r['source_group'] for r in rows})
    result = {'method': 'Mean of per-encounter win rates within each room kind; 95% percentile '
                        'intervals from source-campaign bootstrap resamples shared by all policies.',
              'draws': draws, 'seed': seed}
    if not groups:
        return result
    column = {g: i for i, g in enumerate(groups)}
    counts = np.random.default_rng(seed).multinomial(len(groups), np.full(len(groups), 1/len(groups)), size=draws)

    def bounds(values):
        values = values[np.isfinite(values)]
        return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))] if len(values) else None

    for kind in kinds:
        cases = {r['case_id']: r for r in rows if r['room_kind'] == kind}
        if not cases:
            continue
        encounters = sorted({r['encounter'] for r in cases.values()})
        index = {e: j for j, e in enumerate(encounters)}
        planned = np.zeros((len(groups), len(encounters)))
        for r in cases.values():
            planned[column[r['source_group']], index[r['encounter']]] += 1
        wins = {name: np.zeros_like(planned) for name in names}
        for r in rows:
            if r['room_kind'] == kind and r['policy'] in wins and won(r):
                wins[r['policy']][column[r['source_group']], index[r['encounter']]] += 1
        fights, resampled = planned.sum(0), counts @ planned
        present = resampled > 0
        estimate = {name: float(np.mean(w.sum(0)/fights)) for name, w in wins.items()}
        draws_by_policy = {}
        with np.errstate(invalid='ignore', divide='ignore'):
            for name, w in wins.items():
                # An encounter absent from one resample leaves that draw's mean
                # over the encounters it does contain; an empty draw is undefined.
                rates = np.where(present, (counts @ w)/np.where(present, resampled, 1), 0.)
                draws_by_policy[name] = np.where(present.any(1), rates.sum(1)/present.sum(1), np.nan)
        result[kind] = {
            'encounters': {e: {'fights': int(fights[j]), 'win_rate': {name: float(w[:, j].sum()/fights[j])
                               for name, w in wins.items()}} for j, e in enumerate(encounters)},
            'win_rate': {name: {'estimate': estimate[name], 'interval_95': bounds(draws_by_policy[name])}
                         for name in names},
            'paired': {a: {b: {'difference': estimate[a]-estimate[b],
                               'interval_95': bounds(draws_by_policy[a]-draws_by_policy[b])}
                           for b in names if b != a} for a in names}}
    return result


def summarize(rows, names):
    by_policy={name:[r for r in rows if r['policy']==name] for name in names}
    if any(not values for values in by_policy.values()):
        raise ValueError('Missing planned policy rows')
    return {'summary':{name:summary(values) for name,values in by_policy.items()},
        'paired_vs_heuristic':{name:paired(values,by_policy['heuristic']) for name,values in by_policy.items()
                               if name!='heuristic'}}


def choose(report):
    """Development-only choice. More wins, fewer cutoffs, then HP, then name."""
    if report['split']!='validation' or report['status']!='complete' or any(
            r['status'] not in ('terminated','truncated') for r in report['episodes']):
        raise ValueError('Selection requires complete development evaluation')
    names=[name for name,p in report['policies'].items() if p['algorithm']=='ppo']
    if len(names)<3:
        raise ValueError('Evaluate at least three PPO learner runs before selection')
    return min(names,key=lambda name:(-report['summary'][name]['wins'],
        report['summary'][name]['cutoffs'], -(report['summary'][name]['mean_hp_fraction_on_win'] or 0.), name))


def conclusion(report, name):
    if report['split']!='test' or report['status']!='complete':
        return 'incomplete'
    low, high = report['paired_vs_heuristic'][name]['difference_group_hoeffding_95']
    return 'improved' if low>0 else 'worse' if high<0 else 'inconclusive'
