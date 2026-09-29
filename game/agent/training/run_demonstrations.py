"""Public-teacher campaigns and explicitly assisted coverage demonstrations."""
from collections import Counter, deque
from dataclasses import asdict
import json
from pathlib import Path
import time
import uuid

from game.agent.provenance import implementation
from game.agent.progress import cleared_act, completed_act
from game.agent.recording import load_trajectory
from game.agent.runner import RunCancelled, RunConfig, prepare_directories, run_episode
from .checkpoint import publish
from .config import RUN_SCENARIO_SET, TrainingConfig
from .rewards import strict_json
from .run_task import campaign_seed

SCHEMA = 'sts_full_run_demonstrations_v1'
FIXTURES = ('rewards', 'shop', 'rest', 'event', 'treasure', 'relic', 'assisted_campaign')


def fixture(name):
    """Authored inventory/room starts only; the teacher still sees public input.

    The assisted campaign has 10,000 HP and five upgraded Byrd Swoops. Its fights
    and ending execute normally, but its result is never a genuine-start win.
    """
    if name not in FIXTURES:
        raise ValueError('Unknown run demonstration fixture')
    def make(seed):
        from game.headless.run.engine import RunEngine
        from game.headless.run import rewards, shop, rest_site, events, treasure
        if name == 'assisted_campaign':
            from game.headless.run.ancient import PROFILE
            from game.headless.run.deck import add_card
            run = RunEngine.campaign(seed=seed, ancient_profile=PROFILE)
            run.state.hp = run.state.max_hp = 10000
            run.state.deck.clear()
            for _ in range(5):
                add_card(run.state, run.cards.definition('byrd_swoop'), upgrade_level=1)
        else:
            # Authored room continuation over a real owned map. A bare room
            # without a graph would have no legal decision after Leave/Proceed.
            run = RunEngine.campaign(seed=seed)
            run.state.hp, run.state.gold = 40, 1000
            if name == 'rewards':
                run.obtain_relic('white_beast_statue')
                rewards.begin_combat_rewards(run.state, run.cards, encounter_id='overgrowth_bygone_effigy', extra_cards=1)
            elif name == 'shop':
                shop.begin(run.state, run.cards)
            elif name == 'rest':
                rest_site.begin_rest_site(run.state)
            elif name == 'event':
                events.begin(run.state, 'aroma_of_chaos', cards=run.cards)
            elif name == 'treasure':
                treasure.begin(run.state)
            else:
                run.obtain_relic('dollys_mirror')
        run.state.validate()
        return run
    return make


def describe(result, *, split, goal='full_run'):
    if goal not in ('full_run', 'act1'):
        raise ValueError('Unsupported evaluation goal')
    trajectory = load_trajectory(result.trajectory, split=split)
    last = trajectory.transitions[-1] if trajectory.transitions else None
    decision = (last.successor if last and hasattr(last.successor, 'run')
                else last.observation if last else trajectory.initial)
    row = {'trajectory':Path(result.trajectory).name, 'trajectory_sha256':trajectory.sha256,
        'status':'truncated' if result.outcome.kind == 'truncated' else 'terminated',
        'outcome':asdict(result.outcome), 'steps':len(trajectory.transitions),
        'task_return':sum(t.reward for t in trajectory.transitions),
        'contexts':dict(Counter(t.observation.context.kind for t in trajectory.transitions)),
        'actions':dict(Counter(t.action.kind for t in trajectory.transitions)),
        'last_public_hud':{key:decision.run.get(key) for key in ('act','floor','hp','max_hp')} if hasattr(decision,'run') else None,
        'timings':asdict(result.timings)}
    if goal == 'act1':
        if (not hasattr(trajectory.initial, 'run') or trajectory.initial.run.get('act') != 1 or
                completed_act(trajectory.initial) is not None):
            raise ValueError('Act 1 evaluation requires an unfinished Act 1 start')
        clears = [act for t in trajectory.transitions if (act := cleared_act(t.observation, t.successor)) is not None]
        success = 1 in clears
        if success and (clears != [1] or completed_act(last.successor) != 1 or
                        result.outcome.kind != 'truncated' or result.outcome.reason != 'external_stop'):
            raise ValueError('Act 1 recording continued beyond its task boundary')
        row.update(goal=goal, act1_cleared=success, canonical_return=row['task_return'],
                   task_return=int(success), status='terminated' if success else row['status'])
    return row


def collect_run_demonstrations(*, output_dir, split='train', cases=4, start_index=0,
                              max_decisions=1024, time_limit_seconds=120., include_fixtures=False, cancel=None):
    if type(cases) is not int or not 1 <= cases <= 100 or type(include_fixtures) is not bool:
        raise ValueError('Choose 1–100 bounded demonstration campaigns')
    campaign_seed(split, start_index+cases-1)
    RunConfig(max_decisions=max_decisions, time_limit_seconds=time_limit_seconds).validate()
    if max_decisions > 4096 or time_limit_seconds > 300:
        raise ValueError('Demonstration limits are at most 4096 decisions/300 seconds')
    output = Path(output_dir).resolve()
    output, private = prepare_directories(output, output.with_name(output.name+'-private'))
    path = output/'run-demonstrations.json'
    if path.exists() or (output/'run-demonstrations-plan.json').exists():
        raise FileExistsError(output)
    names = [('overgrowth' if i < (cases+1)//2 else 'underdocks', i, 'headless_rollout') for i in range(cases)]
    if include_fixtures:
        names += [(name, cases+i, 'controlled_fixture') for i,name in enumerate(FIXTURES)]
    report = {'schema':SCHEMA, 'split':split, 'status':'running', 'teacher':implementation().policy,
        'training_config':TrainingConfig.full_run().to_dict(),
        'fixture_definition':'Authored rooms on a campaign map with 40 HP/1000 gold, capped at 32 decisions; assisted_campaign has 10000 HP and five upgraded Byrd Swoops; public teacher, no forced combat wins.',
        'limits':{'decisions':max_decisions, 'seconds':time_limit_seconds},
        'episodes':[{'episode_id':uuid.uuid4().hex, 'scenario':name, 'evidence':evidence, 'status':'unattempted'}
                    for name,_,evidence in names]}
    publish(output/'run-demonstrations-plan.json', json.dumps(report, sort_keys=True).encode())
    before = time.perf_counter()
    report['status'] = 'complete'
    for row, (name,index,evidence) in zip(report['episodes'], names):
        try:
            seed = campaign_seed(split, start_index+index)
            config = RunConfig(seed=seed, first_act=name if evidence == 'headless_rollout' else 'overgrowth',
                split=split, evidence=evidence, scenario=RUN_SCENARIO_SET+':'+name,
                max_decisions=min(max_decisions,32) if evidence=='controlled_fixture' and name!='assisted_campaign' else max_decisions,
                time_limit_seconds=time_limit_seconds)
            result = run_episode(config, output_dir=output, audit_dir=private, episode_id=row['episode_id'],
                engine_factory=fixture(name) if evidence == 'controlled_fixture' else None, cancel=cancel)
            row.update(describe(result, split=split))
        except (Exception, KeyboardInterrupt) as error:
            row.update(status='interrupted' if isinstance(error,(RunCancelled,KeyboardInterrupt)) else 'failed',
                       failure=getattr(error,'reason',type(error).__name__))
            report['status'] = 'cancelled' if row['status']=='interrupted' else 'failed'
            break
    report['total_seconds'] = time.perf_counter()-before
    report['unattempted_episodes'] = sum(r['status']=='unattempted' for r in report['episodes'])
    report['outcomes_by_evidence'] = {kind:dict(Counter(r.get('outcome',{}).get('kind',r['status'])
        for r in report['episodes'] if r['evidence']==kind)) for kind in ('headless_rollout','controlled_fixture')}
    publish(path, (json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n').encode())
    return path, report


class _LoadedRunPaths:
    """One-use handoff of manifest-validated, immutable trajectory snapshots."""

    def __init__(self, paths, episodes, split):
        self.paths, self.split = tuple(paths), split
        self._episodes = deque(episodes)

    def consume(self, split):
        if split != self.split:
            raise ValueError('Dataset split mismatch')
        if self._episodes is None:
            raise ValueError('Retained trajectories were already consumed')
        episodes, self._episodes = self._episodes, None
        return episodes


def corpus_paths(directory, *, split, retain=False):
    """Check the manifest, optionally retaining its snapshots for one preparation.

    Retained data is bound to the bytes just validated. Later file changes do
    not change that snapshot; ordinary path results are reread by the loader.
    """
    if type(retain) is not bool:
        raise ValueError('retain must be boolean')
    root = Path(directory).resolve()
    manifest = strict_json((root/'run-demonstrations.json').read_text())
    if (manifest['schema'] != SCHEMA or manifest['status'] != 'complete' or manifest['split'] != split or
            manifest['unattempted_episodes'] != 0 or
            TrainingConfig.from_dict(manifest['training_config']) != TrainingConfig.full_run()):
        raise ValueError('Incomplete or incompatible full-run demonstration corpus')
    paths, episodes = [], []
    for row in manifest['episodes']:
        name = row.get('trajectory')
        if (row['status'] not in ('terminated','truncated') or type(name) is not str or
                Path(name).name != name or (root/name).resolve().parent != root):
            raise ValueError('Expected a complete local demonstration entry')
        episode = load_trajectory(root/name, split=split)
        if (episode.sha256 != row['trajectory_sha256'] or episode.metadata.evidence != row['evidence'] or
                episode.metadata.scenario != RUN_SCENARIO_SET+':'+row['scenario']):
            raise ValueError('Run demonstration binding mismatch')
        paths.append(root/name)
        if retain:
            episodes.append(episode)
    return _LoadedRunPaths(paths, episodes, split) if retain else paths
