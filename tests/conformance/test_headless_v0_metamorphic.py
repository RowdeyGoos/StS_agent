"""Bounded generated prefixes over the accepted reduced backend, not game parity.

Only advertised candidates are selected. Each of 24 seeded cases stops within
300 accepted transitions. Failures report candidate indices through the first
failing boundary (a shortest failing prefix of that generated execution), never
private snapshots, complete record streams, or unbounded fuzz output.
"""

from copy import deepcopy
from dataclasses import dataclass
from random import Random
from typing import Any

import pytest

from game.backends.headless.reduced_run_backend import HeadlessRunConfig, ReducedRunBackend
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.contracts.headless_v0 import (
    ActionRequest,
    CandidateKind,
    DecisionPhase,
    DecisionState,
    DecisionStatus,
    HeadlessBinding,
    TransitionReason,
    TransitionResult,
    canonical_json,
)


MAX_TRANSITIONS = 300


@dataclass(frozen=True)
class GeneratedCase:
    scenario: str
    game_seed: int
    route: str

    @property
    def prefix_seed(self) -> int:
        return self.game_seed + 1009

    @property
    def label(self) -> str:
        return f"{self.scenario}-{self.game_seed}-{self.route}"

    def config(self) -> HeadlessRunConfig:
        # A generous accepted draw/energy configuration keeps phase coverage
        # reachable even with random card order. Nibbit's HP is not configurable.
        settings: dict[str, Any] = {
            "initial_hp": 60,
            "combat_settings": {"cards_per_turn": 10, "energy_per_turn": 10},
        }
        if self.scenario == "simple__starter":
            settings["combat_settings"]["enemy_max_hp"] = 12
        if self.route == "defeat":
            settings = {"initial_hp": 1}
        elif self.route == "unsupported":
            settings["initial_hp"] = 80
            settings["event_id"] = "cool_spring"
        return HeadlessRunConfig(self.scenario, CONTENT_FINGERPRINT, self.game_seed, settings)


CASES = tuple(
    GeneratedCase(scenario, seed, route)
    for scenario in ("simple__starter", "nibbit__starter")
    for seed in (0, 7, 23)
    for route in ("rest", "event", "defeat", "unsupported")
)
assert len(CASES) == 24


def _check(condition: bool, case: GeneratedCase, prefix: list[int], operation: str) -> None:
    if not condition:
        pytest.fail(
            f"{case.label}; prefix_seed={case.prefix_seed}; "
            f"candidate_index_prefix={prefix}; operation={operation}",
            pytrace=False,
        )


def _request(decision: DecisionState, index: int) -> ActionRequest:
    return ActionRequest(HeadlessBinding.for_candidate(decision, decision.candidates[index].candidate_id))


def _generated_index(decision: DecisionState, rng: Random, case: GeneratedCase) -> int:
    indices = list(range(len(decision.candidates)))
    # Guide only route coverage and the defeat control. All other decisions,
    # including combat ordering and reward choices, use a private seeded RNG.
    if decision.phase is DecisionPhase.MAP:
        desired = "event" if case.route == "unsupported" else case.route
        nodes = {node["node_ref"]: node["kind"] for node in decision.observation.data["nodes"]}
        preferred = [index for index in indices if nodes[decision.candidates[index].node_ref] == desired]
        indices = preferred or indices
    elif decision.phase is DecisionPhase.COMBAT and case.route == "defeat":
        indices = [index for index in indices if decision.candidates[index].kind is CandidateKind.COMBAT_END_TURN]
    elif decision.phase is DecisionPhase.COMBAT and case.route == "unsupported":
        # This control needs a full-HP arrival: play the complete hand in seeded
        # order before ending a turn. The advertised starter blocks protect HP.
        playable = [index for index in indices if decision.candidates[index].kind is CandidateKind.COMBAT_PLAY_CARD]
        indices = playable or indices
    return rng.choice(indices)


def _insert_observations_and_rejections(
    backend: ReducedRunBackend,
    decision: DecisionState,
    previous: ActionRequest | None,
    case: GeneratedCase,
    prefix: list[int],
    repeats: int,
) -> None:
    before = canonical_json(backend.snapshot())
    counters = backend.rng_stream_counters
    for _ in range(repeats):
        _check(backend.observe() == decision, case, prefix, "extra-observe")
        _check(canonical_json(backend.snapshot()) == before, case, prefix, "extra-snapshot")
    invalid = ActionRequest(HeadlessBinding(
        decision.run_id, decision.decision_sequence, decision.decision_hash, "cand." + "0" * 64,
    ))
    stale = previous or ActionRequest(HeadlessBinding(
        decision.run_id, decision.decision_sequence + 1, decision.decision_hash, invalid.binding.candidate_id,
    ))
    for request, result, reason in (
        (invalid, TransitionResult.REJECTED, TransitionReason.INVALID_CANDIDATE),
        (stale, TransitionResult.STALE, TransitionReason.STALE_BINDING),
    ):
        transition = backend.apply(request)
        _check(transition.result is result and transition.reason is reason, case, prefix, f"{result.value}-receipt")
        _check(transition.binding == request.binding, case, prefix, "rejection-binding")
        _check(transition.next_decision == decision, case, prefix, "rejection-decision")
        _check(backend.rng_stream_counters == counters, case, prefix, "rejection-rng-counters")
        # Full serialization includes the world RNG and combat child RNG, not
        # just counters or the public decision hash.
        _check(canonical_json(backend.snapshot()) == before, case, prefix, "rejection-private-state")


def _replay_suffix(
    backend: ReducedRunBackend,
    case: GeneratedCase,
    checkpoint: int,
    prefix: list[int],
    decisions: list[str],
    transitions: list[str],
    snapshots: list[str],
    operation: str,
) -> None:
    _check(backend.observe().to_json() == decisions[checkpoint], case, prefix[:checkpoint], operation + "-restore")
    _check(canonical_json(backend.snapshot()) == snapshots[checkpoint], case, prefix[:checkpoint], operation + "-snapshot")
    for index in range(checkpoint, len(prefix)):
        transition = backend.apply(_request(backend.observe(), prefix[index]))
        # Stop immediately at the first mismatch, omitting the unneeded tail.
        _check(transition.to_json() == transitions[index], case, prefix[:index + 1], operation + "-transition")
        _check(canonical_json(backend.snapshot()) == snapshots[index + 1], case, prefix[:index + 1], operation + "-private-state")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.label)
def test_generated_prefixes_preserve_rejections_reads_and_branch_restore(case: GeneratedCase) -> None:
    source, perturbed, branch = ReducedRunBackend(), ReducedRunBackend(), ReducedRunBackend()
    prefix: list[int] = []
    try:
        decision = source.reset(case.config())
        _check(perturbed.reset(case.config()) == decision, case, [], "reset")
        rng = Random(case.prefix_seed)
        probe_rng = Random(case.prefix_seed + 2003)
        checkpoint_rng = Random(case.prefix_seed + 4001)
        decisions, transitions, snapshots = [], [], []
        # Reservoir sampling picks a generated interior boundary for each phase
        # rather than always reusing the fixed suite's first phase boundary.
        checkpoints: dict[DecisionPhase, tuple[int, dict[str, Any]]] = {}
        phase_counts: dict[DecisionPhase, int] = {}
        previous = None
        for step in range(MAX_TRANSITIONS + 1):
            decisions.append(decision.to_json())
            snapshots.append(canonical_json(source.snapshot()))
            phase_counts[decision.phase] = phase_counts.get(decision.phase, 0) + 1
            if checkpoint_rng.randrange(phase_counts[decision.phase]) == 0:
                checkpoints[decision.phase] = (step, deepcopy(source.snapshot()))
            _insert_observations_and_rejections(
                perturbed, decision, previous, case, prefix, probe_rng.randint(1, 3),
            )
            _check(canonical_json(perturbed.snapshot()) == snapshots[-1], case, prefix, "perturbed-boundary")
            if decision.status is not DecisionStatus.ACTIONABLE:
                _check(decision.candidates == (), case, prefix, "empty-candidates")
                break
            _check(step < MAX_TRANSITIONS, case, prefix, "300-transition-cap")
            index = _generated_index(decision, rng, case)
            previous = _request(decision, index)
            prefix.append(index)
            transition = source.apply(previous)
            _check(transition.result is TransitionResult.ACCEPTED, case, prefix, "generated-candidate-accepted")
            transitions.append(transition.to_json())
            _check(perturbed.apply(previous).to_json() == transitions[-1], case, prefix, "perturbed-continuation")
            decision = transition.next_decision

        expected_phases = {DecisionPhase.COMBAT, DecisionPhase.TERMINAL}
        if case.route == "unsupported":
            expected_phases = {DecisionPhase.COMBAT, DecisionPhase.REWARD, DecisionPhase.MAP, DecisionPhase.UNSUPPORTED}
            _check(decision.status is DecisionStatus.UNSUPPORTED, case, prefix, "unsupported-stop")
            _check(source.unsupported_reason == "room_unavailable", case, prefix, "unsupported-reason")
        else:
            _check(decision.status is DecisionStatus.TERMINAL, case, prefix, "terminal-stop")
            _check(source.terminal_reason == ("defeat" if case.route == "defeat" else "route_complete"), case, prefix, "terminal-reason")
            if case.route != "defeat":
                expected_phases |= {DecisionPhase.REWARD, DecisionPhase.MAP, DecisionPhase.ROOM}
        _check(set(phase_counts) == expected_phases, case, prefix, "phase-coverage")

        for phase, (checkpoint, saved) in checkpoints.items():
            saved_json = canonical_json(saved)
            branch.restore(saved)
            _replay_suffix(branch, case, checkpoint, prefix, decisions, transitions, snapshots, "A")
            branch.restore(saved)
            branch_rng = Random(case.prefix_seed + checkpoint + 6007)
            alternate_prefix: list[int] = []
            for offset in range(min(branch_rng.randint(1, 4), MAX_TRANSITIONS - checkpoint)):
                current = branch.observe()
                if current.status is not DecisionStatus.ACTIONABLE:
                    break
                candidates = list(range(len(current.candidates)))
                if offset == 0 and len(candidates) > 1:
                    candidates.remove(prefix[checkpoint])
                alternate_prefix.append(branch_rng.choice(candidates))
                receipt = branch.apply(_request(current, alternate_prefix[-1]))
                _check(receipt.result is TransitionResult.ACCEPTED, case, prefix[:checkpoint], f"B={alternate_prefix}")
            _check(canonical_json(saved) == saved_json, case, prefix[:checkpoint], "snapshot-aliasing")
            branch.restore(saved)
            _replay_suffix(
                branch, case, checkpoint, prefix, decisions, transitions, snapshots,
                f"A-after-B={alternate_prefix}-at-{phase.value}:{checkpoint}",
            )
    except Exception as error:
        # Unexpected production errors must not dump private objects via pytest.
        _check(False, case, prefix, f"unexpected-{type(error).__name__}")
    finally:
        source.close()
        perturbed.close()
        branch.close()
