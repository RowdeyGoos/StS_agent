"""Verified import of historical public prefixes into the normal Search path.

This is an explicit new derivation, not an override of CombatCorpus's source
guard. Audit uses private snapshots only here, outside the planner. Every
continuation must still equal a native replay from its original frozen opening.
Held-out test snapshots are never opened by this importer.
"""
from collections import defaultdict
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import time

from game.agent.contracts import full as f
from game.agent.headless import HeadlessAdapter
from game.agent.input_views import planning_view
from game.agent.provenance import implementation
from game.agent.runner import prepare_directories
from game.agent.search.belief import BeliefBudget
from game.agent.search.campaign import CampaignWorld
from game.agent.search.combat import CombatBelief, normalize_anchor
from game.agent.search.public_keys import action_key, public_key
from game.headless.draw_knowledge import DrawKnowledge
from game.headless.reveals import run_reveals
from game.headless.run.snapshots import restore_run
from .benchmark_suite import data, digest
from .checkpoint import publish
from .combat_corpus import CombatCorpus, _read, _uuid, _sha, _describe, public_digest

SCHEMA = 'sts_verified_search_source_v1'


def _sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _sibling(directory, name):
    if type(name) is not str or Path(name).name != name:
        raise ValueError('Expected a sibling source artifact')
    path = directory / name
    if path.is_symlink() or directory.is_symlink():
        raise ValueError('Unexpected source symlink')
    return path


def _owners(source):
    """Honor existing split reservations; a real test opening closes development."""
    path, seen, files = source, set(), []
    while True:
        if path in seen:
            raise ValueError('Cyclic combat split delegation')
        seen.add(path)
        report = _read(path)
        files.append(dict(path=str(path), sha256=_sha_file(path)))
        if path.with_name('search-test-opened.json').exists():
            raise ValueError('Development is closed after held-out test was opened')
        marker = path.with_name('test-opened.json')
        if not marker.exists():
            return path, files
        value = _read(marker)
        if (value.get('schema') != 'sts_combat_corpus_delegation_v1' or
                value.get('benchmark_test_gameplay_performed') is not False or
                value.get('parent_corpus') != 'act1_combat_corpus_v2:' + _sha_file(path) or
                value.get('delegated_splits') != ['validation', 'test']):
            raise ValueError('Development is closed after held-out test was opened')
        files.append(dict(path=str(marker), sha256=_sha_file(marker)))
        following = Path(value['destination']).absolute()
        next_report = _read(following)
        if ([r for r in report['cases'] if r['split'] == 'validation'] !=
                [r for r in next_report['cases'] if r['split'] == 'validation']):
            raise ValueError('Delegated validation population changed')
        path = following


def _state(path, sha, row):
    if path.parent.is_symlink() or path.parent.stat().st_mode & 0o077:
        raise ValueError('Source snapshots require an owner-only directory')
    snapshot = _read(path, private=True, expected_sha=sha)
    run = restore_run(snapshot)
    frame = HeadlessAdapter(run, decision_profile=f.PROFILE).observe()
    if (not hasattr(frame, 'decision') or run.combat is None or
            run.state.config.character != 'ironclad' or run.state.config.ascension != 0 or
            frame.decision.run.get('act') != 1 or run.state.config.act != row['region'] or
            public_digest(frame.decision) != row['public_state_sha256'] or
            any(row[k] != v for k, v in _describe(run, frame.decision).items())):
        raise ValueError('Imported snapshot differs from its public source case')
    if json.loads(json.dumps(run.snapshot())) != snapshot:
        raise ValueError('Imported snapshot does not round-trip under current rules')
    return run, snapshot, frame.decision


def _fresh_certificate(run, anchor, belief):
    """Verify the legacy producer's explicit freshness claim, not just its HUD."""
    world, _ = belief.sample(0)
    if (world._run.combat.player.rules.potion_pool != run.combat.player.rules.potion_pool or
            world._run.state.config.reward_potions != run.state.config.reward_potions):
        raise ValueError('Historical source ruleset contradicts native potion pool')
    if anchor['setup_stage'] != 'fresh_before_room_entry':
        return
    from game.agent.search.observed import inventory
    from game.headless.core.card_state import CardState
    from game.headless.core.snapshots import card_record
    declared = inventory(f.from_dict(anchor['initial']))
    actual = []
    for card in run.state.deck:
        record = card_record(card)
        if (record['combats_seen'] or record['permanent_damage'] or record['permanent_block'] or
                record['combat_state'] != asdict(CardState()) or 'event_data' in record):
            raise ValueError('Historical fresh inventory certificate contradicts native card history')
        actual.append((record['definition_id'], record['upgrade_level'], record['enchantment']))
    if sorted(actual, key=repr) != sorted(declared['deck'], key=repr) or any(r.data for r in run.state.relics):
        raise ValueError('Historical fresh inventory certificate contradicts native inventory')
    # Setup can advance counters. Compare the resulting state through native
    # setup, rather than copying actual private counters into the planner.
    if sorted((r.definition_id, r.counter) for r in world._run.state.relics) != sorted(
            (r.definition_id, r.counter) for r in run.state.relics):
        raise ValueError('Historical fresh inventory certificate contradicts native relic counters')


def prepare_search_source(*, corpus_path, prefix_manifest, prefix_dir, output_dir, progress=None):
    started = time.perf_counter()
    source = Path(corpus_path).absolute()
    report = _read(source)
    if report.get('schema') != 'sts_act1_combat_corpus_v2' or report.get('status') != 'complete':
        raise ValueError('Expected a complete historical combat corpus')
    owner, dependencies = _owners(source)
    manifest_path, directory = Path(prefix_manifest).absolute(), Path(prefix_dir).absolute()
    if manifest_path.is_symlink() or directory.is_symlink():
        raise ValueError('Unexpected public prefix symlink')
    manifest = json.loads(gzip.decompress(manifest_path.read_bytes()))
    if (manifest.get('schema') != 'sts_verified_combat_prefixes_v1' or
            manifest.get('source_sha256') != _sha_file(source) or manifest.get('heldout_test_opened') is not False):
        raise ValueError('Public prefixes are not bound to this source')
    dependencies.append(dict(path=str(manifest_path), sha256=_sha_file(manifest_path)))
    rows = [r for r in report['cases'] if r['split'] in ('train', 'validation')]
    bindings = {}
    for group in manifest['groups']:
        for binding in group['bindings']:
            if (binding['case_id'] in bindings or binding['split'] != group['split'] or
                    binding['source_group'] != group['source_group']):
                raise ValueError('Duplicate or cross-split prefix binding')
            bindings[binding['case_id']] = binding
    if set(bindings) != {r['case_id'] for r in rows} or len(bindings) != len(rows):
        raise ValueError('Prefixes must cover every original train/validation start')
    registries, seeds = {}, {}
    for split, path in (('train', source), ('validation', owner)):
        public = _read(path)
        private = path.parent.with_name(path.parent.name + '-private')
        registry = _read(private / 'registry.json', private=True, expected_sha=public['registry_sha256'])
        registries[split] = (private, registry['cases'])
        seeds[split] = registry['campaign_seeds']
    output = Path(output_dir).absolute()
    if output.exists():
        raise FileExistsError(output)
    output, private = prepare_directories(output, output.with_name(output.name + '-private'))
    source_identity = asdict(implementation())
    by_combat, prefix_paths, snapshots, prepared = defaultdict(list), {}, {}, []
    groups = {}
    for row in rows:
        key, binding = row['case_id'], bindings[row['case_id']]
        if (not _uuid(key) or not _uuid(row['combat_id']) or not _uuid(row['source_group']) or
                binding['split'] != row['split'] or binding['source_group'] != row['source_group'] or
                row['start_kind'] not in ('opening', 'continuation')):
            raise ValueError('Invalid source case or prefix split')
        group = groups.setdefault(row['source_group'], row['split'])
        if group != row['split']:
            raise ValueError('Campaign crosses source splits')
        native_dir, registry = registries[row['split']]
        record = registry[key]
        if record['case'] != row or record['snapshot_sha256'] != binding['source_snapshot_sha256']:
            raise ValueError('Prefix native source binding changed')
        path = _sibling(directory, binding['file'])
        if _sha_file(path) != binding['sha256']:
            raise ValueError('Public prefix artifact changed')
        prefix_paths[key] = path
        snapshots[key] = dict(path=str(native_dir / (key + '.start.json')), snapshot_sha256=record['snapshot_sha256'])
        by_combat[row['combat_id']].append(row)
    for combat_rows in by_combat.values():
        # A full dataset can contain gigabytes of expanded public history.
        # Own only one fight's prefixes at a time, never all imported graphs.
        anchors = {}
        for row in combat_rows:
            key = row['case_id']
            path = prefix_paths[key]
            if _sha_file(path) != bindings[key]['sha256']:
                raise ValueError('Public prefix changed during verification')
            value = json.loads(gzip.decompress(path.read_bytes()))
            from game.agent.search.observed import ANCHOR as HISTORICAL_ANCHOR
            if value.get('schema') != HISTORICAL_ANCHOR:
                raise ValueError('Historical import requires certified fresh-inventory public prefixes')
            anchor = normalize_anchor(value)
            if len(anchor['transitions']) != bindings[key]['prefix_decisions']:
                raise ValueError('Public prefix length changed')
            anchors[key] = anchor
        opening = [r for r in combat_rows if r['start_kind'] == 'opening']
        if len(opening) != 1 or any(tuple(r[k] for k in ('source_group', 'split', 'encounter')) !=
                tuple(opening[0][k] for k in ('source_group', 'split', 'encounter')) for r in combat_rows):
            raise ValueError('Combat requires one opening and one split owner')
        opening = opening[0]
        key = opening['case_id']
        anchor = max((anchors[r['case_id']] for r in combat_rows), key=lambda a: len(a['transitions']))
        run, _, root = _state(Path(snapshots[key]['path']), snapshots[key]['snapshot_sha256'], opening)
        if run.state.seed != seeds[opening['split']][opening['source_group']]:
            raise ValueError('Combat campaign seed binding changed')
        belief = CombatBelief(anchors[key], root, seed=0, budget=BeliefBudget(1, 4096, 30.))
        if belief.recover().reason is not None:
            raise ValueError('Public opening cannot be reconstructed under current rules')
        _fresh_certificate(run, anchors[key], belief)
        # Audit only: exact native state, no resampling or conditional RNG.
        # This world is never passed to a planner or saved as a belief particle.
        world = CampaignWorld(run, DrawKnowledge(), f.from_dict(anchor['opening']))
        del run.combat.player.deck.rng.draw_knowledge
        checkpoints = {}
        for row in combat_rows:
            public = anchors[row['case_id']]
            count = len(public['transitions'])
            if (count in checkpoints or {k: v for k, v in public.items() if k != 'transitions'} !=
                    {k: v for k, v in anchor.items() if k != 'transitions'} or
                    public['transitions'] != anchor['transitions'][:count] or
                    (row['start_kind'] == 'opening') != (count == 0)):
                raise ValueError('Inconsistent public combat prefixes')
            checkpoints[count] = row
        for index in range(len(anchor['transitions']) + 1):
            expected = f.from_dict(anchor['opening'] if index == 0 else anchor['transitions'][index - 1]['successor'])
            actual = world.project()
            if public_key(actual) != public_key(planning_view(expected)):
                raise ValueError('Native replay public observation changed')
            if index in checkpoints:
                row = checkpoints[index]
                record = snapshots[row['case_id']]
                _, snapshot, _ = _state(Path(record['path']), record['snapshot_sha256'], row)
                if json.loads(json.dumps(run.snapshot())) != snapshot:
                    raise ValueError('Native prefix replay differs from frozen continuation')
                raw = gzip.compress(data(anchors[row['case_id']]), mtime=0)
                sha = publish(output / (row['case_id'] + '.planning.json.gz'), raw)
                prepared.append(dict(row, planning_sha256=sha))
            if index == len(anchor['transitions']):
                break
            transition = anchor['transitions'][index]
            action = next(a for a in expected.candidates if a.ref == transition['action_ref'])
            with run_reveals(run) as journal:
                world.step(actual, action_key(expected, action))
            if journal.events != transition['reveals']:
                raise ValueError('Native replay public reveals changed')
        if progress:
            progress(len(prepared), len(rows))
    if asdict(implementation()) != source_identity:
        raise ValueError('Implementation changed during source verification')
    registry_sha = publish(private / 'registry.json', data(snapshots), private=True)
    result = dict(schema=SCHEMA, status='complete', implementation=source_identity,
        source=str(source), source_sha256=_sha_file(source), validation_owner=str(owner),
        dependencies=dependencies, registry_sha256=registry_sha, cases=prepared,
        verification='current public setup + exact native opening-to-continuation replay + public reveals',
        original_implementation=report['implementation'], prefix_implementation=manifest['implementation'],
        heldout_test_opened=False, total_seconds=time.perf_counter() - started)
    path = output / 'search-source.json'
    publish(path, data(result))
    return path, result


class VerifiedSearchSource:
    def __init__(self, path, *, expected=None):
        self.path = Path(path).absolute()
        self.report = _read(self.path)
        report = self.report
        self.identity = SCHEMA + ':' + _sha_file(self.path)
        if (report.get('schema') != SCHEMA or report.get('status') != 'complete' or
                report.get('implementation') != asdict(implementation()) or
                report.get('heldout_test_opened') is not False or expected not in (None, self.identity)):
            raise ValueError('Search source requires current verified rules and exact identity')
        owner, dependencies = _owners(Path(report['source']))
        if str(owner) != report['validation_owner'] or dependencies != report['dependencies'][:-1]:
            raise ValueError('Source split reservations changed')
        for binding in report['dependencies']:
            path = Path(binding['path'])
            if path.is_symlink() or _sha_file(path) != binding['sha256']:
                raise ValueError('Imported source provenance changed')
        self.cases = {r['case_id']: r for r in report['cases']}
        original = _read(Path(report['source']))
        rows = [r for r in original['cases'] if r['split'] in ('train', 'validation')]
        if (len(self.cases) != len(report['cases']) or set(self.cases) != {r['case_id'] for r in rows} or
                any({k: v for k, v in self.cases[r['case_id']].items() if k != 'planning_sha256'} != r for r in rows)):
            raise ValueError('Verified source population changed')
        private = self.path.parent.with_name(self.path.parent.name + '-private')
        if private.is_symlink() or private.stat().st_mode & 0o077:
            raise ValueError('Verified source registry requires owner-only permissions')
        self.registry = _read(private / 'registry.json', private=True, expected_sha=report['registry_sha256'])
        if set(self.registry) != set(self.cases):
            raise ValueError('Verified source registry population changed')

    def split(self, split):
        if split not in ('train', 'validation'):
            raise ValueError('Imported search sources do not open held-out test')
        return [r for r in self.cases.values() if r['split'] == split]

    def restore(self, key, *, split):
        row = self.cases[key]
        if row['split'] != split:
            raise ValueError('Combat case belongs to another split')
        if split == 'validation':
            _owners(Path(self.report['source']))
        record = self.registry[key]
        return _state(Path(record['path']), record['snapshot_sha256'], row)[0]

    def planning_start(self, key, *, split):
        row = self.cases[key]
        if row['split'] != split:
            raise ValueError('Planning receipt belongs to another split')
        path = _sibling(self.path.parent, key + '.planning.json.gz')
        if _sha_file(path) != row['planning_sha256']:
            raise ValueError('Verified public planning receipt changed')
        return json.loads(gzip.decompress(path.read_bytes()))


def open_search_source(path, *, expected=None):
    schema = _read(Path(path)).get('schema')
    cls = VerifiedSearchSource if schema == SCHEMA else CombatCorpus
    return cls(path, expected=expected)
