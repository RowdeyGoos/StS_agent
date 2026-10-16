"""Verified study derivative and an explicit, single held-out reservation.

The historical corpus and its hashes remain untouched. Training/development
reuse the current-source native replay verifier. Test snapshot bytes are not
read here until all finalists have been registered at the existing split owner.
"""
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import time

from game.agent.contracts import full as f
from game.agent.provenance import implementation
from ..benchmark_suite import data
from ..checkpoint import publish
from ..combat_corpus import _read
from ..search_sources import (prepare_search_source, VerifiedSearchSource, _owners, _state, _sha_file,
                              development_context)
from .history import PublicHistory
from .projection import study_catalog
from .spec import HISTORY, digest

SOURCE = 'sts_verified_feature_study_source_v1'
DEVELOPMENT_SOURCE = 'sts_verified_development_feature_source_v1'
RESERVATION = 'sts_feature_study_test_reservation_v1'


def prepare_source(*, corpus_path, prefix_manifest, prefix_dir, output_dir, progress=None,
                   development_parent=None):
    started = time.perf_counter()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    path, verified = prepare_search_source(corpus_path=corpus_path, prefix_manifest=prefix_manifest,
        prefix_dir=prefix_dir, output_dir=output/'verified', progress=progress,
        development_parent=development_parent)
    source = VerifiedSearchSource(path)
    catalog = study_catalog()
    types = {e.definition_id: next(v.value for v in e.fields if v.key == 'catalog.card_type')
             for e in catalog.entries if e.kind == 'card'}
    supplements = {}
    for row in source.cases.values():
        anchor = source.planning_start(row['case_id'], split=row['split'])
        record=source.registry[row['case_id']]
        # Bind to the fresh public adapter used by Gym/evaluation. The verified
        # prefix additionally has attachment-only action history, which is
        # reconstructed separately and is not native snapshot state.
        public=_state(Path(record['path']),record['snapshot_sha256'],row)[2]
        history = PublicHistory(types, {(e.kind, e.definition_id): e for e in catalog.entries})
        history.restore(anchor, public)
        supplements[row['case_id']] = history.export(public)
    history_sha = publish(output/'public-history.json.gz', gzip.compress(data(supplements), mtime=0))
    context = development_context(development_parent) if development_parent is not None else None
    owner, dependencies = ((Path(context['owner']), context['dependencies']) if context is not None else
                           _owners(Path(corpus_path).resolve()))
    original = _read(Path(corpus_path))
    owner_report = _read(owner)
    if ([r for r in original['cases'] if r['split'] == 'test'] !=
            [r for r in owner_report['cases'] if r['split'] == 'test']):
        raise ValueError('Held-out population changed across source ownership')
    result = dict(schema=DEVELOPMENT_SOURCE if context is not None else SOURCE,
        implementation=asdict(implementation()), status='complete',
        verified_source=str(path), verified_sha256=_sha_file(path), history_sha256=history_sha,
        original=str(Path(corpus_path).resolve()), original_sha256=_sha_file(corpus_path),
        owner=str(owner), ownership=dependencies,
        cases=[r for r in original['cases'] if r['split'] in ('train', 'validation')] if context is not None else original['cases'],
        original_implementation=original['implementation'], test_gameplay_opened=False,
        verification_seconds=time.perf_counter()-started,
        verification=verified['verification'])
    if context is not None:
        result.update(development_context=context, prior_test_exposure=True, test_access=False)
    publish(output/'source.json', data(result))
    return output/'source.json', result


class StudySource:
    def __init__(self, path, *, expected=None, reservation=None):
        self.path = Path(path).resolve()
        self.report = _read(self.path)
        r = self.report
        self.development_only = r.get('schema') == DEVELOPMENT_SOURCE
        self.identity = r.get('schema', '') + ':' + _sha_file(self.path)
        if self.development_only and reservation is not None:
            raise ValueError('Development-only sources cannot reserve or open TEST')
        if (r.get('schema') not in (SOURCE, DEVELOPMENT_SOURCE) or r.get('status') != 'complete'
                or r.get('implementation') != asdict(implementation()) or expected not in (None, self.identity)
                or _sha_file(r['original']) != r['original_sha256']
                or _sha_file(r['verified_source']) != r['verified_sha256']):
            raise ValueError('Study source identity or implementation changed')
        self.cases = {row['case_id']: row for row in r['cases']}
        original = _read(Path(r['original']))
        expected_cases = ([row for row in original['cases'] if row['split'] in ('train', 'validation')]
                          if self.development_only else original['cases'])
        if r['cases'] != expected_cases or len(self.cases) != len(r['cases']):
            raise ValueError('Study changed the original cases or split population')
        self.reservation = reservation
        if reservation is None:
            if self.development_only:
                context = development_context(r['development_context']['parent_manifest'])
                if (context != r['development_context'] or context['source'] != r['original']
                        or r.get('prior_test_exposure') is not True or r.get('test_access') is not False):
                    raise ValueError('Development-only source provenance changed')
                owner, dependencies = Path(context['owner']), context['dependencies']
            else:
                owner, dependencies = _owners(Path(r['original']))
            if str(owner) != r['owner'] or dependencies != r['ownership']:
                raise ValueError('Study split ownership changed')
            self.verified = VerifiedSearchSource(r['verified_source'])
            if self.verified.development_only != self.development_only:
                raise ValueError('Study and verified source scopes disagree')
            self.registry = self.verified.registry
        else:
            # Test workers validate the frozen complete reservation, rather
            # than asking the development-only verifier to ignore a test lock.
            binding = _read(Path(reservation))
            if (binding.get('schema') != RESERVATION or binding.get('source') != self.identity
                    or _read(Path(r['owner']).with_name('test-opened.json')) != binding):
                raise ValueError('Held-out access requires the exact registered study reservation')
            for dependency in r['ownership']:
                if _sha_file(dependency['path']) != dependency['sha256']:
                    raise ValueError('Original split ownership provenance changed')
            owner = Path(r['owner'])
            owner_report = _read(owner)
            private = owner.parent.with_name(owner.parent.name + '-private')
            self.registry = _read(private/'registry.json', private=True,
                expected_sha=owner_report['registry_sha256'])['cases']
            self.private = private
            self.binding = binding
        history_path = self.path.with_name('public-history.json.gz')
        if _sha_file(history_path) != r['history_sha256']:
            raise ValueError('Verified public history changed')
        self.histories = json.loads(gzip.decompress(history_path.read_bytes()))
        if set(self.histories) != {k for k, row in self.cases.items() if row['split'] != 'test'}:
            raise ValueError('Public history population changed')

    def split(self, split):
        if getattr(self, 'development_only', False) and split == 'test':
            raise ValueError('Development-only sources cannot open TEST')
        if split not in ('train', 'validation', 'test'):
            raise ValueError('Invalid study split')
        if self.reservation is not None and split != 'test':
            raise ValueError('Development is closed after test reservation')
        return [r for r in self.cases.values() if r['split'] == split]

    def restore(self, key, *, split):
        if split not in ('train', 'validation') or self.reservation is not None:
            raise ValueError('Training source cannot open held-out gameplay')
        if not getattr(self, 'development_only', False) and (Path(self.report['owner']).with_name('test-opened.json').exists()
                or Path(self.report['owner']).with_name('search-test-opened.json').exists()):
            raise ValueError('All development is closed after held-out reservation')
        return self.verified.restore(key, split=split)

    def history_start(self, key, *, split):
        if self.reservation is not None or self.cases[key]['split'] != split or split == 'test':
            raise ValueError('History supplement belongs to another split')
        return self.histories[key]

    def restore_test(self, key, *, policy, mode, repeat):
        if getattr(self, 'development_only', False):
            raise ValueError('Development-only sources cannot open TEST')
        if (self.reservation is None or self.cases[key]['split'] != 'test'
                or self.cases[key]['start_kind'] != 'opening'
                or key not in self.binding['cases']
                or policy not in self.binding['policies']
                or [mode, repeat] not in self.binding['modes']):
            raise ValueError('Unregistered held-out study evaluation')
        row, record = self.cases[key], self.registry[key]
        if record['case'] != row:
            raise ValueError('Held-out case ownership changed')
        output = Path(self.binding['execution_output'])
        if not (output/'plan.json').is_file():
            raise ValueError('Held-out execution plan must be published first')
        attempts = output/'attempts'
        attempts.mkdir(exist_ok=True)
        attempt = dict(case_id=key, policy=policy, mode=mode, repeat=repeat)
        publish(attempts/(digest(attempt)+'.json'), data(attempt))
        return _state(self.private/(key+'.start.json'), record['snapshot_sha256'], row)[0]


def reserve_test(source, path, *, policies, manifest_sha256, limits, execution_output):
    """One atomic lock at the actual historical owner, before test restoration."""
    if getattr(source, 'development_only', False):
        raise ValueError('Development-only sources cannot reserve or open TEST')
    if source.reservation is not None:
        raise ValueError('Expected a development source before reservation')
    if len(policies) != 8 or not {'heuristic', 'random_legal'} <= set(policies):
        raise ValueError('Register all six finalist seeds and both controls together')
    for name, policy in policies.items():
        if name not in ('heuristic', 'random_legal'):
            if _sha_file(policy['checkpoint']) != policy['sha256']:
                raise ValueError('Finalist checkpoint changed before reservation')
    for kind in ('identity', 'no_vocabulary'):
        rows = [p for name,p in policies.items() if name.startswith(kind+'-')]
        if len(rows) != 3 or len({p['learner_seed'] for p in rows}) != 3 or len({p['configuration_id'] for p in rows}) != 1:
            raise ValueError('Each finalist requires all three distinct learner seeds')
    if ({p['learner_seed'] for n,p in policies.items() if n.startswith('identity-')} !=
            {p['learner_seed'] for n,p in policies.items() if n.startswith('no_vocabulary-')}):
        raise ValueError('Finalists must use paired learner seeds')
    if limits != dict(max_decisions=512,time_limit_seconds=120.):
        raise ValueError('Test limits differ from the approved study')
    binding = dict(schema=RESERVATION, source=source.identity, manifest_sha256=manifest_sha256,
        policies=policies, modes=[['greedy', 0], ['sampled', 0], ['sampled', 1]], limits=limits,
        execution_output=str(Path(execution_output).resolve()),
        cases=sorted(r['case_id'] for r in source.split('test') if r['start_kind'] == 'opening'),
        no_reselection=True, no_further_training=True)
    lock = Path(source.report['owner']).with_name('test-opened.json')
    publish(Path(path), data(binding))
    # No overwriting, bypass or resetting an existing reservation.
    publish(lock, data(binding))
    return binding
