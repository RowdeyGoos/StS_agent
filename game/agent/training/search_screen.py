"""Supervised representation screen on collected combat-search targets.

Each candidate representation is fitted to the search distributions of most
source campaigns and measured on the held-out rest. Whole campaigns stay on one
side of the split. Every candidate sees the same decisions and the same recipe,
which mirrors ``search-distill``: soft cross entropy plus 0.25 x the completed-
return value loss, Adam, gradient clipping. Study encoders follow each fight's
public history exactly as during play. Nothing here plays games or changes a
checkpoint; the report is a fit measurement, not a win rate.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

SCHEMA = 'sts_search_representation_screen_v1'
KINDS = ('checkpoint', 'production', 'study')
STUDY_CAPACITY = 128


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


OPTIONAL = {'fit_fraction', 'fit_salt', 'evaluation_reports'}


def validate_config(config):
    """Optional fields: ``fit_fraction`` keeps that share of fit campaigns (nested by
    ``fit_salt``); ``evaluation_reports`` supply the held-out decisions instead of
    ``reports``, so students fitted to different labels share one held-out set."""
    keys = {'schema', 'reports', 'holdout_fraction', 'split_salt', 'epochs', 'checkpoints', 'learning_rate',
            'batch_size', 'value_weight', 'gradient_clip', 'seeds', 'threads', 'candidates'}
    if (type(config) is not dict or not keys <= set(config) <= keys | OPTIONAL
            or config['schema'] != SCHEMA):
        raise ValueError('Invalid representation screen configuration')
    if 'fit_fraction' in config:
        if (type(config['fit_fraction']) is not float or not 0 < config['fit_fraction'] <= 1
                or type(config.get('fit_salt')) is not str or config['fit_salt'] == config['split_salt']):
            raise ValueError('A fit fraction needs its own subsampling salt')
    elif 'fit_salt' in config:
        raise ValueError('A fit salt requires a fit fraction')
    if 'evaluation_reports' in config and (not config['evaluation_reports']
            or not all(type(p) is str for p in config['evaluation_reports'])):
        raise ValueError('Invalid held-out evaluation reports')
    if (not config['reports'] or not all(type(p) is str for p in config['reports'])
            or not 0 < config['holdout_fraction'] < 1 or type(config['split_salt']) is not str
            or type(config['epochs']) is not int or not 1 <= config['epochs'] <= 64
            or sorted(set(config['checkpoints'])) != config['checkpoints'] or config['checkpoints'][-1] != config['epochs']
            or not all(type(e) is int and e >= 1 for e in config['checkpoints'])
            or not 0 < config['learning_rate'] <= .01 or type(config['batch_size']) is not int
            or not 1 <= config['batch_size'] <= 256 or not config['value_weight'] >= 0
            or not config['gradient_clip'] > 0 or not config['seeds'] or len(set(config['seeds'])) != len(config['seeds'])
            or not all(type(s) is int and 0 <= s < 2**63 for s in config['seeds'])
            or type(config['threads']) is not int or not 1 <= config['threads'] <= 16
            or type(config['candidates']) is not dict or not config['candidates']):
        raise ValueError('Invalid representation screen settings')
    for name, spec in config['candidates'].items():
        if type(name) is not str or not name.replace('_', '').isalnum() or type(spec) is not dict:
            raise ValueError('Invalid screen candidate')
        fields = {'checkpoint': {'kind', 'checkpoint'},
                  'production': {'kind', 'vocabulary_from', 'schema', 'hidden_size', 'message_layers'},
                  'study': {'kind', 'architecture', 'richness', 'identities', 'hidden_size'}}.get(spec.get('kind'))
        if fields is None or set(spec) != fields:
            raise ValueError(f'Invalid screen candidate {name}')
    return config


def _fraction(salt, group):
    return int.from_bytes(hashlib.sha256(f'{salt}:{group}'.encode()).digest()[:8], 'big') / 2**64


def holdout(group, config):
    """Deterministic campaign assignment, independent of candidate and seed."""
    return _fraction(config['split_salt'], group) < config['holdout_fraction']


def fitted(group, config):
    """Fit campaigns kept by the optional subsample; smaller fractions are nested in larger ones."""
    return not holdout(group, config) and (
        'fit_fraction' not in config or _fraction(config['fit_salt'], group) < config['fit_fraction'])


@dataclass(frozen=True)
class Decision:
    """One searched decision under one candidate's encoding."""
    state: object
    target: tuple
    prior: tuple
    value: float | None
    group: str
    room_kind: str
    encounter: str


def _episodes(config, reports=None, keep=None):
    """Yield every collected fight with its public targets, reveals and returns."""
    from game.agent.recording import load_trajectory
    from .dataset import training_episode
    from .search_run import OBJECTIVE, _artifact, _load_search_targets, _planning_trace, _report_input_view
    for path in config['reports'] if reports is None else reports:
        path = Path(path).resolve()
        report = json.loads(path.read_text())
        if report.get('split') != 'train' or report.get('purpose') != 'collection' or report.get('status') != 'complete':
            raise ValueError('The screen requires complete training collection reports')
        view = _report_input_view(report)
        for row in report['episodes']:
            if not row.get('targets') or keep is not None and not keep(row):
                continue
            trajectory = load_trajectory(_artifact(path.parent, row['trajectory']), split='train',
                expected={'policy': row.get('behavior_policy', report['policies'][row['policy']])})
            data = _load_search_targets(path, report, row, trajectory, view)
            start, _ = _planning_trace(data, trajectory, row)
            episode = training_episode(trajectory, _artifact(path.parent, row['training']), reward_spec=OBJECTIVE)
            returns, total = [], 0.
            discount = OBJECTIVE.discount if OBJECTIVE.discount is not None else 1.
            for step in reversed(episode.transitions):
                total = step.reward + discount * total
                returns.append(total if episode.ending.terminated else None)
            reveals = (data.get('planning') or {}).get('reveals')
            yield dict(row=row, view=view, start=start, reveals=reveals, returns=returns[::-1],
                       steps=trajectory.transitions, targets=data['targets'])


def _study_names(config, fit):
    """Content identities seen in fitted campaigns, as the feature study collected them."""
    from .features import Vocabulary
    from .study.projection import StudyEncoder, study_catalog
    from .study.spec import FeatureSpec, StudyArchitecture
    probe = StudyEncoder(Vocabulary(()), StudyArchitecture(8, 'graph', FeatureSpec(entities=2048).to_dict(),
        study_catalog().to_dict()), action_policy='commit_decisions_v1')
    names = set()
    for episode in _episodes(config, keep=lambda row: fit(row['source_group'])):
        for step in episode['steps']:
            entries, _ = probe._rows(step.observation)
            names.update(n.definition_id for _, n, role in entries
                         if role in ('card', 'enemy', 'potion', 'relic') and n.definition_id)
    return tuple(sorted(names))


def build_model(spec, seed, *, view, names=()):
    import torch
    from .features import Vocabulary
    from .model import ActorCritic, Architecture
    if spec['kind'] == 'checkpoint':
        from .checkpoint import load_policy
        from game.agent.input_views import RAW
        teacher = load_policy(spec['checkpoint']).model
        if teacher.input_view not in (RAW, view):
            raise ValueError('Warm candidate input view cannot be converted')
        model = ActorCritic(teacher.vocabulary, teacher.architecture, action_policy=teacher.action_policy, input_view=view)
        model.load_state_dict(teacher.state_dict(), strict=True)
        return model
    if spec['kind'] == 'production':
        from .checkpoint import load_policy
        source = load_policy(spec['vocabulary_from']).model
        return ActorCritic(source.vocabulary, Architecture(spec['hidden_size'], spec['message_layers'], spec['schema']),
                           seed=seed, action_policy=source.action_policy, input_view=view)
    from .study.model import StudyActorCritic
    from .study.projection import study_catalog
    from .study.spec import FeatureSpec, StudyArchitecture
    features = FeatureSpec(spec['richness'], spec['identities'], entities=STUDY_CAPACITY)
    return StudyActorCritic(Vocabulary(tuple(names) if spec['identities'] else ()),
        StudyArchitecture(spec['hidden_size'], spec['architecture'], features.to_dict(), study_catalog().to_dict()),
        seed=seed, action_policy='commit_decisions_v1')


def encode(config, model):
    """Every searched decision, encoded by ``model``'s own public encoder."""
    from .features import encoder_for
    encoder = encoder_for(model)
    decisions = {False: [], True: []}
    evaluation = config.get('evaluation_reports')
    def fit_rows(row):
        return fitted(row['source_group'], config) or evaluation is None and holdout(row['source_group'], config)
    episodes = _episodes(config, keep=fit_rows)
    if evaluation is not None:
        import itertools
        episodes = itertools.chain(episodes, _episodes(config, evaluation, keep=lambda row: holdout(row['source_group'], config)))
    for episode in episodes:
        row, steps = episode['row'], episode['steps']
        history = getattr(encoder, 'history', None)
        if history is not None:
            # Declared starts carry no public combat anchor; history then begins unknown.
            start = episode['start'] if isinstance(episode['start'], dict) else None
            history.restore(start, steps[0].observation)
        for index, step in enumerate(steps):
            target = episode['targets'][index]
            if target['step'] != index or target['action_ref'] != step.action.ref:
                raise ValueError('Search target differs from the recorded behavior')
            if target['reason'] is None and target['simulations'] >= 1 and target['probabilities']:
                state = encoder.encode_inference(step.observation)
                refs = state.candidate_refs
                if set(target['probabilities']) != {r for r, ok in zip(refs, state.policy_mask) if ok}:
                    raise ValueError('Search target legal support differs from the candidate encoding')
                evidence = target['tree_work']['root_evidence']
                prior = tuple(evidence[r]['prior'] if r in evidence else 0. for r in refs)
                decisions[holdout(row['source_group'], config)].append(Decision(state,
                    tuple(target['probabilities'].get(r, 0.) for r in refs), prior, episode['returns'][index],
                    row['source_group'], row.get('room_kind'), row.get('encounter')))
            if history is not None and index + 1 < len(steps):
                history.observe(step.observation, step.action, steps[index + 1].observation,
                                episode['reveals'][index] if episode['reveals'] is not None else None)
    return decisions[False], decisions[True]


def _batches(decisions, size):
    for start in range(0, len(decisions), size):
        yield decisions[start:start + size]


def _targets(chunk, width):
    import torch
    targets = torch.zeros((len(chunk), width))
    for i, d in enumerate(chunk):
        targets[i, :len(d.target)] = torch.tensor(d.target)
    return targets


def measure(model, decisions, *, batch_size=64):
    """Per-decision fit to the search target; the specialist prior is the reference."""
    import torch
    from .model import collate, log_probabilities
    model.eval()
    rows = []
    with torch.inference_mode():
        for chunk in _batches(decisions, batch_size):
            batch = collate([d.state for d in chunk], vocabulary=model.vocabulary)
            logits, values = model(batch)
            logs = log_probabilities(logits, batch['mask']).masked_fill(~batch['mask'], 0.)
            for i, d in enumerate(chunk):
                target = np.asarray(d.target)
                log = logs[i, :len(target)].numpy()
                entropy = -float(sum(t * math.log(t) for t in target if t > 0))
                cross = -float((target * log).sum())
                top, prior_top = int(np.argmax(target)), int(np.argmax(d.prior))
                choice = int(np.argmax(np.where(np.asarray(batch['mask'][i, :len(target)]), log, -np.inf)))
                rows.append((cross, cross - entropy, choice == top, top != prior_top,
                             None if d.value is None else (float(values[i]) - d.value) ** 2))
    return rows


def summarize(rows, decisions):
    cross = np.array([r[0] for r in rows])
    kl = np.array([r[1] for r in rows])
    agree = np.array([r[2] for r in rows])
    changed = np.array([r[3] for r in rows])
    values = [r[4] for r in rows if r[4] is not None]
    return dict(decisions=len(rows), cross_entropy=float(cross.mean()), kl=float(kl.mean()),
                top_agreement=float(agree.mean()),
                changed_agreement=float(agree[changed].mean()) if changed.any() else None,
                kept_agreement=float(agree[~changed].mean()) if (~changed).any() else None,
                value_mse=float(np.mean(values)) if values else None)


def reference(decisions):
    """The recorded specialist prior measured against the same targets."""
    rows = []
    for d in decisions:
        target, prior = np.asarray(d.target), np.clip(np.asarray(d.prior), 1e-12, None)
        prior = prior / prior.sum()
        entropy = -float(sum(t * math.log(t) for t in target if t > 0))
        cross = -float((target * np.log(prior)).sum())
        top, prior_top = int(np.argmax(target)), int(np.argmax(prior))
        rows.append((cross, cross - entropy, prior_top == top, top != prior_top, None))
    return summarize(rows, decisions)


def train(model, fit, held, config, seed, *, progress=None):
    import torch
    from .model import collate, log_probabilities
    generator = torch.Generator(device='cpu').manual_seed(seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=config['learning_rate'], foreach=False)
    curve, by_checkpoint, started = {}, {}, time.perf_counter()
    fit_sample = fit[::max(1, len(fit) // len(held))][:len(held)]
    for epoch in range(1, config['epochs'] + 1):
        order = torch.randperm(len(fit), generator=generator).tolist()
        model.train()
        for start in range(0, len(order), config['batch_size']):
            chunk = [fit[i] for i in order[start:start + config['batch_size']]]
            batch = collate([d.state for d in chunk], vocabulary=model.vocabulary)
            logits, values = model(batch)
            logs = log_probabilities(logits, batch['mask']).masked_fill(~batch['mask'], 0.)
            policy_loss = -(_targets(chunk, logits.shape[1]) * logs).sum(-1).mean()
            available = torch.tensor([d.value is not None for d in chunk])
            returns = torch.tensor([d.value if d.value is not None else 0. for d in chunk])
            value_loss = ((values[available] - returns[available]).square().mean()
                          if available.any() else values.sum() * 0)
            loss = policy_loss + config['value_weight'] * value_loss
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite screen loss')
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), config['gradient_clip'], error_if_nonfinite=True)
            optimizer.step()
        if epoch in config['checkpoints']:
            held_rows = measure(model, held)
            by_checkpoint[str(epoch)] = dict(kl=[r[1] for r in held_rows], agreement=[bool(r[2]) for r in held_rows])
            curve[str(epoch)] = dict(holdout=summarize(held_rows, held),
                                     fit=summarize(measure(model, fit_sample), fit_sample),
                                     seconds=time.perf_counter() - started)
            if progress:
                progress(dict(phase='checkpoint', seed=seed, epoch=epoch, **{k: curve[str(epoch)]['holdout'][k]
                              for k in ('cross_entropy', 'kl', 'top_agreement', 'changed_agreement')}))
    return curve, held_rows, by_checkpoint


def _encoding_key(model):
    """Candidates whose public encoders are identical share one encoding."""
    from .study.spec import SCHEMA as STUDY
    if model.architecture.schema == STUDY:
        return ('study', model.feature_identity, type(model.encoder()).__name__)
    return ('features', model.vocabulary.identity, model.action_policy, model.architecture.schema, model.input_view)


def run_candidate(config_path, output_dir, name, *, progress=print):
    return run_candidates(config_path, output_dir, (name,), progress=progress)[0]


def run_candidates(config_path, output_dir, names, *, progress=print):
    """Fit every seed of each named candidate; write candidates/NAME.json.

    Candidates with identical public encoders reuse one encoding, so several
    architectures over one representation need memory for a single copy.
    """
    import gc
    import torch
    config_path, output = Path(config_path).resolve(), Path(output_dir).resolve()
    config = validate_config(json.loads(config_path.read_text()))
    if not names or len(set(names)) != len(names) or any(n not in config['candidates'] for n in names):
        raise ValueError('Choose distinct configured screen candidates')
    for name in names:
        if (output / 'candidates' / f'{name}.json').exists():
            raise FileExistsError(output / 'candidates' / f'{name}.json')
    torch.set_num_threads(config['threads'])
    from game.agent.provenance import implementation
    from game.agent.input_views import RAW
    from .search_run import _report_input_view
    sources = [*config['reports'], *config.get('evaluation_reports', ())]
    views = {_report_input_view(json.loads(Path(p).read_text())) for p in sources}
    if len(views) != 1:
        raise ValueError('Screen reports use different input views')
    report_view = views.pop()
    study_names = {}
    written, cache = [], dict(key=None)
    for name in names:
        spec = config['candidates'][name]
        started = time.perf_counter()
        view = RAW if spec['kind'] == 'study' else report_view
        identities = ()
        if spec['kind'] == 'study' and spec['identities']:
            if 'names' not in study_names:
                study_names['names'] = _study_names(config, lambda g: fitted(g, config))
            identities = study_names['names']
        seeds = {}
        for seed in config['seeds']:
            model = build_model(spec, seed, view=view, names=identities)
            key = _encoding_key(model)
            if cache['key'] != key:
                cache.clear()
                gc.collect()
                before = time.perf_counter()
                fit, held = encode(config, model)
                cache.update(key=key, fit=fit, held=held, seconds=time.perf_counter() - before)
                index = [dict(group=d.group, room_kind=d.room_kind, encounter=d.encounter) for d in held]
                _share_index(output, index)
                cache['index_sha256'] = hashlib.sha256(_json(index)).hexdigest()
                progress(dict(phase='encoded', candidate=name, fit=len(fit), holdout=len(held), seconds=cache['seconds']))
            fit, held = cache['fit'], cache['held']
            curve, rows, by_checkpoint = train(model, fit, held, config, seed, progress=progress)
            seeds[str(seed)] = dict(curve=curve, holdout_kl=[r[1] for r in rows],
                                    holdout_agreement=[bool(r[2]) for r in rows], by_checkpoint=by_checkpoint)
        result = dict(schema=SCHEMA, candidate=name, spec=spec, config_sha256=_sha(config_path),
            reports={p: _sha(p) for p in sources}, implementation=asdict(implementation()),
            parameters=sum(p.numel() for p in model.parameters()), feature_identity=model.feature_identity,
            input_view=view, vocabulary_names=len(model.vocabulary.names),
            fit_decisions=len(fit), holdout_decisions=len(held),
            holdout_groups=sorted({d.group for d in held}), holdout_index_sha256=cache['index_sha256'],
            reference=dict(holdout=reference(held), fit=reference(fit)), seeds=seeds,
            fit_fraction=config.get('fit_fraction', 1.), evaluation_reports=config.get('evaluation_reports'),
            fit_groups=len({d.group for d in fit}),
            encode_seconds=cache['seconds'], total_seconds=time.perf_counter() - started)
        if identities:
            result['identities_from'] = 'fitted campaigns only'
        path = output / 'candidates' / f'{name}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.with_suffix('.partial').write_bytes(_json(result))
        path.with_suffix('.partial').replace(path)
        progress(dict(phase='candidate_complete', candidate=name, seconds=result['total_seconds']))
        written.append((path, result))
    return written


def report(config_path, output_dir, *, draws=2000, seed=20261022):
    """Compare candidates on identical held-out decisions with a campaign bootstrap."""
    config_path, output = Path(config_path).resolve(), Path(output_dir).resolve()
    config = validate_config(json.loads(config_path.read_text()))
    results = {}
    for name in config['candidates']:
        path = output / 'candidates' / f'{name}.json'
        if path.exists():
            results[name] = json.loads(path.read_text())
    if not results:
        raise ValueError('No completed screen candidates')
    indexes = {r['holdout_index_sha256'] for r in results.values()}
    if len(indexes) != 1 or len({r['config_sha256'] for r in results.values()}) != 1:
        raise ValueError('Candidates measured different held-out decisions or configurations')
    first = next(iter(results.values()))
    groups = first['holdout_groups']
    last = str(config['epochs'])
    # Per-decision means over seeds, then campaign sums for resampling.
    mean_kl = {n: np.mean([s['holdout_kl'] for s in r['seeds'].values()], axis=0) for n, r in results.items()}
    mean_agree = {n: np.mean([s['holdout_agreement'] for s in r['seeds'].values()], axis=0) for n, r in results.items()}
    owner = _held_groups(output, first)
    column = {g: i for i, g in enumerate(groups)}
    membership = np.array([column[g] for g in owner])
    counts = np.bincount(membership, minlength=len(groups))
    weights = np.random.default_rng(seed).multinomial(len(groups), np.full(len(groups), 1 / len(groups)), size=draws)

    def resampled(values):
        sums = np.bincount(membership, weights=values, minlength=len(groups))
        return (weights @ sums) / (weights @ counts)

    def interval(values):
        return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))]

    def spread(values):
        values = [v for v in values if v is not None]
        return [float(np.mean(values)), float(np.min(values)), float(np.max(values))] if values else None

    table = {}
    for name, r in results.items():
        seeds = list(r['seeds'].values())
        table[name] = dict(parameters=r['parameters'], encode_seconds=r['encode_seconds'],
            curve={e: {k: (spread([s['curve'][e]['holdout'][k] for s in seeds]) or [None])[0]
                       for k in ('cross_entropy', 'kl', 'top_agreement', 'changed_agreement', 'kept_agreement')}
                   for e in map(str, config['checkpoints'])},
            fit_endpoint={k: (spread([s['curve'][last]['fit'][k] for s in seeds]) or [None])[0]
                          for k in ('cross_entropy', 'kl', 'top_agreement')},
            endpoint={k: spread([s['curve'][last]['holdout'][k] for s in seeds])
                      for k in ('cross_entropy', 'kl', 'top_agreement', 'changed_agreement', 'kept_agreement', 'value_mse')},
            kl_interval=interval(resampled(mean_kl[name])))
    comparisons = {}
    names = list(results)
    for position, base in enumerate(names):
        for name in names[position + 1:]:
            comparisons[f'{name}-{base}'] = dict(
                kl=dict(estimate=float(mean_kl[name].mean() - mean_kl[base].mean()),
                        interval_95=interval(resampled(mean_kl[name]) - resampled(mean_kl[base]))),
                top_agreement=dict(estimate=float(mean_agree[name].mean() - mean_agree[base].mean()),
                                   interval_95=interval(resampled(mean_agree[name]) - resampled(mean_agree[base]))))
    summary = dict(schema=SCHEMA, config_sha256=first['config_sha256'], candidates=table, comparisons=comparisons,
                   reference=first['reference'], holdout_decisions=first['holdout_decisions'],
                   fit_decisions=first['fit_decisions'], holdout_groups=len(groups), draws=draws,
                   missing=[n for n in config['candidates'] if n not in results])
    path = output / 'screen.json'
    path.write_bytes(_json(summary))
    return path, summary


def _share_index(output, rows):
    """Every candidate must measure the same held-out decisions in the same order."""
    path = output / 'holdout-index.json'
    data = _json(rows)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('Held-out decisions differ from an earlier candidate')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    import os
    partial = path.with_name(f'{path.name}.{os.getpid()}.partial')
    partial.write_bytes(data)
    partial.replace(path)


def _held_groups(output, result):
    """Held-out decision owners in measurement order, from the shared index file."""
    path = output / 'holdout-index.json'
    index = json.loads(path.read_text())
    if hashlib.sha256(_json(index)).hexdigest() != result['holdout_index_sha256']:
        raise ValueError('Held-out index differs from the measured candidates')
    return [row['group'] for row in index]
