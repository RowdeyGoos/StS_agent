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


def paired(rows, baseline):
    left, right = {r['case_id']:r for r in rows}, {r['case_id']:r for r in baseline}
    if len(left)!=len(rows) or len(right)!=len(baseline) or set(left)!=set(right):
        raise ValueError('Paired comparison requires the same unique planned cases')
    if any(left[k]['source_group']!=right[k]['source_group'] for k in left):
        raise ValueError('Paired source groups disagree')
    gain=sum(won(left[k]) and not won(right[k]) for k in left)
    loss=sum(won(right[k]) and not won(left[k]) for k in left)
    delta=(gain-loss)/len(rows)
    return {'cases':len(rows), 'wins_only_candidate':gain, 'wins_only_heuristic':loss,
            'win_rate_difference':delta, 'difference_group_hoeffding_95':interval(delta, rows, paired=True)}


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
