"""Campaign-derived Act 1 combat starts; engine snapshots remain owner-only."""
from collections import Counter
from dataclasses import asdict, dataclass
from functools import cached_property, lru_cache
import hashlib
import json
import math
from pathlib import Path
from random import Random
import re
import time
import uuid

from game.agent import contracts as c
from game.agent.action_policy import COMMIT_DECISIONS
from game.agent.contracts import full as f
from game.agent.full_policy import choose_action
from game.agent.headless.adapter import HeadlessAdapter
from game.agent.progress import completed_act
from game.agent.provenance import implementation
from game.agent.runner import RunCancelled, prepare_directories
from game.headless.encounters.catalog import ENCOUNTERS
from game.headless.run.engine import RunEngine
from game.headless.run.snapshots import restore_run
from .benchmark_suite import data, digest
from .config import TrainingConfig
from .rewards import RewardSpec, strict_json
from .scenarios import episode_seed

SCHEMA = 'sts_act1_combat_corpus_v2'
SOURCE = 'act1_combat_corpus_v2'
REGIONS = ('overgrowth', 'underdocks')
SPLITS = ('train', 'validation', 'test')
ROOM_KINDS = ('combat', 'elite', 'boss')


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


def build_corpus(output_dir, config=CorpusConfig(), *, checkpoint=None, cancel=None, progress=None):
    """Attempt each predeclared campaign once; retain fights from losing runs too."""
    from .checkpoint import load_policy, publish
    if type(config) is not CorpusConfig:
        raise ValueError('Expected combat corpus settings')
    teacher = load_policy(checkpoint, task='full_run') if checkpoint else None
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
    for group in groups:
        if status != 'complete':
            break
        try:
            if cancel is not None and cancel.is_set():
                raise RunCancelled('Corpus collection cancelled')
            run = RunEngine.campaign(character='ironclad', first_act=group['region'],
                                     ascension=0, seed=seeds[group['source_group']], rng_profile='native')
            adapter = HeadlessAdapter(run, decision_profile=f.PROFILE)
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
                    snapshot_sha = publish(private / (key + '.start.json'), snapshot, private=True)
                    registry[key] = {'snapshot_sha256': snapshot_sha, 'case': row}
                    cases.append(row)
                    group['starts'] += 1
                    last_turn = run.combat.turn
                action = elite_route(frame.decision) if group['route_policy'] == 'elite_first' else None
                if action is None:
                    action = teacher(frame.decision) if teacher else choose_action(frame.decision)
                execution = adapter.step(frame.binding, action.ref)
                if execution.status != 'reconciled':
                    raise RuntimeError('Source campaign action did not reconcile')
                group['steps'] += 1
        except (Exception, KeyboardInterrupt) as error:
            status = 'interrupted' if isinstance(error, (KeyboardInterrupt, RunCancelled)) else 'failed'
            group.update(status=status, failure=type(error).__name__)
        if progress:
            progress(group, len(groups))
    private_value = {'schema': SCHEMA, 'cases': registry, 'campaign_seeds': seeds,
                     'source_config': asdict(config)}
    report = {'schema': SCHEMA, 'implementation': asdict(identity),
        'config': {k: v for k, v in asdict(config).items() if k != 'start_index'},
        'status': status, 'collector': teacher.identity if teacher else identity.policy,
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
        if report['config'] != {k: v for k, v in asdict(config).items() if k != 'start_index'}:
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


def _uuid(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{32}', value) is not None


def _sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


@dataclass(frozen=True)
class CorpusEnvironment:
    """Spawn-safe factory. Only the training partition can enter PPO."""
    path: str
    identity: str

    @cached_property
    def corpus(self):
        return CombatCorpus(self.path, expected=self.identity)

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
            env.corpus_case = row
            return run

        env = CombatTrainingEnv(engine_factory=make, **settings)
        return env


def sample_training_case(pool, seed):
    """Shared encounter/fight-balanced opening-versus-continuation sampling."""
    rng = Random(seed)
    fights = pool[rng.choice(sorted(pool))]
    rows = fights[rng.choice(sorted(fights))]
    opening = [r for r in rows if r['start_kind'] == 'opening']
    later = [r for r in rows if r['start_kind'] == 'continuation']
    return rng.choice(rng.choice((opening, later)) if later else opening)


def training_factory(path, experiment):
    factory = CorpusEnvironment(str(Path(path).absolute()), experiment.source)
    validate_factory(experiment, factory)
    return factory


def validate_factory(experiment, factory):
    """Bind the source at every learner/collection boundary, including resume."""
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
