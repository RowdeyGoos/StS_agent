"""HF13: source-backed Strike rule inside an explicitly synthetic combat profile."""

from copy import deepcopy
from dataclasses import replace
import json

import pytest

from game.agents.baselines import choose_heuristic_action
from game.agents.headless_encoding import ENTITY_FEATURE_NAMES, encode_policy_view
from game.analysis.bruteforce import clone_combat_env
from game.backends.headless.combat_candidates import CombatCandidateError, generate_combat_candidates
from game.backends.headless.combat_projection import CombatProjectionError, project_combat_observation
from game.backends.headless.combat_v0_backend import CombatV0Backend, CombatV0BackendError
from game.content.card_upgrades import STRIKE_UPGRADE_PROFILE
from game.contracts.headless_v0 import (
    ActionRequest, CombatEndTurnCandidate, CombatOutcome, CombatPlayCardCandidate,
    DecisionPhase, DecisionStatus, HeadlessBinding, TransitionResult,
)
from game.data.headless_policy_dataset import ActorDatasetValidationError, _validate_accepted_pins
from game.engine.card_upgrades import preview_card_upgrade, upgrade_persistent_card
from game.engine.headless_state import StateValidationError, WorldState
from game.engine.snapshots import PrivateWorldSnapshot, SnapshotValidationError, WorldSnapshotCodec
from game.simulation.action_features import summarize_action
from game.simulation.encoding import DEFAULT_CARD_NAME_TO_ID


def _backend():
    return CombatV0Backend(card_profile=STRIKE_UPGRADE_PROFILE)


def _world():
    manifest = _backend().manifest()
    return WorldState.create(
        seed=43, current_hp=80, max_hp=80, gold=17,
        deck_definition_ids=("strike", "strike", "defend"), map_node_definitions=(),
        content_fingerprint=manifest.content_fingerprint,
        rules_fingerprint=manifest.rules_fingerprint,
    )


def _upgraded_world():
    world = _world()
    upgrade_persistent_card(world, world.master_deck[0].instance_id)
    return world


def _request(decision, candidate):
    return ActionRequest(HeadlessBinding.for_candidate(decision, candidate.candidate_id))


def _play(decision, *, upgraded):
    card = next(card for card in decision.observation.data["hand"]
                if card["card_definition_id"] == "strike" and card["upgraded"] is upgraded)
    return next(candidate for candidate in decision.candidates
                if isinstance(candidate, CombatPlayCardCandidate) and candidate.card_ref == card["card_ref"])


def _end_turn(decision):
    return next(candidate for candidate in decision.candidates
                if isinstance(candidate, CombatEndTurnCandidate))


def _codec(world):
    return WorldSnapshotCodec(world.content_fingerprint, world.rules_fingerprint)


def test_preview_and_upgrade_preserve_exact_identity_position_rng_and_other_state():
    world = _world()
    target = world.master_deck[0]
    before = world.to_private_dict()
    preview = preview_card_upgrade(world, target.instance_id)
    assert (preview.cost, preview.base_damage, preview.uses_target) == (1, 9, True)
    assert world.to_private_dict() == before
    upgraded = upgrade_persistent_card(world, target.instance_id)
    assert upgraded == replace(target, upgraded=True)
    expected = deepcopy(before)
    expected["master_deck"][0]["upgraded"] = True
    assert world.to_private_dict() == expected
    assert world.master_deck[1].upgraded is False
    restored = _codec(world).restore(PrivateWorldSnapshot.from_json(_codec(world).capture(world).to_json()))
    assert restored.to_private_dict() == expected


@pytest.mark.parametrize("case", ("unknown", "unsupported", "repeat", "active", "wrong_content", "dead", "map"))
def test_invalid_upgrade_and_preview_are_atomic(case):
    world = _world()
    target = world.master_deck[0].instance_id
    if case == "unknown":
        target = "card.missing.00000000"
    elif case == "unsupported":
        target = world.master_deck[2].instance_id
    elif case == "repeat":
        upgrade_persistent_card(world, target)
    elif case == "active":
        world.create_combat_launch("simple__starter")
    elif case == "wrong_content":
        world.content_fingerprint = CombatV0Backend().manifest().content_fingerprint
    elif case == "dead":
        world.current_hp = 0
    elif case == "map":
        world.phase = DecisionPhase.MAP
    before = world.to_private_dict()
    for operation in (preview_card_upgrade, upgrade_persistent_card):
        with pytest.raises(StateValidationError):
            operation(world, target)
        assert world.to_private_dict() == before


def test_two_combats_preserve_upgrade_and_replay_exact_damage_and_cost():
    world = _upgraded_world()
    deck = world.master_deck
    for _ in range(2):
        backend = _backend()
        launch = world.create_combat_launch("simple__starter", combat_settings={"enemy_max_hp": 14})
        assert launch.ordered_deck == deck
        decision = backend.reset(launch)
        hands = decision.observation.data["hand"]
        assert sorted(card["upgraded"] for card in hands if card["card_definition_id"] == "strike") == [False, True]
        assert all(card["cost"] == 1 for card in hands)
        # Existing public encoding distinguishes the variants with no schema change.
        encoded = encode_policy_view(decision.policy_view())
        upgrade_column = ENTITY_FEATURE_NAMES.index("card_upgraded")
        assert sum(row[upgrade_column] for row in encoded.entity_rows) == 1
        public_json = repr(decision.policy_view())
        assert all(card.instance_id not in public_json for card in deck)
        assert world.run_id not in public_json
        env = backend._environment
        legacy = CombatV0Backend()
        legacy.reset(replace(launch, ordered_deck=tuple(replace(c, upgraded=False) for c in deck)))
        assert env.observation_size > legacy._environment.observation_size
        observation = env.get_observation()
        for index, name in enumerate(observation["hand"]):
            if name.startswith("Strike"):
                summary = summarize_action(observation, ("play", index))
                assert summary.damage_to_target == (9 if name == "Strike+" else 6)
                assert env.get_action_mask()[env.encode_action(("play", index))]
        env.encode_observation()
        env.encode_action_features()
        selected = choose_heuristic_action(env, observation)
        assert env.get_action_mask()[selected]
        first_request = _request(decision, _play(decision, upgraded=False))
        after_base = backend.apply(first_request).next_decision
        assert after_base.observation.data["enemies"][0]["hp"] == 8
        assert after_base.observation.data["player"]["energy"] == 2
        saved = backend.snapshot()
        restored = _backend()
        assert restored.restore(json.loads(json.dumps(saved))) == after_base
        # Reusing a consumed request cannot consume energy or apply damage twice.
        assert backend.apply(first_request).result is TransitionResult.STALE
        assert backend.snapshot() == saved
        request = _request(after_base, _play(after_base, upgraded=True))
        final = backend.apply(request)
        assert final == restored.apply(request)
        assert final.next_decision.status is DecisionStatus.TERMINAL
        assert backend._environment.player.energy == 1
        assert backend.resolution.outcome is CombatOutcome.VICTORY
        assert backend.snapshot() == restored.snapshot()
        terminal_copy = _backend()
        assert terminal_copy.restore(backend.snapshot()) == final.next_decision
        world.apply_combat_resolution(launch, backend.resolution)
        world = _codec(world).restore(_codec(world).capture(world))
        assert world.master_deck == deck
    assert world.rng_stream_counters()["combat_launch"] == 2


def test_upgrade_identity_survives_discard_reshuffle_and_search_clone():
    world = _upgraded_world()
    target_id = world.master_deck[0].instance_id
    backend = _backend()
    decision = backend.reset(world.create_combat_launch("simple__starter", combat_settings={"enemy_max_hp": 100}))
    backend.apply(_request(decision, _play(decision, upgraded=True)))
    env = backend._environment
    played = next(card for card in env.player.deck.discard_pile if card.name == "Strike+")
    assert played.persistent_instance_id == target_id
    clone = clone_combat_env(env)
    before = env.get_observation()
    clone.step(("end_turn",))
    assert env.get_observation() == before
    cloned_card = next(card for card in clone.player.hand if card.name == "Strike+")
    assert cloned_card.persistent_instance_id == target_id
    decision = backend.observe()
    decision = backend.apply(_request(decision, _end_turn(decision))).next_decision
    redrawn = next(card for card in backend._environment.player.hand if card.name == "Strike+")
    assert redrawn is played
    assert redrawn.persistent_instance_id == target_id
    restored = _backend()
    assert restored.restore(backend.snapshot()) == decision
    assert [(c.persistent_instance_id, c.name) for c in restored._environment.player.hand] == [(c.persistent_instance_id, c.name) for c in backend._environment.player.hand]


def test_targeted_upgrade_candidates_hit_only_the_selected_enemy():
    world = _upgraded_world()
    backend = _backend()
    decision = backend.reset(world.create_combat_launch("nibbits__starter"))
    card = next(card for card in decision.observation.data["hand"] if card["upgraded"])
    candidates = [candidate for candidate in decision.candidates
                  if isinstance(candidate, CombatPlayCardCandidate) and candidate.card_ref == card["card_ref"]]
    enemies = decision.observation.data["enemies"]
    assert len(candidates) == len(enemies) > 1
    saved = backend.snapshot()
    for candidate in candidates:
        fork = _backend()
        fork.restore(saved)
        result = fork.apply(_request(decision, candidate))
        after = result.next_decision.observation.data["enemies"]
        for old, new in zip(enemies, after):
            assert old["hp"] - new["hp"] == (9 if candidate.target_ref == old["enemy_ref"] else 0)


def test_zero_energy_suppresses_upgrade_play_and_profile_rejections_are_atomic():
    world = _upgraded_world()
    backend = _backend()
    decision = backend.reset(world.create_combat_launch("simple__starter", combat_settings={"energy_per_turn": 1}))
    decision = backend.apply(_request(decision, _play(decision, upgraded=False))).next_decision
    assert len(decision.candidates) == 1
    assert isinstance(decision.candidates[0], CombatEndTurnCandidate)
    saved = backend.snapshot()
    bad = replace(backend.launch_spec, ordered_deck=tuple(replace(card, upgraded=True) for card in world.master_deck))
    with pytest.raises(CombatV0BackendError, match="upgraded"):
        backend.reset(bad)
    assert backend.snapshot() == saved
    legacy = CombatV0Backend()
    legacy.reset("simple__starter")
    old_snapshot = legacy.snapshot()
    with pytest.raises(CombatV0BackendError, match="upgraded"):
        legacy.reset(backend.launch_spec)
    assert legacy.snapshot() == old_snapshot
    for target, snapshot in ((legacy, saved), (backend, old_snapshot)):
        before = target.snapshot()
        with pytest.raises(CombatV0BackendError, match="fingerprint"):
            target.restore(snapshot)
        assert target.snapshot() == before
    with pytest.raises(CombatProjectionError, match="unsupported"):
        project_combat_observation(backend._environment.get_observation(), decision.observation.public_scope)
    # Candidate adapter rejection needs an affordable variant in hand.
    backend._environment.player.energy = 1
    with pytest.raises(CombatCandidateError, match="closed projection registry"):
        generate_combat_candidates(backend._environment, decision.observation.public_scope)


def test_profiles_have_distinct_evidence_and_cannot_relabel_accepted_data_or_world_snapshots():
    legacy = CombatV0Backend().manifest()
    upgraded = _backend().manifest()
    assert upgraded.backend_id == legacy.backend_id
    assert upgraded.contract_fingerprint == legacy.contract_fingerprint
    for name in ("backend_fingerprint", "content_fingerprint", "rules_fingerprint"):
        assert getattr(upgraded, name) != getattr(legacy, name)
    assert upgraded.capabilities.live_truth is False
    with pytest.raises(ActorDatasetValidationError, match="pins"):
        _validate_accepted_pins(legacy, upgraded)
    world = _upgraded_world()
    old_codec = WorldSnapshotCodec(legacy.content_fingerprint, legacy.rules_fingerprint)
    with pytest.raises(SnapshotValidationError, match="incompatible"):
        old_codec.restore(_codec(world).capture(world))
    assert "Strike+" not in DEFAULT_CARD_NAME_TO_ID
    with pytest.raises(ValueError, match="Unsupported card profile"):
        CombatV0Backend(card_profile="future_all_upgrades")
