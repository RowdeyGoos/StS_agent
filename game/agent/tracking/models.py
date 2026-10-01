"""Checkpoint catalog for MLflow's Models view; never restore model tensors."""
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit

from . import records as r


class CheckpointCatalog:
    def __init__(self, store):
        self.store, self.client = store, store.client

    def _local_model(self, model, run, key):
        location = urlsplit(model.artifact_location)
        path = Path(unquote(location.path))
        if (model.experiment_id != self.store.experiment_id or model.source_run_id != run
                or model.tags.get('sts.checkpoint_record') != key
                or location.scheme != 'file' or location.netloc or not r.public_path(path)
                or not path.resolve().is_relative_to(self.store.path/'artifacts')):
            raise ValueError('Checkpoint model identity or artifact destination differs from this local store')

    def boundaries(self, run):
        """Learner endpoints, not the endpoints of every resumed invocation."""
        rows = self.store.db.execute('''SELECT c.sha, c.step FROM checkpoints c
            JOIN segments s ON s.id=c.segment WHERE c.run=? AND s.experiment=? AND
            ((c.step=s.start AND s.start=(SELECT MIN(start) FROM segments WHERE run=?)) OR
             (c.endpoint=1 AND c.step=(SELECT MAX(c2.step) FROM checkpoints c2
                 JOIN segments s2 ON s2.id=c2.segment WHERE c2.run=? AND c2.endpoint=1
                 AND s2.status NOT IN ('running','sync_pending:running'))
              AND s.status NOT IN ('running','sync_pending:running')))''',
            (run, self.store.experiment_id, run, run))
        return {(row['sha'], row['step']) for row in rows}

    def _visibility(self, row, visible):
        """Reversible visibility for the pinned, local MLflow 3.16 SQLite store.

        MLflow has no restore API for logged models. Change only its soft-delete
        lifecycle and our revision marker; never remove rows, artifacts or scores.
        A later manual deletion changes the revision and is never auto-restored.
        """
        with closing(sqlite3.connect(self.store.path/'mlflow.db', timeout=60)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute('BEGIN IMMEDIATE')
            model = db.execute('SELECT * FROM logged_models WHERE model_id=?', (row['model'],)).fetchone()
            if model is None:
                return 'unavailable'
            tags = dict(db.execute('SELECT tag_key,tag_value FROM logged_model_tags WHERE model_id=?',
                                   (row['model'],)).fetchall())
            self._local_model(SimpleNamespace(experiment_id=str(model['experiment_id']),
                source_run_id=model['source_run_id'], artifact_location=model['artifact_location'], tags=tags),
                row['run'], row['record'])
            # Preserve explicitly retained candidates and measurements even if
            # publication stopped after metrics but before the evaluated tag.
            visible = visible or tags.get('sts.catalog_keep') == 'true' or tags.get('sts.evaluated') == 'true' or bool(
                db.execute('SELECT 1 FROM logged_model_metrics WHERE model_id=? LIMIT 1', (row['model'],)).fetchone())
            marker = 'selected_v1:'+str(model['last_updated_timestamp_ms'])
            hidden = model['lifecycle_stage'] == 'deleted'
            if hidden and tags.get('sts.catalog_hidden') != marker:
                return 'unavailable'  # User deletion or external garbage collection.
            if hidden == (not visible):
                return 'kept' if visible else 'already_hidden'
            timestamp = max(int(time.time()*1000), model['last_updated_timestamp_ms']+1)
            db.execute('UPDATE logged_models SET lifecycle_stage=?,last_updated_timestamp_ms=? WHERE model_id=?',
                       ('active' if visible else 'deleted', timestamp, row['model']))
            if visible:
                db.execute("DELETE FROM logged_model_tags WHERE model_id=? AND tag_key='sts.catalog_hidden'", (row['model'],))
            else:
                db.execute('INSERT OR REPLACE INTO logged_model_tags VALUES (?,?,?,?)',
                    (row['model'], self.store.experiment_id, 'sts.catalog_hidden', 'selected_v1:'+str(timestamp)))
            return 'restored' if visible else 'hidden'

    def reconcile(self, run=None):
        rows = self.store.db.execute('''SELECT * FROM checkpoint_models WHERE run IN
            (SELECT run FROM segments WHERE experiment=?)''', (self.store.experiment_id,)).fetchall()
        boundaries, counts = {}, {}
        for row in rows:
            if run is not None and row['run'] != run:
                continue
            if row['run'] not in boundaries:
                boundaries[row['run']] = self.boundaries(row['run'])
            result = self._visibility(row, (row['sha'], row['step']) in boundaries[row['run']])
            counts[result] = counts.get(result, 0)+1
        return counts

    def promote(self, sha):
        """Publish a known recovery checkpoint when evaluated or retained."""
        owners = self.store.db.execute('''SELECT c.run,c.sha,c.step,s.path,s.kind,s.source_sha FROM checkpoints c
            JOIN segments s ON s.id=c.segment WHERE c.sha=? AND s.experiment=? ORDER BY s.path''',
            (sha, self.store.experiment_id)).fetchall()
        seen = set()
        for owner in owners:
            identity = (owner['run'], owner['sha'], owner['step'])
            if identity in seen:
                continue
            seen.add(identity)
            row = self.store.db.execute('SELECT * FROM checkpoint_models WHERE run=? AND sha=? AND step=?', identity).fetchone()
            if row:
                self._visibility(row, True)
                continue
            path = Path(owner['path'])
            report = r.read_json(path)
            if owner['source_sha'] not in (r.digest(path), r.identity(report)):
                raise ValueError('Checkpoint source report changed before catalog promotion')
            artifacts, _ = self.store._checkpoint_artifacts(path, report)
            selected = [item for item in artifacts if (item['sha256'], item['step']) == identity[1:]]
            if not selected:
                raise ValueError('Checkpoint is absent from its recorded source report')
            self.sync(owner['run'], selected, owner['kind'])
        return len(seen)

    def sync(self, run, artifacts, kind):
        from mlflow.entities import LoggedModelOutput
        source = self.client.get_run(run)
        axis = 'decisions' if kind == 'ppo' else 'optimizer_updates'
        outputs = {(m.model_id, m.step) for m in source.outputs.model_outputs} if source.outputs else set()
        for item in artifacts:
            sha, step, manifest = item['sha256'], item['step'], item['manifest']
            key = r.identity([self.store.experiment_id, run, sha, step])
            row = self.store.db.execute('SELECT model FROM checkpoint_models WHERE record=?', (key,)).fetchone()
            if row:
                if self._visibility({'model': row['model'], 'run': run, 'record': key}, True) == 'unavailable':
                    continue
                model = self.client.get_logged_model(row['model'])
            else:
                # Include policy-hidden records when recovering a rolled-back
                # index transaction; stock MLflow search excludes deleted rows.
                with closing(sqlite3.connect(self.store.path/'mlflow.db', timeout=60)) as db:
                    matches = db.execute('''SELECT m.model_id FROM logged_models m JOIN logged_model_tags t
                        ON t.model_id=m.model_id WHERE m.experiment_id=? AND m.source_run_id=?
                        AND t.tag_key='sts.checkpoint_record' AND t.tag_value=? LIMIT 2''',
                        (self.store.experiment_id, run, key)).fetchall()
                if len(matches) > 1:
                    raise ValueError('Ambiguous checkpoint model record')
                if matches and self._visibility({'model': matches[0][0], 'run': run, 'record': key}, True) == 'unavailable':
                    continue
                values = {k: manifest.get(k) for k in ('algorithm', 'architecture', 'feature_identity',
                    'action_policy', 'learner_config', 'implementation', 'runtime')}
                values.update(reward=manifest.get('reward_spec'), checkpoint={'sha256': sha, 'step': step, 'axis': axis})
                model = self.client.get_logged_model(matches[0][0]) if matches else self.client.create_logged_model(
                    self.store.experiment_id,
                    name=source.data.tags.get('mlflow.runName', run)[:160]+' · '+f'{step:,} '+axis.replace('_', ' ')+' · '+sha[:8],
                    source_run_id=run, model_type='sts_'+kind,
                    params=r.params(values), tags={'sts.checkpoint_record': key, 'sts.checkpoint': sha,
                        'sts.checkpoint_step': str(step), 'sts.x_axis': axis, 'sts.kind': kind,
                        'sts.evaluated': 'false', 'sts.evidence': 'reported_metadata',
                        'sts.source_checkpoint': item['path'], 'sts.bundle_format': 'sts-model'})
            self._local_model(model, run, key)
            if str(model.status) != 'READY':
                source_path = Path(item['path'])
                if not r.public_path(source_path):
                    raise ValueError('Checkpoint source must remain a public local path')
                # Stage and hash the exact bytes uploaded. Do not load weights,
                # follow report-supplied artifact destinations or copy private state.
                with tempfile.TemporaryDirectory(prefix='sts-checkpoint-model-') as directory:
                    staged = Path(directory)
                    shutil.copyfile(source_path, staged/'checkpoint.sts-model')
                    if r.digest(staged/'checkpoint.sts-model') != sha:
                        raise ValueError('Checkpoint digest changed before model publication')
                    (staged/'manifest.json').write_bytes(r.data(manifest))
                    (staged/'source.json').write_bytes(r.data({
                        'path': item['path'], 'sha256': sha, 'step': step, 'axis': axis, 'training_run': run}))
                    (staged/'README.md').write_text(
                        '# StS policy checkpoint\n\n'
                        'This is a public StS inference bundle. Use the existing StS checkpoint loader; '
                        'it is not packaged for MLflow model serving.\n\n'
                        'READY means the verified bundle was copied, not that gameplay was revalidated '
                        'or that this checkpoint was selected as the best policy.\n')
                    self.client.log_model_artifacts(model.model_id, str(staged))
                if (model.model_id, step) not in outputs:
                    self.client.log_outputs(run, [LoggedModelOutput(model.model_id, step)])
                    outputs.add((model.model_id, step))
                self.client.finalize_logged_model(model.model_id, 'READY')
            inspector = self.store.inspector_url or source.data.tags.get('sts.inspector_url')
            if inspector and model.tags.get('sts.inspector_url') != inspector:
                self.client.set_logged_model_tags(model.model_id, {'sts.inspector_url': inspector})
            self.store.db.execute('INSERT OR REPLACE INTO checkpoint_models VALUES (?,?,?,?,?)',
                                 (key, run, sha, step, model.model_id))

    def evaluate(self, child, group):
        from mlflow.entities import Dataset, DatasetInput, InputTag, Metric
        self.promote(group['checkpoint'])
        rows = self.store.db.execute('''SELECT * FROM checkpoint_models WHERE sha=?
            AND run IN (SELECT run FROM segments WHERE experiment=?)''',
            (group['checkpoint'], self.store.experiment_id)).fetchall()
        if not rows:
            return []  # A later import can attach metrics after checkpoint backfill.
        population = group['population_id']
        # MLflow dataset digests are limited to 36 characters; the complete
        # population SHA remains in the source metadata and evaluation artifact.
        dataset_digest = population[:32]
        dataset_name = '/'.join((group['goal'], group['split'], group['mode'], group['panel'], population[:12]))
        dataset = Dataset(name=dataset_name, digest=dataset_digest, source_type='sts_evaluation_population_v1',
                          source=json.dumps({'population_id': population}, sort_keys=True))
        self.client.log_inputs(child, datasets=[DatasetInput(dataset, [InputTag('mlflow.data.context', group['split'])])])
        prefix = 'evaluation/'+group['split']+'/'+group['mode']+'/'+population[:12]+'/'
        # The child run identifies one immutable evaluation measurement. Stable
        # timestamps also make crash recovery idempotent in MLflow's metric store.
        timestamp = self.client.get_run(child).info.start_time
        linked = []
        # Reusing an exact bundle does not change its inference policy. Scores
        # apply to every catalog entry for those bytes, without asserting unique
        # learner lineage or pooling different checkpoints/populations.
        for row in rows:
            if self._visibility(row, True) == 'unavailable':
                continue
            model = self.client.get_logged_model(row['model'])
            self._local_model(model, row['run'], row['record'])
            if str(model.status) != 'READY':
                continue
            existing = {(m.key, m.value, m.run_id, m.dataset_digest) for m in model.metrics or ()}
            metrics = [Metric(prefix+k.removeprefix('eval/'), value, timestamp, 0, model_id=model.model_id,
                              dataset_name=dataset_name, dataset_digest=dataset_digest)
                       for k, value in group['metrics'].items()
                       # The Models table makes every metric a column. Keep
                       # aggregate scores here; detailed breakdowns stay on the
                       # evaluation run and its canonical report.
                       if '/' not in k.removeprefix('eval/')
                       and (prefix+k.removeprefix('eval/'), value, child, dataset_digest) not in existing]
            for offset in range(0, len(metrics), 1000):
                self.client.log_batch(child, metrics=metrics[offset:offset+1000])
            self.client.set_logged_model_tags(model.model_id, {'sts.evaluated': 'true',
                'sts.score_binding': 'public_checkpoint_sha256',
                'sts.checkpoint_ownership': 'shared' if len(rows) > 1 else 'unique',
                **({'sts.validation': 'true'} if group['split'] == 'validation' else {})})
            linked.append(model.model_id)
        return sorted(linked)
