"""Development selection and bounded integration transport regressions."""
from __future__ import annotations

import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import check
from components.events.integration_tests import test_generic_event_integration as integration


class CheckSelectionTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix='sts-check-test-', dir='/private/tmp')
        self.addCleanup(scratch.cleanup)
        self.gate = check.Gate(['bridge'], Path(scratch.name), 'fixture-dotnet', None)

    def test_listing_never_builds_or_executes(self):
        self.gate.list_only = True
        with patch.object(self.gate, 'run', side_effect=AssertionError('execution during listing')):
            self.gate.python()
            self.gate.behavior()
        self.assertIn('events:host_native', self.gate.available)
        self.assertIn('client', self.gate.available)
        self.assertEqual(len(self.gate.available), len(set(self.gate.available)))

    def test_exact_native_selection_builds_only_its_dependency(self):
        project = 'components/events/direct_input_tests/DirectTransformInput.Tests.csproj'
        self.gate.only = {'test:' + project}
        with patch.object(self.gate, 'build', return_value=Path('/fixture.dll')) as build, \
             patch.object(self.gate, 'run', return_value=check.SDK_VERSION) as run:
            self.gate.python()
            self.gate.behavior()
        build.assert_called_once_with(project)
        self.assertEqual([call.args[0] for call in run.call_args_list], ['sdk', 'test:' + project])

    def test_wire_selection_omits_native_build_and_forwards_workers(self):
        self.gate.only = {'events:host_native'}
        self.gate.event_groups = ['wire']
        self.gate.jobs = 2
        with patch.object(self.gate, 'build', return_value=Path('/fixture.dll')) as build, \
             patch.object(self.gate, 'run', return_value=check.SDK_VERSION) as run:
            self.gate.behavior()
        build.assert_called_once_with('components/events/integration/Sts2AgentBridge.GenericEventV7.Integration.csproj')
        command = run.call_args.args[1]
        self.assertNotIn('--native-fixture', command)
        self.assertEqual(command[command.index('--jobs') + 1], '2')
        self.assertEqual(command[-2:], ['--group', 'wire'])

    def test_invalid_selections_fail_before_execution(self):
        cases = (
            (['--suite', 'release', '--check', 'events:host_native'], 'selection_requires_development_suite'),
            (['--suite', 'release', '--event-group', 'wire'], 'selection_requires_development_suite'),
            (['--event-group', 'wire'], 'event_group_requires_integration_check'),
            (['--suite', 'python', '--check', 'misspelled'], 'unknown_check:misspelled'),
            (['--suite', 'python', '--component', 'cards', '--check', 'client'], 'unknown_check:client'),
        )
        for args, error in cases:
            with self.subTest(args=args), patch.object(sys, 'argv', ['check.py', *args]), \
                 patch.object(check.Gate, 'run', side_effect=AssertionError('unexpected execution')):
                with self.assertRaisesRegex(ValueError, error):
                    check.main()

    def test_timed_out_worker_tree_is_killed_and_cannot_pass(self):
        process = Mock(pid=12345, returncode=0)
        process.communicate.side_effect = [subprocess.TimeoutExpired('fixture', 240), (b'partial', None)]
        with patch.object(check.subprocess, 'Popen', return_value=process) as start, \
             patch.object(check.os, 'killpg') as kill, patch.object(check.sys, 'stderr', io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'check_failed:fixture'):
                self.gate.run('fixture', ['fixture'])
        self.assertTrue(start.call_args.kwargs['start_new_session'])
        kill.assert_called_once_with(process.pid, check.signal.SIGKILL)
        self.assertEqual(self.gate.checks['fixture']['status'], 'failed')
        self.assertEqual(self.gate.checks['fixture']['failure'], 'timeout')
        self.assertEqual((self.gate.scratch / self.gate.checks['fixture']['log']).read_bytes(), b'partial')

    def test_interruption_kills_worker_tree_and_propagates(self):
        process = Mock(pid=12345)
        process.communicate.side_effect = [KeyboardInterrupt(), (b'', None)]
        with patch.object(check.subprocess, 'Popen', return_value=process), \
             patch.object(check.os, 'killpg') as kill:
            with self.assertRaises(KeyboardInterrupt):
                self.gate.run('fixture', ['fixture'])
        kill.assert_called_once_with(process.pid, check.signal.SIGKILL)
        self.assertNotIn('fixture', self.gate.checks)

    def test_parallel_checks_overlap_and_keep_distinct_logs(self):
        commands = []
        for name, other in (('first', 'second'), ('second', 'first')):
            script = ("from pathlib import Path\nimport time\n"
                      f"Path({name!r}).touch()\n"
                      "deadline = time.monotonic() + 5\n"
                      f"while not Path({other!r}).exists():\n"
                      "    assert time.monotonic() < deadline, 'checks did not overlap'\n"
                      "    time.sleep(0.005)\n"
                      f"print({name!r})\n")
            commands.append((name, [sys.executable, '-c', script]))
        self.gate.run_parallel(commands)
        self.assertEqual(len({row['log'] for row in self.gate.checks.values()}), 2)
        for name, row in self.gate.checks.items():
            self.assertEqual(row['status'], 'passed')
            self.assertEqual((self.gate.scratch / row['log']).read_text().strip(), name)
        self.assertFalse(self.gate._active)

    def test_fast_failure_stops_running_peer(self):
        waiting = "from pathlib import Path\nimport time\nPath('waiting').touch()\ntime.sleep(30)\n"
        failure = ("from pathlib import Path\nimport time\n"
                   "deadline = time.monotonic() + 5\n"
                   "while not Path('waiting').exists():\n"
                   "    assert time.monotonic() < deadline\n"
                   "    time.sleep(0.005)\n"
                   "raise SystemExit(7)\n")
        with patch.object(check.sys, 'stderr', io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'check_failed:failure'):
                self.gate.run_parallel([('waiting', [sys.executable, '-c', waiting]),
                                        ('failure', [sys.executable, '-c', failure])])
        self.assertTrue(self.gate._aborted)
        self.assertFalse(self.gate._active)
        self.assertEqual({name: row['status'] for name, row in self.gate.checks.items()},
                         {'waiting': 'failed', 'failure': 'failed'})
        with self.assertRaisesRegex(ValueError, 'gate_aborted'):
            self.gate.run('later', [sys.executable, '-c', 'pass'])

    def test_serial_override_does_not_create_worker_threads(self):
        self.gate.jobs = 1
        with patch.object(check, 'ThreadPoolExecutor', side_effect=AssertionError('parallel work')), \
             patch.object(self.gate, 'run') as run:
            self.gate.run_parallel([('a', ['a']), ('b', ['b'])])
        self.assertEqual([call.args[0] for call in run.call_args_list], ['a', 'b'])

    def test_parallel_interruption_cleans_up_all_started_checks(self):
        command = [sys.executable, '-c', 'import time; time.sleep(30)']
        with patch.object(check, 'as_completed', side_effect=KeyboardInterrupt()), \
             patch.object(check.sys, 'stderr', io.StringIO()):
            with self.assertRaises(KeyboardInterrupt):
                self.gate.run_parallel([('a', command), ('b', command)])
        self.assertTrue(self.gate._aborted)
        self.assertFalse(self.gate._active)


class RewardSetSchedulingTests(unittest.TestCase):
    def test_all_parts_scheduled_once_and_other_groups_preserved(self):
        tasks = integration.integration_tasks(list(integration.GROUPS))
        self.assertEqual(len(tasks), len(set(tasks)))
        self.assertEqual([part for group, part in tasks if group == 'reward_sets'],
                         ['cards_native', 'cards_host', 'mixed_native', 'mixed_host'])
        self.assertEqual([group for group, part in tasks if part is None],
                         [group for group in integration.GROUPS if group != 'reward_sets'])

    def test_focused_reward_sets_still_include_every_part(self):
        tasks = integration.integration_tasks(['reward_sets'])
        self.assertEqual(len(tasks), 4)
        self.assertTrue(all(group == 'reward_sets' and part for group, part in tasks))


class ReplyReaderTests(unittest.TestCase):
    def read(self, parts):
        selector = Mock()
        selector.select.return_value = [object()]
        with patch.object(integration.os, 'read', side_effect=parts):
            return integration.read_reply(Mock(), selector)

    def test_fragmented_frame(self):
        self.assertEqual(self.read([b'{"a":', b'1}', b'\n']), b'{"a":1}\n')

    def test_exact_limit(self):
        payload = b'x' * 99_999 + b'\n'
        self.assertEqual(self.read([payload[:65_536], payload[65_536:]]), payload)

    def test_oversize_eof_and_trailing_frames(self):
        for parts, error in (([b'x' * 65_536, b'x' * 34_465], 'size'),
                             ([b'{', b''], 'EOF'),
                             ([b'{}\n{}\n'], 'framing'),
                             ([b'{}\nx'], 'framing')):
            with self.subTest(error=error), self.assertRaisesRegex(AssertionError, error):
                self.read(parts)

    def test_absolute_deadline_does_not_reset_after_partial_read(self):
        selector = Mock()
        selector.select.return_value = [object()]
        with patch.object(integration.time, 'monotonic', side_effect=[0, 1, 6]), \
             patch.object(integration.os, 'read', return_value=b'{') as read:
            with self.assertRaisesRegex(AssertionError, 'deadline'):
                integration.read_reply(Mock(), selector)
        read.assert_called_once()

    def test_selector_timeout(self):
        selector = Mock()
        selector.select.return_value = []
        with self.assertRaisesRegex(AssertionError, 'deadline'):
            integration.read_reply(Mock(), selector)

    def test_shutdown_timeout_kills_and_closes_streams(self):
        exchange = integration.Exchange.__new__(integration.Exchange)
        exchange.process = Mock()
        exchange.process.stdin = io.BytesIO()
        exchange.process.stdout = io.BytesIO()
        exchange.process.stderr = io.BytesIO()
        exchange.process.wait.side_effect = [subprocess.TimeoutExpired('fixture', 5), 0]
        exchange.selector = Mock()
        exchange.buffers = []
        with self.assertRaisesRegex(AssertionError, 'shutdown timeout'):
            exchange.close()
        exchange.process.kill.assert_called_once()
        exchange.selector.close.assert_called_once()
        self.assertTrue(all(s.closed for s in (exchange.process.stdin, exchange.process.stdout, exchange.process.stderr)))


if __name__ == '__main__':
    unittest.main()
