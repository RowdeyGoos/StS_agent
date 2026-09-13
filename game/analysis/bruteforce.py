"""Exact seeded combat search for oracle-policy comparisons.

The search treats the complete mutable combat state, including RNG state and pile
order, as part of a node.  It optimizes the project's intended combat objective
lexicographically: win first, preserve player HP, reduce remaining enemy HP, then
use fewer actions.
"""

from __future__ import annotations

from copy import copy, deepcopy
from dataclasses import dataclass, fields, is_dataclass
import heapq
from random import Random
from time import monotonic
from typing import Any, Callable, Hashable, Mapping

from ..simulation.actions import CombatAction
from ..simulation.card import get_card_spec
from ..simulation.core import CombatEnv, Observation
from ..simulation.status import StatusCollection

OracleScore = tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class OracleStep:
    """One action in a best combat line returned by the oracle search."""

    step_index: int
    turn: int
    action_index: int
    action: CombatAction
    reward: float
    observation: Observation
    next_observation: Observation
    info: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of this step."""
        return {
            "step_index": self.step_index,
            "turn": self.turn,
            "action_index": self.action_index,
            "action": list(self.action),
            "reward": self.reward,
            "observation": self.observation,
            "next_observation": self.next_observation,
            "info": self.info,
        }


@dataclass(frozen=True, slots=True)
class BruteForceProgress:
    """Periodic progress snapshot for long-running searches."""

    expanded_nodes: int
    generated_nodes: int
    unique_states: int
    frontier_size: int
    elapsed_seconds: float
    best_player_hp: int | None
    best_steps: int | None


@dataclass(frozen=True, slots=True)
class BruteForceResult:
    """Result of one bounded exhaustive combat search."""

    objective: str
    proven_optimal: bool
    termination_reason: str
    expanded_nodes: int
    generated_nodes: int
    unique_states: int
    elapsed_seconds: float
    max_steps: int
    max_nodes: int
    time_limit_seconds: float | None
    initial_observation: Observation
    steps: tuple[OracleStep, ...]
    summary: dict[str, Any] | None

    @property
    def found_terminal(self) -> bool:
        """Return whether the search found at least one finished combat line."""
        return self.summary is not None

    @property
    def found_win(self) -> bool:
        """Return whether the best finished line is a player victory."""
        return self.summary is not None and self.summary.get("winner") == "player"

    @property
    def action_indices(self) -> tuple[int, ...]:
        """Return the best line as discrete action indices."""
        return tuple(step.action_index for step in self.steps)

    @property
    def actions(self) -> tuple[CombatAction, ...]:
        """Return the best line using the readable tuple action API."""
        return tuple(step.action for step in self.steps)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable result payload."""
        return {
            "objective": self.objective,
            "proven_optimal": self.proven_optimal,
            "termination_reason": self.termination_reason,
            "expanded_nodes": self.expanded_nodes,
            "generated_nodes": self.generated_nodes,
            "unique_states": self.unique_states,
            "elapsed_seconds": self.elapsed_seconds,
            "max_steps": self.max_steps,
            "max_nodes": self.max_nodes,
            "time_limit_seconds": self.time_limit_seconds,
            "initial_observation": self.initial_observation,
            "steps": [step.as_dict() for step in self.steps],
            "summary": self.summary,
        }


@dataclass(slots=True)
class _FrontierNode:
    env: CombatEnv
    path: tuple[int, ...]
    state_key: Hashable
    upper_bound: OracleScore


class _RngStateRegistry:
    """Intern large Random states so search keys stay compact without losing data."""

    def __init__(self) -> None:
        self._tokens: dict[object, int] = {}

    def token(self, rng: Random) -> int:
        state = rng.getstate()
        token = self._tokens.get(state)
        if token is not None:
            return token
        token = len(self._tokens)
        self._tokens[state] = token
        return token


class _CardStateRegistry:
    """Read current instance state; mutable cards cannot use an identity-only cache."""

    def key(self, card: object) -> Hashable:
        return _freeze(card)


def brute_force_combat(
    env: CombatEnv,
    *,
    max_steps: int = 40,
    max_nodes: int = 250_000,
    time_limit_seconds: float | None = None,
    progress_callback: Callable[[BruteForceProgress], None] | None = None,
    progress_interval: int = 10_000,
) -> BruteForceResult:
    """Find the best action sequence from an initialized combat state.

    The objective is lexicographic: a win beats a loss, then higher terminal
    player HP is better, then lower remaining enemy HP is better, then fewer
    player decisions are better.  For victories, remaining enemy HP is always
    zero, so this is the intended "win while preserving HP" objective.

    The input environment is not mutated.  ``proven_optimal`` is true only when
    the solver either exhausts every reachable continuation or proves that no
    frontier state can beat the best victory.  Resource limits therefore never
    silently turn an approximate result into an "optimal" one.
    """
    if max_steps < 0:
        raise ValueError("max_steps cannot be negative.")
    if max_nodes <= 0:
        raise ValueError("max_nodes must be positive.")
    if time_limit_seconds is not None and time_limit_seconds <= 0.0:
        raise ValueError("time_limit_seconds must be positive when provided.")
    if progress_interval <= 0:
        raise ValueError("progress_interval must be positive.")

    env.get_observation()  # Validate that reset() has already been called.
    root_env = clone_combat_env(env)
    root_env.record_trajectory = False
    root_env.episode_transitions = []
    initial_observation = deepcopy(root_env.get_observation())
    started_at = monotonic()
    if root_env.done:
        steps, summary = _replay_path(root_env, ())
        return BruteForceResult(
            objective="win_then_hp_then_enemy_hp_then_steps",
            proven_optimal=True,
            termination_reason="already_terminal",
            expanded_nodes=0,
            generated_nodes=1,
            unique_states=1,
            elapsed_seconds=monotonic() - started_at,
            max_steps=max_steps,
            max_nodes=max_nodes,
            time_limit_seconds=time_limit_seconds,
            initial_observation=initial_observation,
            steps=steps,
            summary=summary,
        )
    rng_registry = _RngStateRegistry()
    card_registry = _CardStateRegistry()
    root_key = _combat_state_key(root_env, rng_registry, card_registry)

    frontier: list[tuple[int, int, int, int, _FrontierNode]] = []
    sequence_number = 0
    root_node = _FrontierNode(
        env=root_env,
        path=(),
        state_key=root_key,
        upper_bound=_winning_upper_bound(root_env, 0),
    )
    heapq.heappush(frontier, _frontier_entry(root_node, sequence_number))
    best_steps_by_state: dict[Hashable, int] = {root_key: 0}

    best_score: OracleScore | None = None
    best_path: tuple[int, ...] | None = None
    cutoff_upper_bound: OracleScore | None = None
    expanded_nodes = 0
    generated_nodes = 1
    stopped_by_limit: str | None = None
    proof_from_frontier_bound = False

    while frontier:
        _neg_hp, _enemy_hp, _steps, _sequence, node = heapq.heappop(frontier)
        node_steps = len(node.path)
        if best_steps_by_state.get(node.state_key) != node_steps:
            continue

        node_upper_bound = node.upper_bound
        if best_score is not None and node_upper_bound <= best_score:
            continue

        if expanded_nodes >= max_nodes:
            stopped_by_limit = "max_nodes"
            cutoff_upper_bound = _max_score(cutoff_upper_bound, node_upper_bound)
            break
        if (
            time_limit_seconds is not None
            and monotonic() - started_at >= time_limit_seconds
        ):
            stopped_by_limit = "time_limit"
            cutoff_upper_bound = _max_score(cutoff_upper_bound, node_upper_bound)
            break
        if node_steps >= max_steps:
            cutoff_upper_bound = _max_score(cutoff_upper_bound, node_upper_bound)
            continue

        expanded_nodes += 1
        best_improved = False
        for action in _unique_legal_actions(node.env, card_registry):
            child_env = clone_combat_env(node.env)
            action_index = child_env.encode_action(action)
            child_env.step(action)
            child_path = (*node.path, action_index)
            generated_nodes += 1

            if child_env.done:
                child_score = _terminal_score(child_env, len(child_path))
                if best_score is None or child_score > best_score:
                    best_score = child_score
                    best_path = child_path
                    best_improved = True
                continue

            child_key = _combat_state_key(child_env, rng_registry, card_registry)
            previous_steps = best_steps_by_state.get(child_key)
            if previous_steps is not None and previous_steps <= len(child_path):
                continue
            best_steps_by_state[child_key] = len(child_path)
            sequence_number += 1
            child_node = _FrontierNode(
                env=child_env,
                path=child_path,
                state_key=child_key,
                upper_bound=_winning_upper_bound(child_env, len(child_path)),
            )
            heapq.heappush(frontier, _frontier_entry(child_node, sequence_number))

        if best_improved and best_score is not None:
            frontier_upper_bound = _frontier_upper_bound(
                frontier,
                best_steps_by_state,
            )
            unresolved_upper_bound = cutoff_upper_bound
            if frontier_upper_bound is not None:
                unresolved_upper_bound = _max_score(
                    unresolved_upper_bound,
                    frontier_upper_bound,
                )
            if (
                unresolved_upper_bound is None
                or unresolved_upper_bound <= best_score
            ):
                proof_from_frontier_bound = True
                break

        if progress_callback is not None and expanded_nodes % progress_interval == 0:
            best_player_hp = None if best_score is None else best_score[1]
            best_steps = None if best_score is None else -best_score[3]
            progress_callback(
                BruteForceProgress(
                    expanded_nodes=expanded_nodes,
                    generated_nodes=generated_nodes,
                    unique_states=len(best_steps_by_state),
                    frontier_size=len(frontier),
                    elapsed_seconds=monotonic() - started_at,
                    best_player_hp=best_player_hp,
                    best_steps=best_steps,
                )
            )

    if frontier:
        frontier_upper_bound = _frontier_upper_bound(frontier, best_steps_by_state)
        if frontier_upper_bound is not None:
            cutoff_upper_bound = _max_score(cutoff_upper_bound, frontier_upper_bound)

    no_unresolved_better_line = (
        best_score is not None
        and (cutoff_upper_bound is None or cutoff_upper_bound <= best_score)
    )
    exhausted_without_cutoff = not frontier and cutoff_upper_bound is None
    proven_optimal = (
        proof_from_frontier_bound
        or exhausted_without_cutoff
        or no_unresolved_better_line
    )

    if proven_optimal:
        termination_reason = (
            "search_exhausted"
            if exhausted_without_cutoff
            else "frontier_hp_bound"
        )
    elif stopped_by_limit is not None:
        termination_reason = stopped_by_limit
    elif cutoff_upper_bound is not None:
        termination_reason = "max_steps"
    else:
        termination_reason = "no_terminal_line"

    steps, summary = _replay_path(root_env, best_path)
    return BruteForceResult(
        objective="win_then_hp_then_enemy_hp_then_steps",
        proven_optimal=proven_optimal,
        termination_reason=termination_reason,
        expanded_nodes=expanded_nodes,
        generated_nodes=generated_nodes,
        unique_states=len(best_steps_by_state),
        elapsed_seconds=monotonic() - started_at,
        max_steps=max_steps,
        max_nodes=max_nodes,
        time_limit_seconds=time_limit_seconds,
        initial_observation=initial_observation,
        steps=steps,
        summary=summary,
    )


def clone_combat_env(env: CombatEnv) -> CombatEnv:
    """Clone only mutable episode state while sharing immutable configuration."""
    cloned_env = copy(env)
    memo: dict[int, Any] = {}

    # ``deepcopy(Random)`` reconstructs hundreds of Python integers for every
    # branch. Copy RNGs through their C-backed state API instead, while using
    # one memo entry per source object to preserve shared-RNG identity.
    rng_owners = [env.rng]
    if env.player is not None:
        rng_owners.extend((env.player.deck.rng, env.player.deck.selection_rng, env.player.deck.target_rng))
    if env.enemies is not None:
        rng_owners.extend(enemy.rng for enemy in env.enemies)
    for source_rng in rng_owners:
        if id(source_rng) in memo:
            continue
        cloned_rng = Random()
        cloned_rng.setstate(source_rng.getstate())
        memo[id(source_rng)] = cloned_rng

    cloned_env.rng = memo[id(env.rng)]
    if env.player is None:
        cloned_env.player = None
    else:
        source_player = env.player
        source_deck = source_player.deck
        cloned_deck = copy(source_deck)
        cloned_deck._allocated_ids = source_deck._allocated_ids.copy()
        cloned_deck.rng = memo[id(source_deck.rng)]
        cloned_deck.selection_rng = memo[id(source_deck.selection_rng)]
        cloned_deck.target_rng = memo[id(source_deck.target_rng)]
        cloned_deck.in_play = [deepcopy(card, memo) for card in source_deck.in_play]
        cloned_deck.draw_pile = [
            deepcopy(card, memo) for card in source_deck.draw_pile
        ]
        cloned_deck.discard_pile = [
            deepcopy(card, memo) for card in source_deck.discard_pile
        ]
        cloned_deck.exhaust_pile = [
            deepcopy(card, memo) for card in source_deck.exhaust_pile
        ]
        cloned_deck.hand = [deepcopy(card, memo) for card in source_deck.hand]

        cloned_player_statuses = copy(source_player.statuses)
        cloned_player_statuses._counts = source_player.statuses._counts.copy()
        cloned_player_statuses._skip_next_tick = source_player.statuses._skip_next_tick.copy()
        cloned_player = copy(source_player)
        cloned_player.deck = cloned_deck
        cloned_player.statuses = cloned_player_statuses
        cloned_player.power_sources = source_player.power_sources.copy()
        memo[id(source_player)] = cloned_player
        cloned_env.player = cloned_player

    if env.enemies is not None:
        for enemy in env.enemies:
            cloned_statuses = copy(enemy.statuses)
            cloned_statuses._counts = enemy.statuses._counts.copy()
            cloned_statuses._skip_next_tick = enemy.statuses._skip_next_tick.copy()
            memo[id(enemy.statuses)] = cloned_statuses
            for attribute_value in vars(enemy).values():
                dataclass_parameters = getattr(
                    type(attribute_value), "__dataclass_params__", None
                )
                if dataclass_parameters is not None and dataclass_parameters.frozen:
                    memo[id(attribute_value)] = attribute_value
    cloned_env.enemies = deepcopy(env.enemies, memo)
    if cloned_env.player is not None:
        cloned_env.player.combat_enemies = cloned_env.enemies
        for enemy in cloned_env.enemies or ():
            enemy.combat_player = cloned_env.player
    cloned_env.episode_transitions = []
    cloned_env.record_trajectory = False
    cloned_env.last_observation = cloned_env.get_observation()
    return cloned_env


def _frontier_entry(
    node: _FrontierNode,
    sequence_number: int,
) -> tuple[int, int, int, int, _FrontierNode]:
    assert node.env.player is not None
    assert node.env.enemies is not None
    enemy_hp = sum(enemy.hp for enemy in node.env.enemies if enemy.is_alive)
    return (
        -node.env.player.hp,
        enemy_hp,
        len(node.path),
        sequence_number,
        node,
    )


def _frontier_upper_bound(
    frontier: list[tuple[int, int, int, int, _FrontierNode]],
    best_steps_by_state: Mapping[Hashable, int],
) -> OracleScore | None:
    """Return the strongest winning bound among non-stale frontier nodes."""
    strongest_bound: OracleScore | None = None
    for _neg_hp, _enemy_hp, _steps, _sequence, node in frontier:
        node_steps = len(node.path)
        if best_steps_by_state.get(node.state_key) != node_steps:
            continue
        strongest_bound = _max_score(
            strongest_bound,
            node.upper_bound,
        )
    return strongest_bound


def _terminal_score(env: CombatEnv, steps: int) -> OracleScore:
    assert env.player is not None
    assert env.enemies is not None
    enemy_hp = sum(enemy.hp for enemy in env.enemies if enemy.is_alive)
    return (
        1 if env.winner == "player" else 0,
        env.player.hp,
        -enemy_hp,
        -steps,
    )


def _winning_upper_bound(env: CombatEnv, steps: int) -> OracleScore:
    """Return the best score any continuation could possibly achieve."""
    assert env.player is not None
    return (
        1,
        env.player.hp,
        0,
        -(steps + _minimum_actions_to_win_lower_bound(env)),
    )


def _minimum_actions_to_win_lower_bound(env: CombatEnv) -> int:
    """Return an optimistic lower bound on remaining damaging card plays."""
    assert env.player is not None
    assert env.enemies is not None
    living_enemies = [enemy for enemy in env.enemies if enemy.is_alive]
    if not living_enemies:
        return 0

    deck = env.player.deck
    maximum_damage = 0
    has_dynamic_damage = False
    seen_card_names: set[str] = set()
    for card in (
        *deck.draw_pile,
        *deck.discard_pile,
        *deck.exhaust_pile,
        *deck.hand,
    ):
        if card.name in seen_card_names:
            continue
        seen_card_names.add(card.name)
        card_spec = get_card_spec(card.name)
        has_dynamic_damage = has_dynamic_damage or card_spec.damage_equals_player_block
        damage_before_vulnerable = max(
            0,
            card_spec.base_damage + env.player.strength,
        )
        maximum_damage = max(
            maximum_damage,
            (damage_before_vulnerable * 3) // 2,
        )

    # One card can target at most one enemy. Ignoring energy, draw timing,
    # block, and incoming damage makes both terms optimistic and therefore safe.
    enemy_count_bound = len(living_enemies)
    if has_dynamic_damage:
        return enemy_count_bound
    if maximum_damage <= 0:
        return enemy_count_bound
    total_enemy_hp = sum(enemy.hp for enemy in living_enemies)
    damage_bound = (total_enemy_hp + maximum_damage - 1) // maximum_damage
    return max(enemy_count_bound, damage_bound)


def _max_score(
    first: OracleScore | None,
    second: OracleScore,
) -> OracleScore:
    return second if first is None or second > first else first


def _replay_path(
    root_env: CombatEnv,
    path: tuple[int, ...] | None,
) -> tuple[tuple[OracleStep, ...], dict[str, Any] | None]:
    if path is None:
        return (), None

    replay_env = clone_combat_env(root_env)
    replay_steps: list[OracleStep] = []
    for step_index, action_index in enumerate(path):
        observation = deepcopy(replay_env.get_observation())
        action = replay_env.decode_action(action_index)
        next_observation, reward, _done, info = replay_env.step_discrete(action_index)
        replay_steps.append(
            OracleStep(
                step_index=step_index,
                turn=int(observation["turn"]),
                action_index=action_index,
                action=action,
                reward=reward,
                observation=observation,
                next_observation=deepcopy(next_observation),
                info=deepcopy(info),
            )
        )
    return tuple(replay_steps), replay_env.get_episode_summary().as_dict()


def _unique_legal_actions(
    env: CombatEnv,
    card_registry: _CardStateRegistry,
) -> tuple[CombatAction, ...]:
    """Remove actions that provably produce the same complete child state.

    Duplicate cards are only collapsed when removing either card leaves the
    exact same ordered hand. This preserves discard order and its effect on a
    later seeded shuffle.
    """
    assert env.player is not None
    hand_keys = tuple(card_registry.key(card) for card in env.player.hand)
    seen_signatures: set[Hashable] = set()
    unique_actions: list[CombatAction] = []
    for action in env.get_legal_actions():
        if action[0] == "end_turn":
            unique_actions.append(action)
            continue
        hand_index = action[1]
        card_key = hand_keys[hand_index]
        signature = (
            card_key,
            hand_keys[:hand_index] + hand_keys[hand_index + 1 :],
            action[2:],
        )
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        unique_actions.append(action)
    return tuple(unique_actions)


def _combat_state_key(
    env: CombatEnv,
    rng_registry: _RngStateRegistry,
    card_registry: _CardStateRegistry,
) -> Hashable:
    """Return a lossless, hashable key for all future-relevant combat state."""
    assert env.player is not None
    assert env.enemies is not None
    player = env.player
    deck = player.deck

    rng_owners = [env.rng, deck.rng, deck.selection_rng, deck.target_rng,
                  *(enemy.rng for enemy in env.enemies)]
    rng_aliases: dict[int, int] = {}
    rng_references: list[int] = []
    rng_state_tokens: list[int] = []
    for rng in rng_owners:
        object_id = id(rng)
        alias = rng_aliases.get(object_id)
        if alias is None:
            alias = len(rng_aliases)
            rng_aliases[object_id] = alias
            rng_state_tokens.append(rng_registry.token(rng))
        rng_references.append(alias)

    player_state = (
        player.max_hp,
        player.hp,
        player.block,
        player.energy_per_turn,
        player.energy,
        player.strength,
        _freeze(player.statuses),
        player.cards_played_this_turn,
        _freeze(player.power_sources),
        tuple(card_registry.key(card) for card in deck.draw_pile),
        tuple(card_registry.key(card) for card in deck.discard_pile),
        tuple(card_registry.key(card) for card in deck.exhaust_pile),
        tuple(card_registry.key(card) for card in deck.hand),
    )
    enemy_states = tuple(
        (
            _type_name(enemy),
            tuple(
                sorted(
                    (attribute_name, _freeze(attribute_value))
                    for attribute_name, attribute_value in vars(enemy).items()
                    if attribute_name not in ("rng", "combat_player")
                )
            ),
        )
        for enemy in env.enemies
    )
    return (
        env.turn,
        player_state,
        enemy_states,
        tuple(rng_references),
        tuple(rng_state_tokens),
    )


def _freeze(value: Any) -> Hashable:
    """Convert current simulator values into lossless hashable structures."""
    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        return value
    if isinstance(value, StatusCollection):
        return (_type_name(value), tuple(sorted(value._counts.items())), tuple(sorted(value._skip_next_tick)))
    if isinstance(value, Mapping):
        return tuple(
            sorted(
                ((_freeze(key), _freeze(item)) for key, item in value.items()),
                key=lambda pair: repr(pair[0]),
            )
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted((_freeze(item) for item in value), key=repr))
    if is_dataclass(value):
        return (
            _type_name(value),
            tuple((field.name, _freeze(getattr(value, field.name))) for field in fields(value)),
        )
    if hasattr(value, "__dict__"):
        return (
            _type_name(value),
            tuple(
                sorted(
                    (attribute_name, _freeze(attribute_value))
                    for attribute_name, attribute_value in vars(value).items()
                )
            ),
        )
    raise TypeError(f"Cannot include value of type {type(value)!r} in combat state key.")


def _type_name(value: object) -> str:
    value_type = type(value)
    return f"{value_type.__module__}.{value_type.__qualname__}"
