"""Local MLflow view over canonical reports, with an idempotent lineage index."""
import json
import os
from pathlib import Path
import sqlite3
import time
import warnings

from . import records as r


def local_store(path):
    path = Path(path).absolute()
    if not r.public_path(path):
        raise ValueError('Tracking store must be a local path without symlinks or private trees')
    path.mkdir(parents=True, exist_ok=True)
    path = path.resolve()
    for name in ('mlflow.db', 'index.sqlite', 'artifacts'):
        target = path/name
        if target.is_symlink():
            raise ValueError('Tracking destinations must not be symlinks')
    # A resumed local artifact store may already have nested run directories.
    # Refuse symlinks there too, before MLflow is allowed to open any artifact.
    artifacts = path/'artifacts'
    if artifacts.exists():
        for root, directories, files in os.walk(artifacts, followlinks=False):
            if any((Path(root)/name).is_symlink() for name in directories+files):
                raise ValueError('Tracking artifact tree contains a symlink')
    return path


def client_for(path):
    # Explicit local destination, independent of ambient MLFLOW_TRACKING_URI.
    # Set before importing MLflow; no telemetry, autologging or remote exporter.
    os.environ['MLFLOW_DISABLE_TELEMETRY'] = 'true'
    os.environ['MLFLOW_DISABLE_AGENT_HINT'] = 'true'
    from mlflow import MlflowClient
    return MlflowClient(tracking_uri='sqlite:///'+str(path/'mlflow.db'))


class TrackingStore:
    """Parent-process writer. The index never contains engine/private resume data.

    A transaction serializes concurrent importers. MLflow operations may outlive
    a rolled-back index transaction, so run lookup and metric writes are also
    idempotent at the MLflow boundary, including after a process interruption.
    """

    def __init__(self, path, *, experiment='StS experiments', name=None, inspector_url=None):
        self.path = local_store(path)
        self.client = client_for(self.path)
        self.experiment_name, self.name = experiment, name
        self.inspector_url = inspector_url
        if inspector_url:
            from urllib.parse import urlsplit
            url = urlsplit(inspector_url)
            if url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost', '::1') or url.username or url.password:
                raise ValueError('Inspector links must point to a local HTTP server')
        experiment_record = self.client.get_experiment_by_name(experiment)
        if experiment_record:
            from urllib.parse import unquote, urlsplit
            location = urlsplit(experiment_record.artifact_location)
            if (location.scheme != 'file' or location.netloc or
                    Path(unquote(location.path)).resolve() != self.path/'artifacts'):
                raise ValueError('Existing experiment artifacts are not in this local store')
        self.experiment_id = (experiment_record.experiment_id if experiment_record else
            self.client.create_experiment(experiment, artifact_location=(self.path/'artifacts').as_uri()))
        self.db = sqlite3.connect(self.path/'index.sqlite', timeout=60)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS segments (
            id TEXT PRIMARY KEY, path TEXT NOT NULL, run TEXT NOT NULL, kind TEXT NOT NULL,
            signature TEXT, start INTEGER, end INTEGER, elapsed REAL, source_sha TEXT,
            status TEXT, experiment TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS checkpoints (
            sha TEXT NOT NULL, segment TEXT NOT NULL, run TEXT NOT NULL, step INTEGER NOT NULL,
            resume TEXT, endpoint INTEGER NOT NULL, PRIMARY KEY(sha, segment));
          CREATE INDEX IF NOT EXISTS checkpoint_resume ON checkpoints(resume);
          CREATE TABLE IF NOT EXISTS checkpoint_models (
            record TEXT PRIMARY KEY, run TEXT NOT NULL, sha TEXT NOT NULL,
            step INTEGER NOT NULL, model TEXT NOT NULL, UNIQUE(run, sha, step));
          CREATE TABLE IF NOT EXISTS model_segments (
            segment TEXT PRIMARY KEY, source_sha TEXT NOT NULL);
        ''')
        self._histories, self._bundles = {}, {}
        self._view_metric_keys = set()
        self._views_dirty = True

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _run(self, key, name, tags):
        matches = self.client.search_runs([self.experiment_id],
            filter_string="tags.`sts.record` = '"+key+"'", max_results=2)
        if len(matches) > 1:
            raise ValueError('Ambiguous tracking record')
        if matches:
            self._local_run(matches[0].info.run_id)
            return matches[0].info.run_id
        return self.client.create_run(self.experiment_id, tags={
            'mlflow.runName': name, 'sts.record': key, 'sts.evidence': 'reported_metadata',
            'sts.clock': 'Imported timestamps are ingestion times; metric steps carry decisions or seconds.',
            **{k: str(v) for k, v in tags.items()}}).info.run_id

    def _local_run(self, run):
        from urllib.parse import unquote, urlsplit
        location = urlsplit(self.client.get_run(run).info.artifact_uri)
        path = Path(unquote(location.path))
        if (location.scheme != 'file' or location.netloc or not r.public_path(path)
                or not path.resolve().is_relative_to(self.path/'artifacts')):
            raise ValueError('Run artifact destination is outside the local tracking store')

    def _metrics(self, run, step, values):
        from mlflow.entities import Metric
        pending = []
        timestamp = int(time.time()*1000)
        for key, value in r.numbers(values).items():
            cache = (run, key)
            if cache not in self._view_metric_keys:
                self._view_metric_keys.add(cache)
                self._views_dirty = True
            if cache not in self._histories:
                self._histories[cache] = {(m.step, m.value) for m in self.client.get_metric_history(run, key)}
            point = (step, value)
            if point not in self._histories[cache]:
                pending.append(Metric(key, value, timestamp, step))
        for offset in range(0, len(pending), 1000):
            batch = pending[offset:offset+1000]
            self.client.log_batch(run, metrics=batch)
            for metric in batch:
                self._histories[(run, metric.key)].add((metric.step, metric.value))

    def _params(self, run, values):
        from mlflow.entities import Param
        existing = self.client.get_run(run).data.params
        values = r.params(values)
        # Params are immutable. Genuine continuations must agree; per-segment
        # variation belongs in the attached source report, not rewritten params.
        changed = {k for k in existing.keys() & values.keys() if existing[k] != values[k]}
        if changed:
            raise ValueError('Tracking parameters changed: '+', '.join(sorted(changed)))
        pending = [Param(k, v) for k, v in values.items() if k not in existing]
        for offset in range(0, len(pending), 100):
            self.client.log_batch(run, params=pending[offset:offset+100])

    def _bundle(self, path, sha):
        key = (str(path), sha)
        if key not in self._bundles:
            self._bundles[key] = r.bundle(path, sha)
        return self._bundles[key]

    def _notes(self, run, path, extra=''):
        tags = self.client.get_run(run).data.tags
        extra = extra or tags.get('sts.notes_detail', '')
        inspector_url = self.inspector_url or tags.get('sts.inspector_url')
        notes = ('Source reports and checkpoints remain the canonical records. '
                 'Importing historical metrics does not revalidate gameplay.\n\n'
                 'Latest report: `'+str(path)+'`\n\n'+extra)
        if inspector_url:
            notes += '\n\n[Open decision inspector]('+inspector_url+')'
            self.client.set_tag(run, 'sts.inspector_url', inspector_url)
        if extra:
            self.client.set_tag(run, 'sts.notes_detail', extra)
        start, end = '<!-- sts-tracking:start -->', '<!-- sts-tracking:end -->'
        generated = start+'\n'+notes+'\n'+end
        previous = tags.get('mlflow.note.content', '')
        if start in previous and end in previous.split(start, 1)[1]:
            before, remaining = previous.split(start, 1)
            _, after = remaining.split(end, 1)
            notes = before+generated+after
        elif previous.strip() in ('', notes.strip()):
            notes = generated
        else:
            # Unmarked descriptions are user-owned. Never discard them when a
            # subsequent training segment or historical evaluation is imported.
            notes = previous+'\n\n'+generated
        self.client.set_tag(run, 'mlflow.note.content', notes)

    def import_report(self, path, report=None):
        path = Path(path).absolute()
        if not r.public_path(path):
            raise ValueError('Only public report paths may be tracked')
        live = report is not None
        report = report if live else r.read_json(path)
        if live and report.get('status') != 'running' and path.exists():
            if r.identity(report) != r.identity(r.read_json(path)):
                raise ValueError('Published report differs from tracking snapshot')
            source_sha = r.digest(path)
        else:
            source_sha = r.identity(report) if live else r.digest(path)
        key = r.identity({'path': str(path), 'experiment': self.experiment_name})
        self.db.execute('BEGIN IMMEDIATE')
        try:
            previous = self.db.execute('SELECT * FROM segments WHERE id=?', (key,)).fetchone()
            if (previous and previous['source_sha'] == source_sha and previous['kind'] != 'evaluation'
                    and not previous['status'].startswith('sync_pending:')):
                self._checkpoint_models(path, report, key, source_sha, previous['run'], previous['kind'])
                if self.inspector_url:
                    last_path = self.client.get_run(previous['run']).data.tags.get('sts.last_report', str(path))
                    self._notes(previous['run'], last_path)
                self.db.commit()
                self._refresh_views_after_report()
                return {'path': str(path), 'run_id': previous['run'], 'status': 'unchanged'}
            if (previous and previous['source_sha'] != source_sha and
                    previous['status'] not in ('running', 'sync_pending:running')):
                raise ValueError('A completed report changed; keep historical sources immutable')
            schema = report.get('schema')
            if schema in ('sts_ppo_report_v1', 'sts_imitation_report_v1'):
                result = self._training(path, report, key, source_sha, previous)
            else:
                normalized = r.prepare_evaluation(path, report)
                result = self._evaluation(path, normalized, key, source_sha, previous)
            self.db.commit()
            self._refresh_views_after_report()
            return result
        except BaseException:
            self.db.rollback()
            self._histories.clear()
            raise

    def refresh_views(self):
        """Apply reusable view templates without importing reports or changing runs."""
        from .views import sync_views
        self.db.execute('BEGIN IMMEDIATE')
        try:
            result = sync_views(self.client, self.experiment_id)
            self.db.commit()
            self._views_dirty = False
            return result
        except BaseException:
            self.db.rollback()
            raise

    def _refresh_views_after_report(self):
        if not self._views_dirty:
            return
        try:
            self.refresh_views()
        except Exception as error:
            # The report and its metrics have already committed. An optional
            # layout failure must not change that result, including under -Werror.
            message = (f'MLflow saved views were not refreshed: {error}. '
                       'Retry with sts-agent-track views for this experiment.')
            try:
                warnings.warn(message, RuntimeWarning)
            except Exception:
                pass

    def _checkpoint_artifacts(self, path, report, points=None):
        points = list(r.training_points(report)) if points is None else points
        start = report.get('start_decisions', report.get('start_update', 0))
        end = points[-1][0] if points else start
        rows = [(path.parent/'initial.sts-model', report['initial_sha256'], start, False)]
        for (step, _, _), entry in zip(points, report.get('iterations', [])):
            if entry.get('checkpoint_sha256'):
                rows.append((path.parent/f'update-{entry["iteration"]:05}.sts-model',
                             entry['checkpoint_sha256'], step, False))
        if report.get('final_sha256'):
            rows.append((path.parent/'final.sts-model', report['final_sha256'], end, True))
        else:
            rows[-1] = (*rows[-1][:3], True)
        artifacts = [{'path': str(p), 'sha256': sha, 'step': step, 'manifest': self._bundle(p, sha)}
                     for p, sha, step, _ in rows]
        return artifacts, rows

    def _checkpoint_models(self, path, report, key, source_sha, run, kind, artifacts=None):
        from .models import CheckpointCatalog
        catalog = CheckpointCatalog(self)
        previous = self.db.execute('SELECT source_sha FROM model_segments WHERE segment=?', (key,)).fetchone()
        if previous and previous['source_sha'] == source_sha and not self.inspector_url:
            catalog.reconcile(run)
            return
        self._local_run(run)
        if artifacts is None:
            artifacts, _ = self._checkpoint_artifacts(path, report)
        boundaries = catalog.boundaries(run)
        catalog.sync(run, [item for item in artifacts if (item['sha256'], item['step']) in boundaries], kind)
        catalog.reconcile(run)
        self.db.execute('INSERT OR REPLACE INTO model_segments VALUES (?,?)', (key, source_sha))

    def curate_models(self, *, keep=(), release=()):
        from .models import CheckpointCatalog
        catalog = CheckpointCatalog(self)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            for paths, retained in ((keep, True), (release, False)):
                for path in paths:
                    path = Path(path).absolute()
                    if not r.public_path(path):
                        raise ValueError('Select a public local checkpoint')
                    sha = r.digest(path)
                    if not catalog.promote(sha):
                        raise ValueError('Checkpoint has no imported training provenance in this experiment')
                    rows = self.db.execute('''SELECT model FROM checkpoint_models WHERE sha=? AND run IN
                        (SELECT run FROM segments WHERE experiment=?)''', (sha, self.experiment_id))
                    for row in rows:
                        self.client.set_logged_model_tags(row['model'], {'sts.catalog_keep': str(retained).lower()})
            result = catalog.reconcile()
            self.db.commit()
            return result
        except BaseException:
            self.db.rollback()
            raise

    def _training(self, path, report, key, source_sha, previous):
        ppo = report['schema'] == 'sts_ppo_report_v1'
        kind = 'ppo' if ppo else 'imitation'
        initial = self._bundle(path.parent/'initial.sts-model', report['initial_sha256'])
        config = {'algorithm': kind, 'architecture': initial.get('architecture'),
            'feature_identity': initial.get('feature_identity'), 'reward': initial.get('reward_spec'),
            'action_policy': initial.get('action_policy', 'all_legal_v1'),
            'implementation': report.get('implementation', initial.get('implementation')),
            'runtime': report.get('runtime'), 'collection': report.get('collection'),
            'experiment': report.get('experiment'), 'learner_config': report.get('learner_config'),
            'corpus_identity': report.get('corpus_identity'), 'validation_identity': report.get('validation_identity')}
        signature = r.identity(config)
        start = report.get('start_decisions', report.get('start_update', 0))
        points = list(r.training_points(report))
        end = points[-1][0] if points else start
        artifacts, checkpoint_rows = self._checkpoint_artifacts(path, report, points)
        resumed = report.get('initialization', {}).get('resumed') is True
        parent, lineage = None, 'new'
        if previous:
            if previous['signature'] != signature or previous['start'] != start or end < previous['end']:
                raise ValueError('Changed or regressing training segment')
            run = previous['run']
        else:
            resume = initial.get('resume_state_sha256')
            parent_identity = report.get('initialization', {}).get('checkpoint', '') or ''
            # Imitation's historical manifest has no optimizer-state digest.
            # New reports explicitly name the bundle successfully restored by
            # restore_learner; do not infer old imitation resumes from weights.
            match_field, match_value = ('resume', resume) if ppo else ('sha', parent_identity.rsplit(':', 1)[-1])
            candidates = self.db.execute('''SELECT DISTINCT c.run, s.id, s.end, s.signature
                FROM checkpoints c JOIN segments s ON c.segment=s.id
                WHERE c.'''+match_field+'''=? AND c.step=? AND c.endpoint=1 AND s.experiment=?
                AND s.end>s.start AND s.status!='running' AND s.status NOT LIKE 'sync_pending:%' ''',
                (match_value, start, self.experiment_id)).fetchall() if resumed and match_value else []
            candidates = [row for row in candidates if row['signature'] == signature]
            if len(candidates) == 1:
                parent = candidates[0]['run']
                tail = self.db.execute('SELECT MAX(end) FROM segments WHERE run=?', (parent,)).fetchone()[0]
                claimed = self.db.execute('''SELECT COUNT(*) FROM segments WHERE run=? AND id!=?
                    AND start>=? AND (end>start OR status='running' OR status LIKE 'sync_pending:%')''',
                    (parent, candidates[0]['id'], start)).fetchone()[0]
                if tail == start and not claimed:
                    run, lineage = parent, 'exact_resume'
                else:
                    lineage = 'fork'
            elif resumed:
                lineage = 'unresolved_resume' if not candidates else 'ambiguous_resume'
            if lineage != 'exact_resume':
                run = self._run(key, self.name or _name(path), {'sts.kind': kind, 'sts.lineage': lineage,
                    'sts.x_axis': 'decisions' if ppo else 'optimizer_updates',
                    'sts.seed': 'private; identity retained in exact-resume digest',
                    **({'sts.parent_run': parent} if parent else {})})
        self._local_run(run)
        other_elapsed = self.db.execute('SELECT COALESCE(SUM(elapsed),0) FROM segments WHERE run=? AND id!=?',
                                       (run, key)).fetchone()[0]
        segment_elapsed = report.get('total_seconds', points[-1][1] if points and points[-1][1] is not None else 0.)
        # Durable ownership before any metric side effect. A failed/resumed
        # import must retain its curve assignment even if a sibling is imported
        # before retry. The pending reservation also blocks competing live tails.
        self.db.execute('INSERT OR REPLACE INTO segments VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (key, str(path), run, kind, signature, start, end, segment_elapsed, source_sha,
             'sync_pending:'+report.get('status', 'unknown'), self.experiment_id))
        self.db.commit()
        self.db.execute('BEGIN IMMEDIATE')
        self._histories.clear()
        self._params(run, config)
        self.client.set_tag(run, 'sts.sync_status', 'pending')
        for item, (_, sha, step, endpoint) in zip(artifacts, checkpoint_rows):
            self.db.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?,?,?,?,?)',
                (sha, key, run, step, item['manifest'].get('resume_state_sha256'), int(endpoint)))
        self.client.set_tag(run, 'sts.report_status', report.get('status', 'unknown'))
        self.client.set_tag(run, 'sts.last_report', str(path))
        self.client.set_tag(run, 'sts.last_checkpoint', report.get('final_sha256', report['initial_sha256']))
        for step, elapsed, metrics in points:
            if elapsed is not None:
                seconds = other_elapsed+elapsed
                metrics['system/training_seconds'] = seconds
                self._metrics(run, int(seconds), {'by_seconds/'+k: v for k, v in metrics.items()
                                                if k.startswith(('train/', 'ppo/'))})
            self._metrics(run, step, metrics)
        if 'summary' in report:
            self._metrics(run, end, r.numbers(report['summary'], 'segment/'))
        for phase in ('before', 'after'):
            for split, metrics in report.get(phase, {}).items():
                self._metrics(run, start if phase == 'before' else end,
                              r.numbers(metrics, 'imitation/'+split+'/'))
        if report.get('status') != 'running':
            self._metrics(run, end, {'system/cumulative_wall_seconds': other_elapsed+segment_elapsed,
                **r.numbers({'peak_process_rss_bytes': report.get('peak_process_rss_bytes')}, 'system/')})
        artifact_dir = 'segments/'+key[:16]
        self.client.log_dict(run, artifacts, artifact_dir+'/checkpoints.json')
        self.client.log_dict(run, {'path': str(path), 'sha256': source_sha, 'live_snapshot': report.get('status') == 'running'},
                             artifact_dir+'/source.json')
        self.client.log_dict(run, report, artifact_dir+'/report.json')
        if report.get('status') != 'running':
            final = checkpoint_rows[-1][0]
            self.client.log_artifact(run, str(final), artifact_path=artifact_dir)
        self._checkpoint_models(path, report, key, source_sha, run, kind, artifacts)
        self._notes(run, path, 'Charts use cumulative processed decisions (imitation: optimizer updates). '
            '`by_seconds/*` charts use measured training seconds as their step axis. '
            'Per-update timing excludes unmeasured checkpoint overhead within that segment; '
            '`system/cumulative_wall_seconds` includes complete segment wall time. '
            'Failures and previous segment statuses remain in the segment report artifacts.')
        self.db.execute('INSERT OR REPLACE INTO segments VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (key, str(path), run, kind, signature, start, end, segment_elapsed, source_sha,
             report.get('status', 'unknown'), self.experiment_id))
        self._status(run, report.get('status'))
        self.client.set_tag(run, 'sts.sync_status', 'synced')
        return {'path': str(path), 'run_id': run, 'status': 'tracked', 'end_step': end, 'lineage': lineage}

    def _evaluation(self, path, report, key, source_sha, previous):
        groups = list(r.evaluations(report))
        if not groups:
            raise ValueError('No supported evaluation episodes')
        run = previous['run'] if previous else self._run(key, self.name or _name(path)+' evaluation',
            {'sts.kind': 'evaluation', 'sts.report_schema': report['schema']})
        self._local_run(run)
        # Evaluations need the same durable source binding as training: a
        # partial child-metric write must not accept a changed report on retry.
        self.db.execute('INSERT OR REPLACE INTO segments VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (key, str(path), run, 'evaluation', None, 0, 0, report.get('total_seconds') or 0., source_sha,
             'sync_pending:'+report.get('status', 'unknown'), self.experiment_id))
        self.db.commit()
        self.db.execute('BEGIN IMMEDIATE')
        self._histories.clear()
        self.client.set_tag(run, 'sts.sync_status', 'pending')
        self.client.log_dict(run, report, 'report.json')
        self.client.log_dict(run, {'path': str(path), 'sha256': source_sha}, 'source.json')
        self._notes(run, path, 'Each child identifies one model and one fixed evaluation population. '
                    'All planned cases, including failures and cutoffs, remain in the denominator.')
        for group in groups:
            group_key = r.identity([key, group['label'], group['population_id']])
            child = self._run(group_key, group['label']+' · '+group['split']+' · '+group['mode'],
                {'mlflow.parentRunId': run, 'sts.kind': 'evaluation_slice', 'sts.split': group['split'],
                 'sts.goal': group['goal'], 'sts.mode': group['mode'], 'sts.panel': group['panel'],
                 'sts.population': group['population_id'], 'sts.checkpoint': group['checkpoint'],
                 'sts.policy': group['policy_identity']})
            self._params(child, {'population_id': group['population_id'], 'goal': group['goal'],
                'split': group['split'], 'mode': group['mode'], 'panel': group['panel'],
                'checkpoint': group['checkpoint']})
            self.client.log_dict(child, group['population'], 'population.json')
            # One checkpoint may appear as an initial/final bundle in adjacent
            # chunks. They must all agree about the owning learner and step.
            owners = self.db.execute('''SELECT DISTINCT c.run, c.step FROM checkpoints c
                JOIN segments s ON c.segment=s.id WHERE c.sha=? AND s.experiment=?''',
                                    (group['checkpoint'], self.experiment_id)).fetchall()
            if len(owners) == 1:
                owner, step = owners[0]['run'], owners[0]['step']
                self.client.set_tag(child, 'sts.learner_run', owner)
                self.client.set_tag(child, 'sts.checkpoint_step', str(step))
                prefix = 'evaluation/'+group['split']+'/'+group['mode']+'/'+group['population_id'][:12]+'/'
                self._metrics(owner, step, {prefix+k.removeprefix('eval/'): v for k, v in group['metrics'].items()})
            else:
                self.client.set_tag(child, 'sts.checkpoint_step', 'unknown' if not owners else 'ambiguous')
                if 'sts.learner_run' in self.client.get_run(child).data.tags:
                    self.client.delete_tag(child, 'sts.learner_run')
            from .models import CheckpointCatalog
            model_ids = CheckpointCatalog(self).evaluate(child, group)
            self.client.set_tag(child, 'sts.model_ids', json.dumps(model_ids))
            self.client.set_tag(child, 'sts.checkpoint_ownership',
                                'unique' if len(owners) == 1 else 'shared' if owners else 'unresolved')
            if len(model_ids) == len(owners) == 1:
                self.client.set_tag(child, 'sts.model_id', model_ids[0])
            elif 'sts.model_id' in self.client.get_run(child).data.tags:
                self.client.delete_tag(child, 'sts.model_id')
            # A slice is one measurement. Its local step stays zero even if a
            # later import resolves checkpoint lineage; only learner overlays
            # use the checkpoint's decision/update counter.
            self._metrics(child, 0, group['metrics'])
            self._notes(child, path, 'Population: `'+group['population_id']+'`. Checkpoint: `'+group['checkpoint']+'`.')
            self._status(child, report.get('status'))
        self._metrics(run, 0, {'system/evaluation_seconds': report.get('total_seconds')})
        self.db.execute('INSERT OR REPLACE INTO segments VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (key, str(path), run, 'evaluation', None, 0, 0, report.get('total_seconds') or 0., source_sha,
             report.get('status', 'unknown'), self.experiment_id))
        self._status(run, report.get('status'))
        self.client.set_tag(run, 'sts.sync_status', 'synced')
        return {'path': str(path), 'run_id': run, 'status': 'tracked', 'evaluation_slices': len(groups)}

    def _status(self, run, status):
        self.client.set_tag(run, 'sts.report_status', status or 'unknown')
        if status == 'running':
            self.client.update_run(run, status='RUNNING')
        else:
            state = 'FAILED' if status == 'failed' else 'KILLED' if status in ('cancelled', 'interrupted') else 'FINISHED'
            self.client.set_terminated(run, status=state)


def _name(path):
    parent = path.parent
    while parent.name.startswith(('chunk-', 'stage-')):
        parent = parent.parent
    return parent.name
