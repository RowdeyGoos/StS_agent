"""Public trajectory integrity, atomic publication, and training data boundaries."""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path

import pytest

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.dataset import load_dataset, training_examples
from game.agent.recording import Metadata, SUFFIX, TrajectoryError, TrajectoryWriter, load_trajectory
from game.agent.runner import RunCancelled, RunConfig, run_episode


@pytest.fixture
def recorded(tmp_path):
    result = run_episode(RunConfig(seed=178932465789876543210, max_decisions=3),
                         output_dir=tmp_path / 'public', audit_dir=tmp_path / 'private')
    return Path(result.trajectory)


def rewritten(source, target, edit):
    records = [json.loads(line) for line in source.read_text().splitlines()]
    edit(records)
    lines = [(json.dumps(row, separators=(',', ':')) + '\n').encode() for row in records[:-1]]
    records[-1]['sha256'] = hashlib.sha256(b''.join(lines)).hexdigest()
    lines.append((json.dumps(records[-1]) + '\n').encode())
    target.write_bytes(b''.join(lines))


def test_round_trip_preserves_all_candidates_actions_and_cutoff(recorded):
    trace = load_trajectory(recorded, split='train')
    assert len(trace.transitions) == 3
    assert trace.outcome == c.RunOutcome('sts_run_outcome_v1', 'truncated', 'decision_budget')
    current = trace.initial
    for step in trace.transitions:
        assert step.observation == current and step.action in current.candidates
        assert step.execution.status == 'reconciled' and step.reward == 0
        assert f.loads(f.dumps(current)) == current
        current = step.successor
    assert isinstance(current, f.PublicDecision) and current.candidates
    with TrajectoryWriter(recorded.parent / ('copy' + SUFFIX), trace.metadata, trace.initial) as writer:
        for step in trace.transitions:
            writer.append(step.action, step.execution, step.successor)
        writer.finish(trace.outcome)
    assert load_trajectory(writer.path) == trace


def test_audit_seed_and_backend_state_are_not_in_public_artifact(recorded, monkeypatch):
    public = recorded.read_text()
    assert '178932465789876543210' not in public
    for forbidden in ('"seed"', '"rng"', '"snapshot"', '"binding"', '"audit"', '"private"'):
        assert forbidden not in public
    audit, = (recorded.parent.parent / 'private').glob('*.audit.json')
    private = json.loads(audit.read_text())
    assert private['config']['seed'] == 178932465789876543210
    assert private['episode_id'] == load_trajectory(recorded).metadata.episode_id
    assert audit.stat().st_mode & 0o777 == 0o600
    assert audit.parent.stat().st_mode & 0o777 == 0o700
    def cannot_open(*_):
        pytest.fail('The public loader attempted to open a private audit file')
    monkeypatch.setattr(Path, 'open', cannot_open)
    with pytest.raises(TrajectoryError, match='published public'):
        load_trajectory(audit)


@pytest.mark.parametrize('mutation', [
    lambda r: r[0].update(schema='sts_public_trajectory_v999'),
    lambda r: r[0]['metadata'].update(encoding='sts_public_json_v999'),
    lambda r: r[0]['metadata'].update(seed=99),
    lambda r: r[0]['metadata'].update(evidence='live_demonstration'),
    lambda r: r[0]['metadata'].update(build='unknown'),
    lambda r: r[0]['initial'].update(schema='headless_run_state_v69'),
    lambda r: r[1].update(index=True),
    lambda r: r[1].update(index=2),
    lambda r: r[1].update(action='action:99999'),
    lambda r: r[1].update(action=0),
    lambda r: r[1]['execution'].update(status='pending', mutation='queued'),
    lambda r: r[1]['execution'].update(status='uncertain', mutation='unknown'),
    lambda r: r[1].update(reward=1),
    lambda r: r[1].update(reward=False),
    lambda r: r[1].update(private_snapshot={}),
    lambda r: r[-1].update(steps=1),
    lambda r: r[-1]['outcome'].update(kind='victory', reason='none'),
])
def test_malformed_or_incompatible_artifacts_reject_even_with_new_digest(recorded, mutation):
    path = recorded.parent / ('bad' + SUFFIX)
    rewritten(recorded, path, mutation)
    with pytest.raises(TrajectoryError):
        load_trajectory(path)


def test_digest_truncation_duplicate_fields_and_trailing_records_reject(recorded):
    path = recorded.parent / ('bad' + SUFFIX)
    source = recorded.read_bytes()
    for corrupted in (
        source.replace(b'"scenario":', b'"scenario":"changed","scenario":', 1),
        source.replace(b'generated_campaign_all_unlocked_v1', b'changed_scenario'),
        b'\n'.join(source.splitlines()[:-1]) + b'\n',
        source + b'{}\n',
        source.replace(b'"reward":0', b'"reward":NaN', 1),
    ):
        path.write_bytes(corrupted)
        with pytest.raises(TrajectoryError):
            load_trajectory(path)


def test_incomplete_writes_never_replace_existing_finished_artifacts(recorded):
    original = recorded.read_bytes()
    trace = load_trajectory(recorded)
    with pytest.raises(FileExistsError):
        TrajectoryWriter(recorded, trace.metadata, trace.initial)
    assert recorded.read_bytes() == original
    path = recorded.parent / ('interrupted' + SUFFIX)
    with pytest.raises(RunCancelled):
        with TrajectoryWriter(path, trace.metadata, trace.initial) as writer:
            writer.append(*[getattr(trace.transitions[0], key) for key in ('action', 'execution', 'successor')])
            raise RunCancelled()
    assert not path.exists() and writer.partial.exists()
    with pytest.raises(TrajectoryError):
        load_trajectory(writer.partial)


def test_publish_race_and_cancel_during_commit_keep_partial(recorded):
    trace = load_trajectory(recorded)
    for cancel in (False, True):
        path = recorded.parent / (str(cancel) + SUFFIX)
        with TrajectoryWriter(path, trace.metadata, trace.initial) as writer:
            if not cancel:
                path.write_bytes(b'previous finished artifact')
            def check_cancel():
                raise RunCancelled()
            with pytest.raises(RunCancelled if cancel else FileExistsError):
                writer.finish(c.RunOutcome('sts_run_outcome_v1', 'truncated', 'external_stop'),
                              check_cancel=check_cancel if cancel else None)
        assert writer.partial.exists()
        assert not path.exists() if cancel else path.read_bytes() == b'previous finished artifact'


def test_split_and_implementation_identity_are_enforced(recorded):
    trace = load_trajectory(recorded)
    assert list(load_dataset([recorded], split='train', expected={'rules': trace.metadata.rules})) == [trace]
    for kwargs in ({'split': 'test'}, {'split': 'train', 'expected': {'build': '0' * 64}},
                   {'split': 'train', 'expected': {'private_seed': 3}}):
        with pytest.raises(TrajectoryError):
            list(load_dataset([recorded], **kwargs))


def test_training_loader_uses_exact_candidate_slot_and_keeps_cutoff_observation(recorded):
    pytest.importorskip('numpy')
    from game.agent.encoding.full import FullRunEncoder
    encoder = FullRunEncoder()
    trace = load_trajectory(recorded)
    samples = list(training_examples([recorded], split='train', encoder=encoder))
    for step, sample in zip(trace.transitions, samples):
        encoded = encoder.encode(step.observation)
        assert encoded.candidate_refs[sample.action] == step.action.ref
        assert sample.observation['action_mask'][sample.action]
        assert sample.encoding == encoder.profile.identity
        assert not sample.terminated and sample.reward == 0
    assert [s.truncated for s in samples] == [False, False, True]
    assert samples[-1].successor['action_mask'].any()
    assert isinstance(encoder.decode(samples[-1].successor), f.PublicDecision)
