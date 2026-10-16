"""Paired greedy/sampled study evaluations using the existing episode recorder."""
from dataclasses import asdict, dataclass, replace
import hashlib
from pathlib import Path
import time
import uuid
import numpy as np
import torch

from game.agent.action_policy import action_mask
from game.agent.contracts import full as f
from game.agent.full_policy import choose_action
from game.agent.provenance import implementation
from game.agent.runner import prepare_directories
from ..benchmark_suite import data
from ..checkpoint import load_policy, publish
from ..config import TrainingConfig
from ..evaluation import BaselineCase, _episode
from ..evaluation_workers import evaluate_parallel
from ..rewards import RewardSpec
from .source import StudySource, _read, _sha_file
from .spec import FeatureSpec, channels, digest


@dataclass(frozen=True, slots=True)
class StudyCase(BaselineCase):
    case_id: str
    mode: str
    repeat: int


def policy_seed(case, seed, repeat):
    return int.from_bytes(hashlib.sha256(f'{case}:{seed}:{repeat}:evaluation-actions'.encode()).digest()[:8], 'big') % 2**63


class StudyPolicy:
    def __init__(self, policy, *, mode, seed, training_content=()):
        self.policy, self.mode = policy, mode
        self.generator = torch.Generator().manual_seed(seed)
        self.feature_rows = self.calls = 0
        self.low = self.high = None
        self.unknown = {}
        self.boss_hp = None
        self.training_content = set(training_content)
        self.content_exposure = None
        self.numeric_unknown, self.numeric_applicable = {}, {}
        self.history_missing = self.history_observations = 0
        self.inference_seconds = 0.

    def __getattr__(self, key):
        return getattr(self.policy, key)

    def __call__(self, public):
        before = time.perf_counter()
        state = self.policy.encoder.encode_inference(public)
        encoding_seconds = time.perf_counter()-before
        values = state.values
        self.feature_rows += len(values)
        self.calls += 1
        low, high = values.min(0), values.max(0)
        self.low = low if self.low is None else np.minimum(self.low, low)
        self.high = high if self.high is None else np.maximum(self.high, high)
        columns = self.policy.encoder.indexes
        if self.content_exposure is None:
            content = {n.definition_id for n in (*f.walk(public.context), *f.walk(public.run))
                       if n.kind in ('card', 'enemy', 'potion', 'relic')}
            self.content_exposure = dict(known=len(content & self.training_content), total=len(content))
        player = values[0]
        for name, index in columns.items():
            if name.startswith('turn.') and name.endswith('.known'):
                self.unknown[name] = self.unknown.get(name, 0) + int(player[index] == 0)
        roles = {role: values[:, columns['role='+role]] > 0 for role in ('player','enemy','card','potion','relic','selection')}
        for name, index in columns.items():
            if not name.endswith('.known'):
                continue
            prefix = name.split('.')[0]
            selected = (roles['player'] if prefix in ('turn','threat','count','actions') else
                roles['enemy'] if prefix in ('intent','history') else
                roles['player'] | roles['enemy'] if prefix == 'power' else
                roles['potion'] | roles['relic'] if prefix == 'item' else
                roles['card'] | roles['potion'] | roles['relic'] if prefix == 'mechanics' else
                roles['card'] if prefix in ('card','damage','card_block','draw','uses_target','all_enemies','hits') else
                np.ones(len(values), dtype=bool))
            parts = name.split('.')
            if len(parts) > 4 and parts[:2] == ['mechanics','effect'] and parts[3] != 'present':
                selected = selected & (values[:,columns['.'.join(parts[:3])+'.present.scaled']] > 0)
            self.numeric_unknown[name] = self.numeric_unknown.get(name,0)+int((values[selected,index] == 0).sum())
            self.numeric_applicable[name] = self.numeric_applicable.get(name,0)+int(selected.sum())
        if 'history.complete.scaled' in columns:
            self.history_observations += int(roles['enemy'].sum())
            self.history_missing += int((values[roles['enemy'],columns['history.complete.scaled']] == 0).sum())
        current_hp = [n.get('hp') for n in public.context.children if n.kind == 'enemy']
        if not current_hp:
            from .history import enemies
            current_hp = [n.get('hp') for n in enemies(public)]
        self.boss_hp = sum(current_hp) if all(type(hp) is int for hp in current_hp) else None
        before = time.perf_counter()
        probabilities, _ = self.policy._probabilities(state)
        refs, weights = tuple(probabilities), torch.tensor(tuple(probabilities.values()))
        index = (int(weights.argmax()) if self.mode == 'greedy' else
                 int(torch.multinomial(weights, 1, generator=self.generator)))
        action = next(a for a in public.candidates if a.ref == refs[index])
        self.inference_seconds += encoding_seconds+time.perf_counter()-before
        return action

    def audit(self):
        return dict(decisions=self.calls, entity_rows=self.feature_rows,
            missing_counter_decisions=self.unknown,
            numeric_unknown=self.numeric_unknown, numeric_applicable=self.numeric_applicable,
            history_missing=self.history_missing, history_observations=self.history_observations,
            minimum=None if self.low is None else self.low.tolist(),
            maximum=None if self.high is None else self.high.tolist())


class StudyEvaluator:
    """One frozen model cache and source per existing evaluation worker."""
    def __init__(self, settings, checkpoints, policies, source):
        self.settings, self.identities = settings, policies
        self.source = StudySource(settings['path'], expected=settings['identity'], reservation=settings.get('reservation'))
        self.models = {name: load_policy(path, expected_sha256=sha, task=task)
                       for name, (path, sha, task) in checkpoints.items()}
        self.implementation = implementation()
        if asdict(self.implementation) != source:
            raise ValueError('Evaluation source changed')
        self.reward = RewardSpec({'combat_win': 1., 'win_hp_fraction': .1})

    def run(self, config, episode, name, output, private, cancel=None):
        source = self.source
        row = source.cases[config.case_id]
        if config.split != row['split'] or row['start_kind'] != 'opening':
            raise ValueError('Study evaluation requires the declared opening split')
        model = self.models.get(name)
        chooser = StudyPolicy(model, mode=config.mode, seed=config.policy_seed,
                              training_content=self.settings['training_content']) if model else None
        if source.reservation:
            registered = source.binding
            entry = registered['policies'].get(name)
            if (entry is None or registered['limits'] != dict(max_decisions=config.max_decisions,
                    time_limit_seconds=config.time_limit_seconds)
                    or entry != self.settings['registered_policies'][name]
                    or model is not None and entry['sha256'] != model.identity.split(':')[-1]):
                raise ValueError('Held-out model or limits differ from reservation')
            make = lambda _: source.restore_test(config.case_id, policy=name, mode=config.mode, repeat=config.repeat)
            # Certified source openings have no prior enemy phase. The initial
            # draw receipts are absent for test, so their counter stays unknown.
            anchor = (lambda public: dict(opening=f.to_dict(public),
                                          opening_reveals=None, transitions=[])) if chooser else None
        else:
            make = lambda _: source.restore(config.case_id, split=config.split)
            anchor = source.history_start(config.case_id, split=config.split) if chooser else None
        result = _episode(config, name, replace(self.implementation, policy=self.identities[name]),
            Path(output), Path(private), TrainingConfig(reward=self.reward, action_policy='commit_decisions_v1'),
            chooser=chooser, engine_factory=make, scenario_set=source.identity, cancel=cancel,
            episode_id=episode, expected_start=row['public_state_sha256'], evidence='headless_rollout', planning_start=anchor,
            public_health=True)
        result.update(case_id=config.case_id, source_group=row['source_group'], combat_id=row['combat_id'],
                      mode=config.mode, repeat=config.repeat)
        result['slice'] = {key: row[key] for key in ('hp','max_hp','hp_band','deck_size','potions')}
        if chooser:
            result['feature_audit'] = chooser.audit()
            result['content_exposure'] = chooser.content_exposure
            result['inference_seconds'] = chooser.inference_seconds
        health = result.get('settled_public_health') or {}
        enemy_hp = [e['hp'] for e in health.get('enemies', ())]
        result['boss_hp'] = sum(enemy_hp) if enemy_hp and all(type(h) is int for h in enemy_hp) else None
        result['boss_hp_measurement'] = 'settled_public_hud' if result['boss_hp'] is not None else 'unavailable'
        return result


def evaluate(*, source_path, output_dir, checkpoints, split, modes, workers,
             seed=0, reservation=None, cancel=None, max_decisions=512, time_limit_seconds=120., training_content=()):
    source = StudySource(source_path, reservation=reservation)
    entries = {name: dict(checkpoint=str(Path(path).resolve()), sha256=_sha_file(path)) for name, path in checkpoints.items()}
    if reservation:
        entries = source.binding['policies']
        if (split != 'test' or [list(m) for m in modes] != source.binding['modes']
                or dict(max_decisions=max_decisions,time_limit_seconds=time_limit_seconds) != source.binding['limits']):
            raise ValueError('Execute all and only the registered held-out modes and limits')
    binding = dict(source=source.identity, split=split, policies=entries,
        modes=[list(m) for m in modes], seed=seed,
        training_content=list(training_content),
        limits=dict(max_decisions=max_decisions, time_limit_seconds=time_limit_seconds))
    output = Path(output_dir).resolve()
    if reservation and str(output) != source.binding['execution_output']:
        raise ValueError('Held-out evaluation output differs from the single reservation')
    report_path = output/'evaluation.json'
    if report_path.exists():
        report = _read(report_path)
        if report['binding'] != binding or report['status'] != 'complete':
            raise ValueError('Existing evaluation is incomplete or has another binding; no retry')
        return report
    output, private = prepare_directories(output, output.with_name(output.name+'-private'))
    if (output/'plan.json').exists():
        raise ValueError('Evaluation was already attempted; never silently repeat it')
    cases = [r for r in source.split(split) if r['start_kind'] == 'opening']
    models = {name: (e['checkpoint'], e['sha256'], 'combat') for name, e in entries.items() if 'checkpoint' in e}
    impl = asdict(implementation())
    identities = {name: 'ppo_v1:'+e['sha256'] if 'checkpoint' in e else
                  impl['policy'] if name == 'heuristic' else 'random_legal_v1:'+impl['build'] for name, e in entries.items()}
    rows, configs = [], []
    for row in cases:
        for name in entries:
            for mode, repeat in modes:
                if mode not in ('greedy', 'sampled') or repeat not in (0, 1) or mode == 'greedy' and repeat:
                    raise ValueError('Unsupported study evaluation mode')
                rows.append(dict(row, policy=name, mode=mode, repeat=repeat, episode_id=uuid.uuid4().hex,
                                 status='unattempted', steps=0, combat=None))
                paired_seed = entries[name].get('learner_seed', seed)
                configs.append(StudyCase(row['encounter'], split, 0, policy_seed(row['case_id'], paired_seed, repeat),
                                         max_decisions, time_limit_seconds, row['case_id'], mode, repeat))
    publish(output/'plan.json', data(dict(binding=binding, episodes=rows, implementation=impl)))
    settings = dict(kind='feature_study', path=str(source.path), identity=source.identity,
                    reservation=reservation, registered_policies=entries, training_content=training_content)
    started = time.perf_counter()
    if workers > 1:
        status = evaluate_parallel(rows, configs, checkpoints=models, policies=identities, source=impl,
            output=output, private=private, workers=workers, cancel=cancel, combat=settings)
    else:
        owner = StudyEvaluator(settings, models, identities, impl)
        status = dict(status='complete')
        for row, config in zip(rows, configs):
            row.update(owner.run(config, row['episode_id'], row['policy'], output, private, cancel))
            if row['status'] not in ('terminated', 'truncated'):
                status = dict(status='failed', failure=row.get('failure'))
                break
    audits = {}
    for row in rows:
        audit = row.pop('feature_audit', None)
        if audit is None:
            continue
        name = row['policy']
        previous = audits.get(name)
        if previous is None:
            audits[name] = audit
        else:
            for key in ('decisions', 'entity_rows', 'history_missing', 'history_observations'):
                previous[key] += audit[key]
            for family in ('missing_counter_decisions','numeric_unknown','numeric_applicable'):
                for key, value in audit[family].items():
                    previous[family][key] += value
            for key, fn in (('minimum', np.minimum), ('maximum', np.maximum)):
                if audit[key] is not None:
                    previous[key] = audit[key] if previous[key] is None else fn(previous[key], audit[key]).tolist()
    for audit in audits.values():
        audit['unknown_numeric_rates'] = {k: v/max(1,audit['numeric_applicable'][k]) for k,v in audit['numeric_unknown'].items()}
        audit['missing_enemy_history_rate'] = audit['history_missing']/max(1,audit['history_observations'])
    report = dict(schema='sts_feature_study_evaluation_v1', binding=binding, episodes=rows, feature_audits=audits,
                  seconds=time.perf_counter()-started, **status)
    publish(report_path, data(report))
    if report['status'] != 'complete':
        raise ValueError('Study evaluation did not complete; inspect its retained report')
    return report
