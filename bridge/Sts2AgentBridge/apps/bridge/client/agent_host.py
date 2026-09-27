"""Shared public-contract policy adapter over the one bridge transport.

Only immutable public decisions cross the policy callback. Native tokens, wire
receipts and dispatch bindings stay here. Acceptance is never reconciliation.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).absolute().parents[5]))
from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.full_policy import choose_action as choose_full_action
from game.agent.policy import choose_action

READ = '/probe/agent-v1/public/decision'
ACT = '/probe/agent-v1/public/action'
FULL_READ = '/probe/agent-v2/public/decision'
FULL_ACT = '/probe/agent-v2/public/action'
FIELDS = {'schema_version', 'protocol', 'status', 'decision_id', 'action_id', 'observation',
          'code', 'outcome', 'attempted', 'accepted', 'reconciled', 'parent_pending', 'child_pending'}
REJECTION_FIELDS = {'schema_version', 'protocol', 'status', 'mutation_state', 'reason',
                    'decision_id', 'action_id', 'attempted', 'accepted', 'reconciled'}
FULL_FAILURE_CODES = frozenset({
    'agent_stopped', 'unsupported_public_surface', 'agent_boundary_failed', 'read_limit',
    'unowned_completion', 'incomplete_run', 'invalid_public_graph', 'candidate_binding',
    'invalid_action', 'action_limit', 'duplicate_native_action', 'uncertain_dispatch', 'public_capacity',
    'read_native_rest_deck_capacity', 'read_native_rest_clone_capacity',
    *(f'read_{stage}_failed' for stage in ('native', 'run', 'deck', 'relics', 'potions', 'map', 'context', 'graph')),
    *(f'read_native_event_{reason}' for reason in (
        'none', 'parent_ready', 'parent_unavailable', 'parent_waiting', 'parent_map',
        'parent_overlay', 'parent_layout', 'parent_travel', 'child_ready', 'map_ready',
        'capture_disposed', 'capture_exception', 'diagnostic_unavailable',
        'prepare_binding', 'prepare_screen', 'prepare_external_selector', 'prepare_deck', 'prepare_foreground', 'prepare_family', 'prepare_grid_node',
        'prepare_grid_state', 'prepare_holders', 'prepare_candidates', 'prepare_geometry', 'prepare_preview_nodes', 'prepare_preview_state', 'prepare_confirm',
        'pending_binding_failed', 'pending_ownership', 'pending_context', 'pending_task_failed',
        'pending_chosen_entry', 'pending_chosen_task', 'pending_chosen_completion',
        'pending_request_task', 'pending_screen', 'pending_selectorless_request',
        'pending_overlay', 'pending_deck', 'pending_offers', 'pending_proceed',
        'pending_owner_binding', 'pending_owner_hooks', 'pending_owner_thread', 'pending_owner_patches')),
})


class AgentFailure(ValueError):
    """Bounded local failure; callers must not retry an uncertain dispatch."""


def require(condition, code):
    if not condition:
        raise AgentFailure(code)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate_field')
        result[key] = value
    return result


def decode(raw, *, full=False):
    require(type(raw) in (bytes, bytearray) and 0 < len(raw) <= (2097152 if full else 65536), 'wire_shape')
    try:
        value = json.loads(raw, object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(AgentFailure('nonfinite')))
    finally:
        if type(raw) is bytearray:
            raw[:] = b'\0' * len(raw)
    require(type(value) is dict and value.get('schema_version') == (2 if full else 1) and
            type(value['schema_version']) is int and value.get('protocol') == ('agent_v2' if full else 'agent_v1'), 'wire_version')
    fields = REJECTION_FIELDS if value.get('status') == 'rejected' else FIELDS
    if full:
        fields = fields - {'parent_pending', 'child_pending'} | {'pending'}
    require(set(value) == fields, 'wire_fields')
    for name in ('attempted', 'accepted', 'reconciled'):
        require(type(value[name]) is int and 0 <= value[name] <= (8192 if full else 512), 'wire_counts')
    require(value['reconciled'] <= value['accepted'] <= value['attempted'], 'wire_counts')
    if full:
        require(type(value['pending']) is int and value['pending'] == value['accepted'] - value['reconciled'], 'pending_counts')
    return value


@dataclass(frozen=True, slots=True)
class DecisionFrame:
    decision: c.PublicDecision | f.PublicDecision
    binding: object


class LiveAdapter:
    def __init__(self, request, *, full=False):
        self.request = request
        self.full = full
        self._frame = self._token = None
        self.stopped = False
        self.counts = (0, 0, 0)
        self.pending = False
        self.reads = 0
        self.attempted = 0

    def _counts(self, value):
        counts = tuple(value[name] for name in ('attempted', 'accepted', 'reconciled'))
        require(all(new >= old for new, old in zip(counts, self.counts)), 'counts_regressed')
        self.counts = counts
        self.attempted = max(self.attempted, counts[0])

    def observe(self):
        require(not self.stopped, 'adapter_stopped')
        try:
            self.reads += 1
            require(self.reads <= (131072 if self.full else 4096), 'read_limit')
            value = decode(self.request('GET', FULL_READ if self.full else READ, None), full=self.full)
            status = value['status']
            require(status in ('waiting', 'ready', 'complete', 'unsupported', 'failed'), 'read_status')
            if self.full:
                next_pending = value['pending'] > 0
            else:
                for name in ('parent_pending', 'child_pending'):
                    require(type(value[name]) is bool, 'pending_shape')
                next_pending = value['parent_pending'] or value['child_pending']
            self._frame = self._token = None
            if status in ('unsupported', 'failed'):
                if self.full:
                    self._counts(value)
                    self.pending = next_pending
                    code = value['code']
                    raise AgentFailure(code if type(code) is str and code in FULL_FAILURE_CODES else 'native_failure')
                raise AgentFailure('unsupported_profile' if status == 'unsupported' else 'native_failure')
            require(value['code'] is None and value['action_id'] is None, 'read_fields')
            counts = tuple(value[name] for name in ('attempted', 'accepted', 'reconciled'))
            require(all(new >= old for new, old in zip(counts, self.counts)), 'counts_regressed')
            if not self.full:
                require(not value['child_pending'] or value['parent_pending'], 'unowned_child')
                require(counts[1] - counts[2] == int(value['parent_pending']) + int(value['child_pending']), 'pending_counts')
            if status == 'ready':
                require(type(value['decision_id']) is str and re.fullmatch('[0-9a-f]{64}', value['decision_id']), 'decision_token')
                require(value['outcome'] is None, 'ready_outcome')
                codec = f if self.full else c
                public = codec.from_dict(value['observation'])
                codec.require_ready(public)
                require([a.ref for a in public.candidates] == [f'action:{i}' for i in range(len(public.candidates))], 'action_refs')
                require(len(public.candidates) <= (2048 if self.full else 256), 'candidate_limit')
                if not self.full:
                    require(not value['child_pending'], 'unreconciled_child')
                    require(not value['parent_pending'] or isinstance(public.context, c.CardSelection), 'unreconciled_parent')
                self._counts(value)
                self.pending = next_pending
                self._token = value['decision_id']
                self._frame = DecisionFrame(public, object())
                return self._frame
            require(value['observation'] is None and value['decision_id'] is None, 'idle_fields')
            if status == 'waiting':
                require(value['outcome'] is None, 'waiting_outcome')
                self._counts(value)
                self.pending = next_pending
                return None
            require(not next_pending and counts[1] == counts[2], 'incomplete_actions')
            require(value['outcome'] in (('victory', 'defeat', 'run_abandoned') if self.full else ('slice_complete', 'defeat')), 'outcome')
            self._counts(value)
            self.pending = False
            self.stopped = True
            if self.full:
                return c.RunOutcome('sts_run_outcome_v1', 'abandoned' if value['outcome'] == 'run_abandoned' else value['outcome'], 'none')
            return c.RunOutcome('sts_run_outcome_v1',
                                'defeat' if value['outcome'] == 'defeat' else 'truncated',
                                'none' if value['outcome'] == 'defeat' else 'slice_complete')
        except BaseException:
            self.stopped = True
            raise

    def step(self, binding, candidate_ref):
        require(not self.stopped, 'adapter_stopped')
        if self._frame is None or binding is not self._frame.binding:
            return c.ExecutionReport('sts_execution_report_v1', 'rejected', 'none', 'stale_decision')
        if candidate_ref not in {a.ref for a in self._frame.decision.candidates}:
            return c.ExecutionReport('sts_execution_report_v1', 'rejected', 'none', 'invalid_action')
        token, before = self._token, self.counts
        self._frame = self._token = None  # Consume even if transport later fails.
        body = bytearray(json.dumps({'decision_id': token, 'action_id': candidate_ref}, separators=(',', ':')).encode())
        was_pending = self.pending
        self.pending = True  # A request may mutate even when its receipt is lost.
        self.attempted += 1
        try:
            value = decode(self.request('POST', FULL_ACT if self.full else ACT, body), full=self.full)
            require(value['decision_id'] == token and value['action_id'] == candidate_ref, 'receipt_binding')
            counts = tuple(value[name] for name in ('attempted', 'accepted', 'reconciled'))
            if value['status'] == 'rejected':
                require(value['mutation_state'] == 'none' and value['reason'] == 'stale_decision', 'rejection')
                require(counts[0] in (before[0], before[0] + 1) and counts[1] == before[1] and
                        (before[2] <= counts[2] <= before[1] if self.full else counts[2] == before[2]), 'rejected_counts')
                self._counts(value)
                self.pending = value['pending'] > 0 if self.full else was_pending
                return c.ExecutionReport('sts_execution_report_v1', 'rejected', 'none', 'stale_decision')
            require(value['status'] == 'accepted' and value['code'] is None and
                    value['observation'] is None and value['outcome'] is None, 'receipt_status')
            require(counts[:2] == (before[0] + 1, before[1] + 1) and
                    (before[2] <= counts[2] <= before[1] if self.full else counts[2] == before[2]), 'accepted_counts')
            if self.full:
                require(value['pending'] > 0, 'accepted_pending')
            else:
                require(type(value['parent_pending']) is bool and type(value['child_pending']) is bool and
                        (value['parent_pending'] or value['child_pending']), 'accepted_pending')
            self.pending = True
            self._counts(value)
            return c.ExecutionReport('sts_execution_report_v1', 'pending', 'queued', 'none')
        except BaseException as error:
            self.stopped = True
            if not isinstance(error, Exception):
                raise
            return c.ExecutionReport('sts_execution_report_v1', 'uncertain', 'unknown', 'transport_failure')
        finally:
            body[:] = b'\0' * len(body)


def run_agent(request, *, policy=None, full=False, dispatch_map=False, stop_at_map=False, clock=time.monotonic, sleep=time.sleep,
              decision_limit=256, seconds=180.0, recorder=None):
    """Run a bounded shared-policy case; optionally stop at a reconciled map."""
    require(recorder is None or full, "recording_requires_full_agent")
    adapter = LiveAdapter(request, full=full)
    policy = policy or (choose_full_action if full else choose_action)
    deadline = clock() + seconds
    decisions = stale = stale_streak = 0
    kinds = set()
    outcome = None
    status, code = 'failed', 'time_limit'
    try:
        while clock() < deadline:
            frame = adapter.observe()
            require(clock() < deadline, 'deadline')
            if frame is None:
                sleep(min(0.05, max(0.0, deadline - clock())))
                continue
            if isinstance(frame, c.RunOutcome):
                outcome, status, code = c.to_dict(frame), 'resolved', None
                break
            if recorder is not None:
                recorder.observe(frame.decision, adapter.counts)
            kinds.add(frame.decision.context.kind)
            if (isinstance(frame.decision.context, c.MapChoice) and not dispatch_map or
                    full and stop_at_map and frame.decision.context.kind == 'map'):
                require(not adapter.pending, 'map_parent_pending')
                outcome = c.to_dict(c.RunOutcome('sts_run_outcome_v1', 'truncated', 'external_stop' if full else 'slice_complete'))
                status, code = 'resolved', None
                break
            require(decisions < decision_limit, 'decision_limit')
            # Callback receives no native state, binding, transport or tokens.
            candidate = policy(frame.decision)
            require(candidate in frame.decision.candidates, 'policy_action')
            require(clock() < deadline, 'deadline')
            report = adapter.step(frame.binding, candidate.ref)
            if recorder is not None:
                recorder.action(candidate, report, adapter.counts)
            if report.status == 'rejected' and report.reason == 'stale_decision':
                stale += 1
                stale_streak += 1
                # Long full runs can cross many independently changing native
                # frames. Bound retries without accepted progress, while still
                # reporting every rejection and retaining the legacy total cap.
                require((stale_streak if full else stale) <= 3, 'stale_limit')
                continue
            require(report.status == 'pending', 'uncertain_dispatch')
            stale_streak = 0
            decisions += 1
        if clock() >= deadline:
            code = 'deadline_pending' if adapter.pending else 'time_limit'
    except KeyboardInterrupt:
        code = 'interrupted_pending' if adapter.pending else 'interrupted'
    except AgentFailure as error:
        code = str(error)
    except Exception:
        code = 'adapter_failure'
    except BaseException:
        if recorder is not None:
            recorder.abort()
        raise
    if recorder is not None:
        try:
            if status == 'resolved' and not adapter.pending and outcome is not None:
                recorder.finish(c.from_dict(outcome), adapter.counts)
        except Exception:
            status, code = 'failed', 'recording_failed'
        finally:
            recorder.abort()
    return {'schema_version': 1, 'status': status, 'code': code, 'outcome': outcome,
            'decisions': decisions, 'reads': adapter.reads, 'stale_rejections': stale,
            'attempted': adapter.attempted, 'accepted': adapter.counts[1], 'reconciled': adapter.counts[2],
            'pending': adapter.pending, 'decision_kinds': sorted(kinds)}
