"""Opt-in native journals retain public decisions, not dispatch credentials."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from test_full_agent_host import FullWire, host
from game.agent.live_recording import LiveTrajectoryWriter, load_live_trajectory
from game.agent.recording import TrajectoryError


class LiveRecordingTests(unittest.TestCase):
    def writer(self, path):
        return LiveTrajectoryWriter(path, release_sha256='a' * 64, split='test', setup='controlled')

    def test_nested_success_and_stale_keep_only_public_data(self):
        for stale in (False, True):
            with TemporaryDirectory() as folder:
                path = Path(folder) / 'run.live.jsonl'
                wire = FullWire(); wire.stale = stale
                writer = self.writer(path)
                result = host.run_agent(wire.request, full=True, recorder=writer)
                self.assertEqual(result['status'], 'resolved', result)
                trace = load_live_trajectory(path, split='test', release_sha256='a' * 64)
                self.assertEqual(trace.outcome.kind, 'victory')
                actions = [row for row in trace.records if row['record'] == 'action']
                self.assertEqual(len(actions), 8 + int(stale))
                self.assertTrue(all(row['execution']['status'] in ('pending', 'rejected') for row in actions))
                self.assertGreater(actions[2]['counts'][1], actions[2]['counts'][2])
                raw = path.read_text()
                for forbidden in ('decision_id', 'session_nonce', 'binding', 'authorization', '0000000000000000000000000000000000000000000000000000000000000001'):
                    self.assertNotIn(forbidden, raw)
                self.assertFalse(writer.partial.exists())
                with self.assertRaises(FileExistsError): self.writer(path)

    def test_cutoff_and_failures_are_distinct(self):
        for mode in ('cutoff', 'lost', 'policy', 'interrupt', 'system_exit'):
            with TemporaryDirectory() as folder:
                path = Path(folder) / 'run.live.jsonl'; wire = FullWire(); writer = self.writer(path)
                def request(method, route, body):
                    if mode == 'lost' and method == 'POST': raise ConnectionError()
                    return wire.request(method, route, body)
                def policy(public):
                    if mode == 'policy': raise ValueError()
                    if mode == 'interrupt': raise KeyboardInterrupt()
                    if mode == 'system_exit': raise SystemExit()
                    return host.choose_full_action(public)
                if mode == 'system_exit':
                    with self.assertRaises(SystemExit): host.run_agent(request, full=True, recorder=writer, policy=policy)
                else:
                    result = host.run_agent(request, full=True, recorder=writer, policy=policy, stop_at_map=mode == 'cutoff')
                    self.assertEqual(result['status'], 'resolved' if mode == 'cutoff' else 'failed')
                self.assertTrue(writer.closed)
                self.assertEqual(path.exists(), mode == 'cutoff')
                self.assertEqual(writer.partial.exists(), mode != 'cutoff')
                if mode == 'cutoff':
                    self.assertEqual(load_live_trajectory(path).outcome.reason, 'external_stop')
                else:
                    with self.assertRaises(TrajectoryError): load_live_trajectory(writer.partial)

    def test_loader_rejects_corruption_even_with_recomputed_digest(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'run.live.jsonl'; host.run_agent(FullWire().request, full=True, recorder=self.writer(path))
            original = path.read_bytes()
            for mode in ('private', 'unadvertised', 'counts', 'settled_pending', 'uncertain', 'digest', 'tail', 'split', 'missing_actions', 'no_records', 'outcome_as_observation'):
                rows = [json.loads(line) for line in original.splitlines()]
                if mode == 'private': rows[1]['private'] = 'x'
                if mode == 'unadvertised': rows[2]['action'] = 'action:999'
                if mode == 'counts': rows[2]['counts'][1] = 0
                if mode == 'settled_pending': rows[2]['counts'][2] = 1
                if mode == 'uncertain': rows[2]['execution'].update(status='uncertain', mutation_state='unknown', reason='transport_failure')
                if mode == 'missing_actions': rows = [row for row in rows if row['record'] != 'action']
                if mode == 'no_records': rows = [rows[0], rows[-1]]
                if mode == 'outcome_as_observation': rows[1]['public'] = rows[-1]['outcome']
                raw = b''.join((json.dumps(row) + '\n').encode() for row in rows[:-1])
                rows[-1]['sha256'] = '0' * 64 if mode == 'digest' else hashlib.sha256(raw).hexdigest()
                path.write_bytes(raw + (json.dumps(rows[-1]) + '\n').encode() + (b'{}\n' if mode == 'tail' else b''))
                with self.assertRaises((TrajectoryError, ValueError)):
                    load_live_trajectory(path, split='train' if mode == 'split' else 'test')

    def test_metadata_is_explicit_and_no_overwrite(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'run.live.jsonl'
            for options in (dict(split=[]), dict(setup='unknown'), dict(release_sha256='bad')):
                values = dict(release_sha256='a' * 64, split='test', setup='controlled'); values.update(options)
                with self.assertRaises(TrajectoryError): LiveTrajectoryWriter(path, **values)
            writer = self.writer(path); writer.abort()
            with self.assertRaises(FileExistsError): self.writer(path)


if __name__ == '__main__': unittest.main()
