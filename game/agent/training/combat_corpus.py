"""Campaign-derived Act 1 combat starts; engine snapshots remain owner-only."""
from collections import Counter
from dataclasses import asdict, dataclass
from functools import cached_property, lru_cache
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
from random import Random
import re
import signal
import time
import uuid

from game.agent import contracts as c
from game.agent.action_policy import COMMIT_DECISIONS
from game.agent.contracts import full as f
from game.agent.full_policy import choose_action
from game.agent.headless.adapter import HeadlessAdapter
from game.agent.performance import GAME_WORKER_LIMIT
from game.agent.progress import completed_act
from game.agent.provenance import implementation
from game.agent.runner import RunCancelled, prepare_directories
from game.agent.workers import _cleanup, _defer_start_signals
from game.headless.encounters.catalog import ENCOUNTERS
from game.headless.run.engine import RunEngine
from game.headless.run.hidden import resample_hidden_combat
from game.headless.run.snapshots import restore_run
from .benchmark_suite import data, digest
from .config import TrainingConfig
from .ppo_config import FROZEN_HIDDEN_STATE, HIDDEN_STATES, RESAMPLED_HIDDEN_STATE
from .rewards import RewardSpec, strict_json
from .scenarios import episode_seed

SCHEMA = 'sts_act1_combat_corpus_v2'
SOURCE = 'act1_combat_corpus_v2'
REGIONS = ('overgrowth', 'underdocks')
SPLITS = ('train', 'validation', 'test')
ROOM_KINDS = ('combat', 'elite', 'boss')
STARTUP_SECONDS = 30.
CAMPAIGN_GRACE_SECONDS = 30.
DRAIN_SECONDS = 10.


@dataclass(frozen=True, slots=True)
class CorpusConfig:
    train_campaigns: int = 32
    validation_campaigns: int = 16
    test_campaigns: int = 16
    start_index: int = 1_000_000
    max_decisions: int = 1024
    time_limit_seconds: float = 120.
    route_policy: str = 'collector'
    capture_turns: int = 1
    record_planning: bool = False

    def __post_init__(self):
        episode_seed('train', self.start_index)
        for key in ('train_campaigns', 'validation_campaigns', 'test_campaigns'):
            if type(getattr(self, key)) is not int or not 1 <= getattr(self, key) <= 512:
                raise ValueError('Choose 1–512 source campaigns per region and split')
        episode_seed('test', self.start_index + 2 * max(self.train_campaigns,
                     self.validation_campaigns, self.test_campaigns))
        if type(self.max_decisions) is not int or not 1 <= self.max_decisions <= 4096:
            raise ValueError('Invalid source campaign decision limit')
        if (type(self.time_limit_seconds) not in (int, float) or
                not math.isfinite(self.time_limit_seconds) or not 0 < self.time_limit_seconds <= 300):
            raise ValueError('Invalid source campaign time limit')
        if self.route_policy not in ('collector', 'mixed_elites'):
            raise ValueError('Choose collector or mixed_elites routing')
        if type(self.capture_turns) is not int or not 1 <= self.capture_turns <= 12:
            raise ValueError('Capture 1–12 player-turn starts per combat')
        if type(self.record_planning) is not bool:
            raise ValueError('Invalid planning receipt setting')


def public_digest(decision):
    return digest(f.to_dict(decision))


def _freeze_start(run):
    # Engine maps may preserve visible power/effect order. Sorting their keys
    # is appropriate for report digests, but changes a continuation's public
    # graph. Bind the observation to the exact, order-preserving bytes saved.
    raw = json.dumps(run.snapshot(), ensure_ascii=False, allow_nan=False,
                     separators=(',', ':')).encode('utf-8')
    restored = restore_run(strict_json(raw))
    public = HeadlessAdapter(restored, decision_profile=f.PROFILE).observe().decision
    return raw, restored, public


def _describe(run, decision):
    encounter = run.state.active_encounter_id
    deck = next(n for n in decision.run.children if n.kind == 'deck')
    potions = [n.definition_id for root in decision.run.children if root.kind == 'potions'
               for n in f.walk(root) if n.kind == 'potion']
    enemies = [n for n in f.walk(decision.context) if n.kind == 'enemy' and n.get('alive')]
    incoming = sum((n.get('damage') or 0) * (n.get('hits') or 0) for e in enemies
                   for n in e.children if n.kind == 'intent' and n.definition_id == 'attack')
    block = decision.context.get('block', 0)
    hp, maximum = decision.run.get('hp'), decision.run.get('max_hp')
    threat = ('none' if not incoming else 'covered' if incoming <= block else
              'lethal' if incoming - block >= hp else 'unblocked')
    if decision.context.kind != 'combat':
        incoming, block, threat = None, None, 'unavailable'
    return {'encounter': encounter, 'room_kind': ENCOUNTERS[encounter].room_kind,
            'floor': decision.run.get('floor'), 'hp': decision.run.get('hp'),
            'max_hp': decision.run.get('max_hp'), 'deck_size': len(deck.children),
            'turn': run.combat.turn, 'potions': sorted(potions),
            'hp_band': 'critical' if hp * 4 <= maximum else 'damaged' if hp * 2 <= maximum else 'healthy',
            'incoming_damage': incoming, 'block': block,
            'threat': threat,
            'enemy_powers': sorted({n.definition_id for e in enemies for n in e.children
                                    if n.kind in ('power', 'power_counter') and n.get('amount')}),
            'inventory_sha256': digest([asdict(n) for n in decision.run.children
                                       if n.kind in ('deck', 'relics', 'potions')])}


def coverage(cases):
    result = {}
    for split in SPLITS:
        rows = [r for r in cases if r['split'] == split]
        openings = [r for r in rows if r['start_kind'] == 'opening']
        fights = list({r['combat_id']: r for r in rows}.values())
        expected = {name for name in ENCOUNTERS if name.startswith(REGIONS)}
        hard = {name for name in expected if ENCOUNTERS[name].room_kind in ('elite', 'boss')}
        result[split] = {'combats': len(fights), 'openings': len(openings), 'starts': len(rows),
            'source_campaigns': len({r['source_group'] for r in rows}),
            'by_region': dict(Counter(r['region'] for r in fights)),
            'by_room_kind': dict(Counter(r['room_kind'] for r in fights)),
            'by_encounter': dict(sorted(Counter(r['encounter'] for r in fights).items())),
            'by_start_kind': dict(Counter(r['start_kind'] for r in rows)),
            'starts_by_encounter': dict(sorted(Counter(r['encounter'] for r in rows).items())),
            'starts_with_potions': sum(bool(r['potions']) for r in rows),
            'by_potion': dict(sorted(Counter(p for r in rows for p in set(r['potions'])).items())),
            'by_threat': dict(Counter(r['threat'] for r in rows)),
            'by_hp_band': dict(Counter(r['hp_band'] for r in rows)),
            'by_enemy_power': dict(sorted(Counter(p for r in rows for p in r['enemy_powers']).items())),
            'missing_elites_bosses': sorted(hard - {r['encounter'] for r in rows}),
            'missing_encounters': sorted(expected - {r['encounter'] for r in rows}),
            'missing_region_kinds': [region + '/' + kind for region in REGIONS
                for kind in ('combat', 'elite', 'boss')
                if not any(r['region'] == region and r['room_kind'] == kind for r in rows)],
            'hp_range': [min(r['hp'] for r in rows), max(r['hp'] for r in rows)] if rows else None,
            'deck_size_range': [min(r['deck_size'] for r in rows), max(r['deck_size'] for r in rows)] if rows else None,
            'distinct_inventories': len({r['inventory_sha256'] for r in rows})}
    return result


def elite_route(decision):
    """Choose a legal route maximizing reachable elites using only the public map."""
    choices = [a for a in decision.candidates if a.kind == 'choose_map_node']
    if not choices:
        return None
    nodes = {n.ref: n for root in decision.run.children if root.kind == 'map' for n in root.children}

    @lru_cache(None)
    def value(ref):
        node = nodes[ref]
        return int(node.definition_id == 'elite') + max(
            [value(r) for r in node.linked('next_nodes')] + [0])

    return max(choices, key=lambda a: value(a.subject))


def _collect_campaign(group, seed, config, teacher, output, private, cancel=None):
    """Play one predeclared source campaign and freeze each reached fight start.

    Returns the campaign's public cases and private registry rows. Captures made
    before a failure stay with the failed group, as in serial collection; nothing
    is retried. The group row records the campaign outcome in place.
    """
    from .checkpoint import publish
    cases, registry = [], {}
    try:
        if cancel is not None and cancel.is_set():
            raise RunCancelled('Corpus collection cancelled')
        run = RunEngine.campaign(character='ironclad', first_act=group['region'],
                                 ascension=0, seed=seed, rng_profile='native')
        adapter = HeadlessAdapter(run, decision_profile=f.PROFILE)
        planning = None
        if config.record_planning:
            from game.agent.headless.planning import CampaignPlanning
            planning = CampaignPlanning(adapter)
        previous, combat_id, last_turn = None, None, None
        deadline = time.monotonic() + config.time_limit_seconds
        for step in range(config.max_decisions + 1):
            if cancel is not None and cancel.is_set():
                raise RunCancelled('Corpus collection cancelled')
            frame = adapter.observe()
            if isinstance(frame, c.RunOutcome):
                group['status'] = frame.kind
                break
            if completed_act(frame.decision) == 1:
                group['status'] = 'act1_cleared'
                break
            if step == config.max_decisions or time.monotonic() >= deadline:
                group['status'] = 'cutoff'
                break
            summary = adapter.combat_summary
            if run.combat is not None and summary and not summary.completed:
                if run.combat is not previous:
                    previous, combat_id, last_turn = run.combat, uuid.uuid4().hex, None
                    group['combats'] += 1
                opening = last_turn is None
                # A native turn may initially pause in an enemy-owned
                # selection. Retain a continuation only once it reaches an
                # ordinary player decision, never inside that pending effect.
                capture = opening or (last_turn < run.combat.turn <= config.capture_turns and
                    frame.decision.context.kind == 'combat' and not any(
                        n.kind == 'selection' for n in f.walk(frame.decision.context)))
            else:
                capture = False
            if capture:
                key = uuid.uuid4().hex
                # New combat episodes start with fresh adapter history. The
                # game-owned deck, draw order, RNG and run inventory survive.
                snapshot, restored, public = _freeze_start(run)
                row = {k: group[k] for k in ('source_group', 'split', 'region')}
                row.update(case_id=key, combat_id=combat_id, start_kind='opening' if opening else 'continuation',
                           scenario=run.state.active_encounter_id,
                           public_state_sha256=public_digest(public), **_describe(restored, public))
                if planning is not None:
                    anchor = planning.export()
                    row['planning_sha256'] = (publish(output / (key + '.planning.json'), data(anchor))
                                              if anchor is not None else None)
                snapshot_sha = publish(private / (key + '.start.json'), snapshot, private=True)
                registry[key] = {'snapshot_sha256': snapshot_sha, 'case': row}
                cases.append(row)
                group['starts'] += 1
                last_turn = run.combat.turn
            action = elite_route(frame.decision) if group['route_policy'] == 'elite_first' else None
            if action is None:
                action = teacher(frame.decision) if teacher else choose_action(frame.decision)
            execution = (planning or adapter).step(frame.binding, action.ref)
            if execution.status != 'reconciled':
                raise RuntimeError('Source campaign action did not reconcile')
            group['steps'] += 1
    except (Exception, KeyboardInterrupt) as error:
        status = 'interrupted' if isinstance(error, (KeyboardInterrupt, RunCancelled)) else 'failed'
        group.update(status=status, failure=type(error).__name__)
    return cases, registry


def _corpus_worker(collector, source, settings, output, private, stopped, connection):
    """Own whole campaigns with one collector copy; report only public rows and digests."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    index = None
    try:
        teacher = None
        if collector is not None:
            import torch
            torch.set_num_threads(1)
            from .checkpoint import load_policy
            path, sha, identity = collector
            teacher = load_policy(path, expected_sha256=sha, task='full_run')
            if teacher.identity != identity:
                raise ValueError('Corpus collector changed after planning')
        if asdict(implementation()) != source:
            raise ValueError('Corpus implementation changed after planning')
        config = CorpusConfig(**settings)
        connection.send(('ready', None, None))
        while not stopped.is_set():
            if not connection.poll(.02):
                continue
            index, group, seed = connection.recv()
            found, rows = _collect_campaign(group, seed, config, teacher, Path(output), Path(private), stopped)
            connection.send(('complete', index, (group, found, rows)))
            index = None
    except BaseException as error:
        # Seeds, engine state and exception text never leave the worker.
        status = 'interrupted' if isinstance(error, (RunCancelled, KeyboardInterrupt)) else 'failed'
        try:
            connection.send((status, index, type(error).__name__))
        except (OSError, EOFError):
            pass
    finally:
        connection.close()


def _valid_campaign_result(planned, value):
    if type(value) is not tuple or len(value) != 3:
        return False
    group, found, rows = value
    return (type(group) is dict and type(found) is list and type(rows) is dict and
            all(group.get(k) == planned[k] for k in ('source_group', 'split', 'region', 'route_policy')) and
            group.get('status') in ('act1_cleared', 'defeat', 'abandoned', 'cutoff', 'failed', 'interrupted') and
            group.get('starts') == len(found) and
            all(type(r) is dict and r.get('source_group') == planned['source_group'] for r in found) and
            set(rows) == {r['case_id'] for r in found} and len(rows) == len(found))


def _collect_parallel(groups, seeds, config, collector, output, private, workers, cancel, progress):
    """Collect predeclared campaigns in persistent spawn workers, preserving plan order.

    Each worker owns whole campaigns: its engine, collector copy and snapshot
    files. No campaign is retried. A failure or cancellation stops assignment;
    finished campaigns are retained and unassigned ones remain unattempted.
    """
    context = multiprocessing.get_context('spawn')
    stopped = context.Event()
    source = asdict(implementation())
    active, phases, assigned, deadlines, results = {}, {}, {}, {}, {}
    outcome = {'status': 'complete'}
    scheduled = 0

    def stop(status, failure=None, worker=None):
        if outcome['status'] == 'complete':
            outcome['status'] = status
        if worker in assigned:
            groups[assigned.pop(worker)].update(status=status, failure=failure)
        stopped.set()

    def receive(worker):
        process, connection, _ = active[worker]
        try:
            status, index, value = connection.recv()
        except (EOFError, OSError):
            stop('failed', 'WorkerExited', worker)
            phases[worker] = 'closed'
            return
        if status == 'ready' and index is None and phases[worker] == 'starting':
            phases[worker] = 'idle'
            return
        if status in ('failed', 'interrupted'):
            stop(status, value if type(value) is str else 'WorkerFailed', worker)
            phases[worker] = 'closed'
            return
        if (status != 'complete' or type(index) is not int or assigned.get(worker) != index or
                not _valid_campaign_result(groups[index], value)):
            stop('failed', 'InvalidWorkerResult', worker)
            phases[worker] = 'closed'
            return
        group, found, rows = value
        groups[index].update(group)
        results[index] = (found, rows)
        assigned.pop(worker)
        phases[worker] = 'idle'
        if group['status'] in ('failed', 'interrupted'):
            stop(group['status'])
        if progress:
            progress(groups[index], len(groups))

    try:
        for worker in range(min(workers, len(groups))):
            if cancel is not None and cancel.is_set():
                stop('interrupted', 'RunCancelled')
                break
            parent, child = context.Pipe()
            process = context.Process(target=_corpus_worker, name='sts-corpus-worker', args=(
                collector, source, asdict(config), str(output), str(private), stopped, child))
            active[worker] = (process, parent, None)
            phases[worker] = 'starting'
            deadlines[worker] = time.monotonic() + STARTUP_SECONDS
            try:
                with _defer_start_signals():
                    process.start()
            finally:
                child.close()
        while len(results) < len(groups) and not stopped.is_set():
            if cancel is not None and cancel.is_set():
                stop('interrupted', 'RunCancelled')
                break
            for worker, (process, connection, _) in active.items():
                if phases[worker] == 'closed':
                    continue
                if connection.poll():
                    receive(worker)
                elif not process.is_alive():
                    stop('failed', 'WorkerExited', worker)
                    phases[worker] = 'closed'
                elif phases[worker] != 'idle' and time.monotonic() >= deadlines[worker]:
                    stop('failed', 'WorkerDeadlineExceeded', worker)
                if stopped.is_set():
                    break
            if stopped.is_set():
                break
            for worker, (_, connection, _) in active.items():
                if phases[worker] != 'idle' or scheduled == len(groups):
                    continue
                if cancel is not None and cancel.is_set():
                    stop('interrupted', 'RunCancelled')
                    break
                assigned[worker] = scheduled
                phases[worker] = 'busy'
                # The campaign's own wall-clock limit is enforced in the worker;
                # this bounded margin covers snapshot publication and scheduling.
                deadlines[worker] = time.monotonic() + 2 * config.time_limit_seconds + CAMPAIGN_GRACE_SECONDS
                connection.send((scheduled, dict(groups[scheduled]), seeds[groups[scheduled]['source_group']]))
                scheduled += 1
            if len(results) < len(groups) and not stopped.is_set():
                time.sleep(.01)
    except (Exception, KeyboardInterrupt) as error:
        stop('interrupted' if isinstance(error, (RunCancelled, KeyboardInterrupt)) else 'failed',
             type(error).__name__)
    finally:
        stopped.set()
        # In-flight campaigns stop at their next decision and report what they
        # captured; a returned campaign is retained even after a sibling failed.
        until = time.monotonic() + DRAIN_SECONDS
        try:
            while assigned and time.monotonic() < until:
                for worker in list(assigned):
                    process, connection, _ = active[worker]
                    if connection.poll():
                        receive(worker)
                    elif not process.is_alive():
                        stop('failed', 'WorkerExited', worker)
                time.sleep(.01)
        except (Exception, KeyboardInterrupt) as error:
            stop('interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', type(error).__name__)
        finally:
            for worker in list(assigned):
                stop('interrupted', 'CorpusStopped', worker)
            try:
                _cleanup(active, stopped)
            except Exception:
                stop('failed', 'WorkerCleanupFailed')
    cases, registry = [], {}
    for index in sorted(results):
        found, rows = results[index]
        cases.extend(found)
        registry.update(rows)
    return outcome['status'], cases, registry


def build_corpus(output_dir, config=CorpusConfig(), *, checkpoint=None, cancel=None, progress=None, workers=1):
    """Attempt each predeclared campaign once; retain fights from losing runs too.

    Parallel workers each own whole campaigns. Seeds, routes and the collector
    are fixed before collection, so cases match serial collection except for
    opaque identifiers; their order follows the predeclared campaign schedule.
    """
    from .checkpoint import load_policy, publish
    if type(config) is not CorpusConfig:
        raise ValueError('Expected combat corpus settings')
    if type(workers) is not int or not 1 <= workers <= GAME_WORKER_LIMIT:
        raise ValueError(f'Corpus workers must be between 1 and {GAME_WORKER_LIMIT}')
    teacher, collector = None, None
    if checkpoint:
        checkpoint = Path(checkpoint).resolve()
        sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        teacher = load_policy(checkpoint, expected_sha256=sha, task='full_run')
        collector = (str(checkpoint), sha, teacher.identity)
    identity = implementation()
    output = Path(output_dir).resolve()
    output, private = prepare_directories(output, output.with_name(output.name + '-private'))
    path = output / 'corpus.json'
    if path.exists() or (private / 'registry.json').exists():
        raise FileExistsError(output)
    reservation = path.with_name(path.name + '.partial')
    with reservation.open('x'):
        pass
    groups, seeds = [], {}
    for split in SPLITS:
        for index in range(getattr(config, split + '_campaigns')):
            for region_index, region in enumerate(REGIONS):
                group = uuid.uuid4().hex
                seeds[group] = episode_seed(split, config.start_index + 2 * index + region_index)
                groups.append({'source_group': group, 'split': split, 'region': region,
                               'route_policy': 'elite_first' if config.route_policy == 'mixed_elites' and index % 2 else 'collector',
                               'status': 'unattempted', 'steps': 0, 'combats': 0, 'starts': 0, 'failure': None})
    publish(private / 'campaigns.json', data(seeds), private=True)
    cases, registry, status = [], {}, 'complete'
    started = time.perf_counter()
    if workers == 1:
        for group in groups:
            if status != 'complete':
                break
            found, rows = _collect_campaign(group, seeds[group['source_group']], config, teacher,
                                            output, private, cancel)
            cases.extend(found)
            registry.update(rows)
            if group['status'] in ('failed', 'interrupted'):
                status = group['status']
            if progress:
                progress(group, len(groups))
    else:
        status, cases, registry = _collect_parallel(groups, seeds, config, collector, output, private,
                                                    workers, cancel, progress)
    private_value = {'schema': SCHEMA, 'cases': registry, 'campaign_seeds': seeds,
                     'source_config': asdict(config)}
    report = {'schema': SCHEMA, 'implementation': asdict(identity),
        'config': {k: v for k, v in asdict(config).items() if k != 'start_index'},
        'status': status, 'collector': teacher.identity if teacher else identity.policy,
        'execution': {'workers': workers, 'schedule': 'serial_v1' if workers == 1 else 'parallel_campaigns_v1'},
        'evidence': 'headless_rollout', 'campaigns': groups, 'cases': cases,
        'registry_sha256': digest(private_value), 'coverage': coverage(cases),
        'sampling': 'Equal room-kind schedule; uniform encounter, then source combat within kind. '
                    'Half opening, half continuation when that combat has continuations; uniform later turn.',
        'limitations': ['Only fights reached by the frozen collector are represented; no failed source is retried.',
            'Late-fight inventories are conditioned on surviving the source campaign prefix.',
            'Coverage gaps are reported, not filled with assisted or invented inventory.',
            'Fights in one campaign share a source group and must remain in the same split.',
            'Later-turn starts are collector-conditioned practice states, not independent full-fight evaluations.',
            'Threat categories use displayed attack damage minus current block, not a simulated outcome forecast.',
            'Collection actions are not expert labels; more starts do not establish improved policy quality.',
            'Restored combat episodes begin with fresh adapter history.'],
        'total_seconds': time.perf_counter() - started}
    publish(private / 'registry.json', data(private_value), private=True)
    reservation.unlink()
    publish(path, data(report))
    if status == 'complete' and any(r['split'] == 'train' for r in cases):
        from .ppo_config import PPOConfig, PPOExperiment
        training = TrainingConfig(reward=RewardSpec({'combat_win': 1., 'win_hp_fraction': .1}),
                                  action_policy=COMMIT_DECISIONS)
        experiment = PPOExperiment(training, PPOConfig(rollout_steps=4096, episode_decisions=512,
            episode_seconds=120., batch_size=16, epochs=2),
            tuple(k for k in ROOM_KINDS if any(r['split'] == 'train' and r['room_kind'] == k for r in cases)),
            SOURCE + ':' + digest(report), 'sts_ppo_experiment_v2')
        publish(output / 'combat-ppo.json', data(experiment.to_dict()))
        publish(output / 'combat-training.json', data(training.to_dict()))
    return path, report


def _read(path, *, private=False, expected_sha=None):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('Invalid corpus artifact')
    if private and path.stat().st_mode & 0o077:
        raise ValueError('Combat snapshots and seeds require owner-only permissions')
    raw = path.read_bytes()
    if expected_sha is not None and hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError('Frozen combat artifact digest mismatch')
    return strict_json(raw)


class CombatCorpus:
    def __init__(self, path, *, expected=None):
        path = Path(path)
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError('Unexpected corpus symlink')
        self.path = path.resolve()
        self.report = _read(self.path)
        report = self.report
        self.identity = SOURCE + ':' + digest(report)
        if expected is not None and expected != self.identity:
            raise ValueError('Combat corpus differs from the bound training/evaluation source')
        if (report.get('schema') != SCHEMA or report.get('status') != 'complete' or
                report.get('implementation') != asdict(implementation())):
            raise ValueError('Combat corpus requires a complete collection and unchanged implementation')
        self.private = self.path.parent.with_name(self.path.parent.name + '-private')
        if self.private.is_symlink() or self.private.stat().st_mode & 0o077:
            raise ValueError('Combat corpus private directory must be owner-only')
        private = _read(self.private / 'registry.json', private=True, expected_sha=report['registry_sha256'])
        if private.get('schema') != SCHEMA or digest(private) != report['registry_sha256']:
            raise ValueError('Combat corpus registry mismatch')
        config = CorpusConfig(**private['source_config'])
        recorded_config = {k: v for k, v in asdict(config).items() if k != 'start_index'}
        if not config.record_planning and 'record_planning' not in report['config']:
            recorded_config.pop('record_planning')
        if report['config'] != recorded_config:
            raise ValueError('Combat source settings mismatch')
        groups, roots = {}, set()
        for row in report['campaigns']:
            key, split, region = row['source_group'], row['split'], row['region']
            if (not _uuid(key) or key in groups or split not in SPLITS or region not in REGIONS or
                    row['route_policy'] not in ('collector', 'elite_first') or
                    config.route_policy == 'collector' and row['route_policy'] != 'collector' or
                    row['status'] not in ('act1_cleared', 'defeat', 'abandoned', 'cutoff')):
                raise ValueError('Invalid source campaign')
            seed = private['campaign_seeds'][key]
            if type(seed) is not int or seed < 0 or seed % 3 != SPLITS.index(split) or seed in roots:
                raise ValueError('Overlapping or cross-split source campaign seed')
            roots.add(seed)
            groups[key] = row
        if set(private['campaign_seeds']) != set(groups) or any(
                sum(r['split'] == split and r['region'] == region for r in groups.values()) !=
                getattr(config, split + '_campaigns') for split in SPLITS for region in REGIONS):
            raise ValueError('Source campaign population mismatch')
        self._campaign_seeds = private['campaign_seeds']
        self.cases, combats, turns = {}, {}, set()
        for row in report['cases']:
            key = row['case_id']
            group = groups.get(row['source_group'])
            if (not _uuid(key) or key in self.cases or group is None or
                    not _uuid(row['combat_id']) or row['start_kind'] not in ('opening', 'continuation') or
                    type(row['turn']) is not int or not 1 <= row['turn'] <= config.capture_turns or
                    (row['start_kind'] == 'opening') != (row['turn'] == 1) or
                    any(row[k] != group[k] for k in ('split', 'region')) or
                    row['encounter'] not in ENCOUNTERS or row['scenario'] != row['encounter'] or
                    row['room_kind'] != ENCOUNTERS[row['encounter']].room_kind or
                    not _sha(row['public_state_sha256']) or not _sha(row['inventory_sha256'])):
                raise ValueError('Invalid or cross-split combat case')
            combat = row['combat_id']
            owner = tuple(row[k] for k in ('source_group', 'encounter', 'floor'))
            if (combat in combats and combats[combat] != owner or (combat, row['turn']) in turns):
                raise ValueError('Duplicate turn or cross-source combat continuation')
            combats[combat] = owner
            turns.add((combat, row['turn']))
            self.cases[key] = row
            if config.record_planning and ('planning_sha256' not in row or
                    row['planning_sha256'] is not None and not _sha(row['planning_sha256'])):
                raise ValueError('Invalid public planning receipt binding')
        self.registry = private['cases']
        if set(self.registry) != set(self.cases) or any(
                not _sha(r['snapshot_sha256']) or r['case'] != self.cases[key]
                for key, r in self.registry.items()):
            raise ValueError('Combat snapshot mapping mismatch')
        if (any((combat, 1) not in turns for combat in combats) or
                any(sum(c['source_group'] == key for c in self.cases.values()) != group['starts'] or
                    sum(c['source_group'] == key and c['start_kind'] == 'opening' for c in self.cases.values()) != group['combats']
                    for key, group in groups.items()) or coverage(list(self.cases.values())) != report['coverage']):
            raise ValueError('Corpus coverage disagrees with its cases')

    def split(self, split):
        if split not in SPLITS:
            raise ValueError('Unknown corpus split')
        return [r for r in self.cases.values() if r['split'] == split]

    def restore(self, key, *, split):
        row = self.cases[key]
        if row['split'] != split:
            raise ValueError('Combat case belongs to another split')
        path = self.private / (key + '.start.json')
        snapshot = _read(path, private=True, expected_sha=self.registry[key]['snapshot_sha256'])
        run = restore_run(snapshot)
        adapter = HeadlessAdapter(run, decision_profile=f.PROFILE)
        frame = adapter.observe()
        summary = adapter.combat_summary
        if (isinstance(frame, c.RunOutcome) or not summary or summary.completed or
                run.state.config.character != 'ironclad' or run.state.config.ascension != 0 or
                run.state.seed != self._campaign_seeds[row['source_group']] or
                run.state.config.act != row['region'] or frame.decision.run.get('act') != 1 or
                public_digest(frame.decision) != row['public_state_sha256'] or
                any(row[k] != v for k, v in _describe(run, frame.decision).items())):
            raise ValueError('Frozen combat state disagrees with its public case')
        return run

    def planning_start(self, key, *, split):
        row = self.cases[key]
        if row['split'] != split:
            raise ValueError('Planning receipt belongs to another split')
        sha = row.get('planning_sha256')
        if sha is None:
            return None
        # Search validates capability separately and records unsupported public
        # entries as fallbacks. Artifact integrity applies to every entry.
        return _read(self.path.parent / (key + '.planning.json'), expected_sha=sha)


def _uuid(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{32}', value) is not None


def _sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


@dataclass(frozen=True)
class CorpusEnvironment:
    """Spawn-safe factory. Only the training partition can enter PPO."""
    path: str
    identity: str
    hidden_state: str = FROZEN_HIDDEN_STATE

    def __post_init__(self):
        if self.hidden_state not in HIDDEN_STATES:
            raise ValueError('Unknown corpus hidden-state treatment')

    @cached_property
    def corpus(self):
        from .search_sources import open_search_source
        return open_search_source(self.path, expected=self.identity)

    @cached_property
    def pools(self):
        pools = {}
        for row in self.corpus.split('train'):
            pools.setdefault(row['room_kind'], {}).setdefault(row['encounter'], {}).setdefault(
                row['combat_id'], []).append(row)
        return pools

    def __call__(self, *, encounter, **settings):
        from .env import CombatTrainingEnv
        pool = self.pools.get(encounter)
        if not pool:
            raise ValueError('Room kind has no training cases in this corpus')

        def make(seed):
            row = sample_training_case(pool, seed)
            run = self.corpus.restore(row['case_id'], split='train')
            if self.hidden_state == RESAMPLED_HIDDEN_STATE:
                # The verified public start is unchanged; the reset seed alone
                # determines the new hidden state, so replay audits reproduce it.
                resample_hidden_combat(run, hidden_state_seed(seed))
            env.corpus_case = row
            history = getattr(self.corpus, 'history_start', None) or self.corpus.planning_start
            env.public_history_start = history(row['case_id'], split='train')
            return run

        env = CombatTrainingEnv(engine_factory=make, **settings)
        return env


def hidden_state_seed(seed):
    """Separate the hidden-state stream from case selection for the same reset seed."""
    return int.from_bytes(hashlib.sha256(f'{RESAMPLED_HIDDEN_STATE}:{seed}'.encode()).digest()[:8], 'big')


def sample_training_case(pool, seed):
    """Shared encounter/fight-balanced opening-versus-continuation sampling."""
    rng = Random(seed)
    fights = pool[rng.choice(sorted(pool))]
    rows = fights[rng.choice(sorted(fights))]
    opening = [r for r in rows if r['start_kind'] == 'opening']
    later = [r for r in rows if r['start_kind'] == 'continuation']
    return rng.choice(rng.choice((opening, later)) if later else opening)


def training_factory(path, experiment):
    factory = CorpusEnvironment(str(Path(path).absolute()), experiment.source, experiment.hidden_state)
    validate_factory(experiment, factory)
    return factory


def validate_factory(experiment, factory):
    """Bind the source at every learner/collection boundary, including resume."""
    if (experiment.hidden_state != FROZEN_HIDDEN_STATE or isinstance(factory, CorpusEnvironment)) and (
            type(factory) is not CorpusEnvironment or factory.hidden_state != experiment.hidden_state):
        raise ValueError('Combat PPO requires the environment bound to its hidden-state treatment')
    if not experiment.source.startswith('act1_combat_corpus_') and not isinstance(factory, CorpusEnvironment):
        return
    if type(factory) is not CorpusEnvironment or factory.identity != experiment.source:
        raise ValueError('Combat PPO requires the environment bound to its corpus source')
    corpus = factory.corpus
    encounters = {r['room_kind'] for r in corpus.split('train')}
    if (corpus.identity != experiment.source or experiment.training.mode != 'combat' or
            not set(experiment.encounters) <= encounters):
        raise ValueError('PPO must use only room kinds present in the train partition')


def collect_corpus_demonstrations(*, corpus_path, output_dir, split='train', config=None,
                                  max_decisions=512, time_limit_seconds=120., cancel=None):
    from .checkpoint import publish
    from .demonstrations import SCHEMA as DEMO_SCHEMA
    from .evaluation import BaselineCase, _episode
    if split not in ('train', 'validation'):
        raise ValueError('Held-out combat cases cannot become imitation demonstrations')
    corpus = CombatCorpus(corpus_path)
    rows = corpus.split(split)
    if not rows:
        raise ValueError('No combat cases in requested demonstration split')
    config = config or TrainingConfig(reward=RewardSpec({'combat_win': 1., 'win_hp_fraction': .1}),
                                      action_policy=COMMIT_DECISIONS)
    if type(config) is not TrainingConfig or config.mode != 'combat':
        raise ValueError('Combat demonstrations require a combat training objective')
    from .env import CombatTrainingEnv
    with CombatTrainingEnv(max_decisions=max_decisions, time_limit_seconds=time_limit_seconds):
        pass
    output = Path(output_dir).resolve()
    output, private = prepare_directories(output, output.with_name(output.name + '-private'))
    path = output / 'demonstrations.json'
    if path.exists() or path.with_name(path.name + '.partial').exists():
        raise FileExistsError(path)
    report = {'schema': DEMO_SCHEMA, 'scenario_set': corpus.identity, 'split': split,
              'teacher': implementation().policy, 'training_config': config.to_dict(),
              'status': 'complete', 'requested_episodes': len(rows), 'episodes': []}
    for row in rows:
        case = BaselineCase(row['encounter'], split, 0, 0, max_decisions, time_limit_seconds)
        result = _episode(case, 'heuristic', implementation(), output, private, config,
            engine_factory=lambda _, key=row['case_id']: corpus.restore(key, split=split),
            scenario_set=corpus.identity, evidence='headless_rollout',
            expected_start=row['public_state_sha256'], cancel=cancel)
        result.update(case_id=row['case_id'], source_group=row['source_group'])
        report['episodes'].append(result)
        if result['status'] not in ('terminated', 'truncated'):
            report['status'] = result['status']
            break
    report['unattempted_episodes'] = len(rows) - len(report['episodes'])
    publish(path, data(report))
    return path, report
