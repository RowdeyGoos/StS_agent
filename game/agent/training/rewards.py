"""Versioned objectives and pure measurements of public combat transitions."""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.contracts.codec import _invalid_constant, _unique_object
from game.agent.headless.combat_summary import CombatSummary
from game.agent.progress import completed_act

SCHEMA = 'sts_training_reward_v1'
DEFAULT_WEIGHTS = (('combat_win', 1.0), ('combat_loss', 0.0), ('win_hp_fraction', 0.0),
                   ('end_turn_action', 0.0), ('potion_use_action', 0.0))
COMPONENTS = tuple(name for name, _ in DEFAULT_WEIGHTS)
POTENTIAL_SCHEMA = 'sts_training_reward_v2'
POTENTIAL_WEIGHTS = DEFAULT_WEIGHTS + (('enemy_hp_potential', 0.0), ('player_hp_potential', 0.0))
POTENTIAL_COMPONENTS = tuple(name for name, _ in POTENTIAL_WEIGHTS)
RUN_SCHEMA = 'sts_full_run_reward_v1'
RUN_WEIGHTS = tuple((name, 0.0) for name in COMPONENTS) + (('run_victory', 1.0),)
SHAPED_RUN_SCHEMA = 'sts_full_run_reward_v2'
SHAPED_RUN_WEIGHTS = RUN_WEIGHTS + (('run_defeat', 0.0), ('run_abandoned', 0.0))
SHAPED_RUN_COMPONENTS = tuple(name for name, _ in SHAPED_RUN_WEIGHTS)
ACT_RUN_SCHEMA = 'sts_full_run_reward_v3'
ACT_RUN_WEIGHTS = SHAPED_RUN_WEIGHTS + (('act_cleared', 0.0),)
ACT_RUN_COMPONENTS = tuple(name for name, _ in ACT_RUN_WEIGHTS)
SHAPED_RUN_SCHEMAS = (SHAPED_RUN_SCHEMA, ACT_RUN_SCHEMA)


class RewardError(ValueError):
    """Unsupported objective, missing measurement or invalid public transition."""


def strict_json(text):
    try:
        return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (ValueError, TypeError, RecursionError) as error:
        raise RewardError('Invalid or ambiguous JSON') from error


def finite(value):
    if type(value) not in (int, float):
        raise RewardError('Reward values must be finite numbers, not booleans')
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise RewardError('Reward value is not finite') from error
    if not math.isfinite(result):
        raise RewardError('Reward value is not finite')
    return result if result else 0.0


@dataclass(frozen=True, slots=True)
class RewardSpec:
    """Immutable resolved weights. Omitted weights keep their declared defaults."""
    weights: tuple[tuple[str, float], ...] = DEFAULT_WEIGHTS
    schema: str = SCHEMA
    goal: str | None = None
    discount: float | None = None

    def __post_init__(self):
        if self.schema not in (SCHEMA, POTENTIAL_SCHEMA, RUN_SCHEMA, SHAPED_RUN_SCHEMA, ACT_RUN_SCHEMA):
            raise RewardError('Unsupported reward schema')
        if self.schema == POTENTIAL_SCHEMA:
            discount = finite(self.discount)
            if not 0 < discount <= 1:
                raise RewardError('Potential shaping requires 0 < discount <= 1')
            object.__setattr__(self, 'discount', discount)
        elif self.discount is not None:
            raise RewardError('Only potential shaping declares a reward discount')
        if (self.schema == ACT_RUN_SCHEMA and self.goal not in ('act1', 'full_run') or
                self.schema != ACT_RUN_SCHEMA and self.goal is not None):
            raise RewardError('Full-run v3 requires an explicit act1 or full_run goal')
        source = tuple(self.weights.items()) if type(self.weights) is dict else self.weights
        if type(source) is not tuple:
            raise RewardError('Weights must be a dictionary or immutable pairs')
        defaults = (POTENTIAL_WEIGHTS if self.schema == POTENTIAL_SCHEMA else
                    DEFAULT_WEIGHTS if self.schema == SCHEMA else
                    ACT_RUN_WEIGHTS if self.schema == ACT_RUN_SCHEMA else
                    SHAPED_RUN_WEIGHTS if self.schema == SHAPED_RUN_SCHEMA else RUN_WEIGHTS)
        resolved, seen = dict(defaults), set()
        for pair in source:
            if type(pair) is not tuple or len(pair) != 2:
                raise RewardError('Invalid reward weight entry')
            name, value = pair
            if type(name) is not str or name not in resolved or name in seen:
                raise RewardError('Unknown or duplicate reward component')
            seen.add(name)
            resolved[name] = finite(value)
        if self.schema == RUN_SCHEMA and resolved != dict(RUN_WEIGHTS):
            raise RewardError('Full-run v1 requires unshaped canonical run victory utility')
        object.__setattr__(self, 'weights', tuple((name, resolved[name]) for name, _ in defaults))

    @classmethod
    def full_run(cls):
        return cls(RUN_WEIGHTS, RUN_SCHEMA)

    @classmethod
    def potential_combat(cls, weights=(), *, discount=1.0):
        """Public health potentials; terminal potential is zero, cutoffs retain it."""
        return cls(weights, POTENTIAL_SCHEMA, discount=discount)

    @classmethod
    def shaped_full_run(cls, weights=()):
        """Explicit configurable training objective; evaluation still uses wins."""
        return cls(weights, SHAPED_RUN_SCHEMA)

    @classmethod
    def with_act_rewards(cls, weights=(), *, goal='full_run'):
        """Versioned act bonuses and a value horizon bound to the objective."""
        return cls(weights, ACT_RUN_SCHEMA, goal)

    @property
    def episode_goal(self):
        return self.goal or self.task

    @property
    def task(self):
        return 'combat' if self.schema in (SCHEMA, POTENTIAL_SCHEMA) else 'full_run'

    @property
    def components(self):
        # Zero combat weights in the run preset are declarations, not invented
        # measurements of fights. Run trajectories measure only their utility.
        return (POTENTIAL_COMPONENTS if self.schema == POTENTIAL_SCHEMA else
                COMPONENTS if self.task == 'combat' else
                ACT_RUN_COMPONENTS if self.schema == ACT_RUN_SCHEMA else
                SHAPED_RUN_COMPONENTS if self.schema == SHAPED_RUN_SCHEMA else ('run_victory',))

    def to_dict(self):
        return {'schema': self.schema, 'weights': dict(self.weights),
                **({'discount': self.discount} if self.schema == POTENTIAL_SCHEMA else {}),
                **({'goal': self.goal} if self.schema == ACT_RUN_SCHEMA else {})}

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != ({'schema', 'weights', 'goal'}
                if value.get('schema') == ACT_RUN_SCHEMA else {'schema', 'weights', 'discount'}
                if value.get('schema') == POTENTIAL_SCHEMA else {'schema', 'weights'}) or type(value['weights']) is not dict:
            raise RewardError('Expected reward schema and weights')
        return cls(value['weights'], value['schema'], value.get('goal'), value.get('discount'))

    @classmethod
    def loads(cls, text):
        return cls.from_dict(strict_json(text))

    @property
    def identity(self):
        data = json.dumps(self.to_dict(), sort_keys=True, separators=(',', ':'), allow_nan=False)
        return self.schema + ':' + hashlib.sha256(data.encode()).hexdigest()

    def evaluate(self, components):
        # Validate every measurement, even if its objective weight is zero.
        kind = (PotentialRewardComponents if self.schema == POTENTIAL_SCHEMA else
                RewardComponents if self.task == 'combat' else
                ActRunRewardComponents if self.schema == ACT_RUN_SCHEMA else
                ShapedRunRewardComponents if self.schema == SHAPED_RUN_SCHEMA else RunRewardComponents)
        components = kind.from_dict(components) if type(components) is dict else components
        if type(components) is not kind:
            raise RewardError('Expected measured reward components')
        values = asdict(components)
        try:
            return finite(math.fsum(weight * values[name] for name, weight in self.weights if weight))
        except (ValueError, OverflowError) as error:
            raise RewardError('Non-finite weighted reward') from error


@dataclass(frozen=True, slots=True)
class RewardComponents:
    combat_win: int
    combat_loss: int
    win_hp_fraction: float
    end_turn_action: int
    potion_use_action: int

    def __post_init__(self):
        for value in (self.combat_win, self.combat_loss, self.end_turn_action, self.potion_use_action):
            if type(value) is not int or value not in (0, 1):
                raise RewardError('Event components must be measured zero/one integers')
        fraction = finite(self.win_hp_fraction)
        if not 0 <= fraction <= 1 or not self.combat_win and fraction != 0:
            raise RewardError('Invalid victory HP fraction')
        if self.combat_win + self.combat_loss > 1 or self.end_turn_action + self.potion_use_action > 1:
            raise RewardError('Incompatible reward measurements')
        object.__setattr__(self, 'win_hp_fraction', fraction)

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != set(COMPONENTS):
            raise RewardError('Missing or unknown reward measurement')
        return cls(**value)


@dataclass(frozen=True, slots=True)
class PotentialRewardComponents(RewardComponents):
    enemy_hp_potential: float
    player_hp_potential: float

    def __post_init__(self):
        RewardComponents.__post_init__(self)
        for name in ('enemy_hp_potential', 'player_hp_potential'):
            value = finite(getattr(self, name))
            if not -1 <= value <= 1:
                raise RewardError('Invalid normalized health potential difference')
            object.__setattr__(self, name, value)

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != set(POTENTIAL_COMPONENTS):
            raise RewardError('Missing or unknown potential reward measurement')
        return cls(**value)


@dataclass(frozen=True, slots=True)
class RunRewardComponents:
    run_victory: int

    def __post_init__(self):
        if type(self.run_victory) is not int or self.run_victory not in (0, 1):
            raise RewardError('Run victory must be a measured zero/one integer')

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != {'run_victory'}:
            raise RewardError('Expected only the measured run victory component')
        return cls(**value)


@dataclass(frozen=True, slots=True)
class ShapedRunRewardComponents:
    combat_win: int
    combat_loss: int
    win_hp_fraction: float
    end_turn_action: int
    potion_use_action: int
    run_victory: int
    run_defeat: int
    run_abandoned: int

    def __post_init__(self):
        combat = RewardComponents(*(getattr(self, key) for key in COMPONENTS))
        object.__setattr__(self, 'win_hp_fraction', combat.win_hp_fraction)
        endings = (self.run_victory, self.run_defeat, self.run_abandoned)
        if any(type(v) is not int or v not in (0, 1) for v in endings) or sum(endings) > 1:
            raise RewardError('Invalid mutually exclusive run ending measurements')
        if self.combat_loss and not self.run_defeat:
            raise RewardError('A combat defeat must also end the run in defeat')

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != set(SHAPED_RUN_COMPONENTS):
            raise RewardError('Missing or unknown full-run reward measurement')
        return cls(**value)


@dataclass(frozen=True, slots=True)
class ActRunRewardComponents(ShapedRunRewardComponents):
    act_cleared: int

    def __post_init__(self):
        ShapedRunRewardComponents.__post_init__(self)
        if type(self.act_cleared) is not int or self.act_cleared not in (0, 1):
            raise RewardError('Act clear must be a measured zero/one integer')
        if self.act_cleared and (self.run_victory or self.run_defeat or self.run_abandoned):
            raise RewardError('Act completion precedes the campaign ending')

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != set(ACT_RUN_COMPONENTS):
            raise RewardError('Missing or unknown act reward measurement')
        return cls(**value)


def measure_run(successor):
    if type(successor) not in (f.PublicDecision, c.RunOutcome):
        raise RewardError('Expected a public run successor')
    return RunRewardComponents(int(type(successor) is c.RunOutcome and successor.kind == 'victory'))


def public_summary(value):
    """Strict allowlist for the controller's public HUD/result measurement."""
    if type(value) is dict:
        if set(value) != set(CombatSummary.__dataclass_fields__):
            raise RewardError('Missing or unknown combat summary field')
        value = CombatSummary(**value)
    if type(value) is not CombatSummary or value.schema != 'sts_combat_summary_v1':
        raise RewardError('Unsupported combat summary')
    if (type(value.combat_ref) is not str or re.fullmatch(r'combat:[0-9]+', value.combat_ref) is None
            or value.outcome not in ('ongoing', 'victory', 'defeat')
            or any(type(v) is not int for v in (value.hp, value.max_hp, value.turn))
            or not 0 <= value.hp <= value.max_hp or value.max_hp <= 0 or value.turn < 1):
        raise RewardError('Invalid combat summary')
    if value.outcome == 'defeat' and value.hp != 0:
        raise RewardError('Defeat requires the final zero-HP HUD')
    return value


def measure(action, execution, before, after):
    """Measure exactly one reconciled action, without an engine or any RNG.

    The owner supplies post-hook summaries. Rejections/uncertain actions are not
    transitions; reset and external cutoffs without an action have no reward.
    """
    before, after = public_summary(before), public_summary(after)
    if (before.completed or before.combat_ref != after.combat_ref or after.turn < before.turn
            or type(action) is not f.Candidate or action.kind not in f.ACTIONS
            or type(execution) is not c.ExecutionReport or execution.status != 'reconciled'
            or execution.reason != 'none' or execution.mutation not in ('none', 'applied')):
        raise RewardError('Expected one reconciled transition in the same ongoing fight')
    won, lost = int(after.outcome == 'victory'), int(after.outcome == 'defeat')
    return RewardComponents(won, lost, after.hp / after.max_hp if won else 0.0,
                            int(action.kind == 'end_turn'), int(action.kind == 'use_potion'))


def health_potentials(public):
    """Version-1 public potentials: (-enemy health fraction, player health fraction).

    Include every visible enemy slot, including dead ones, in the denominator.
    A non-combat context or incomplete HUD has potential (0, 0); this is an
    explicit neutral potential, not an assertion that an unknown enemy is dead.
    Only the confirmed combat boundary decides terminal potential in measure_combat.
    """
    if type(public) is not f.PublicDecision or public.context.kind != 'combat':
        return 0.0, 0.0
    hp, maximum = public.run.get('hp'), public.run.get('max_hp')
    groups = [n for n in public.context.children if n.kind == 'enemies']
    if (type(hp) is not int or type(maximum) is not int or not 0 <= hp <= maximum or maximum <= 0
            or len(groups) != 1 or not groups[0].children):
        return 0.0, 0.0
    enemy_hp = enemy_max = 0
    for enemy in groups[0].children:
        current, top = enemy.get('hp'), enemy.get('max_hp')
        if (enemy.kind != 'enemy' or type(current) is not int or type(top) is not int
                or not 0 <= current <= top or top <= 0):
            return 0.0, 0.0
        enemy_hp += current
        enemy_max += top
    return -enemy_hp / enemy_max, hp / maximum


def measure_combat(spec, action, execution, before, after, observation, successor):
    """Measure a real combat edge, including optional discounted public shaping."""
    base = measure(action, execution, before, after)
    if spec.schema != POTENTIAL_SCHEMA:
        return base
    before, after = public_summary(before), public_summary(after)
    if type(observation) is not f.PublicDecision:
        raise RewardError('Potential shaping requires the public pre-action decision')
    if not after.completed and type(successor) is not f.PublicDecision:
        raise RewardError('A combat cutoff must retain its public successor potential')
    previous = health_potentials(observation)
    following = (0.0, 0.0) if after.completed else health_potentials(successor)
    changes = tuple(spec.discount * new - old for old, new in zip(previous, following))
    return PotentialRewardComponents(**asdict(base), enemy_hp_potential=changes[0], player_hp_potential=changes[1])


def measure_full_run(action, execution, successor, before_combat, after_combat):
    """Public facts for one accepted run action; no private engine or RNG input.

    Summaries are captured by the owner before/after dispatch, including cleanup
    healing and fights that finish during room entry. A retained completed owner
    never pays twice. Cutoffs without an action must not call this function.
    """
    if (type(action) is not f.Candidate or action.kind not in f.ACTIONS or
            type(execution) is not c.ExecutionReport or execution.status != 'reconciled' or
            execution.reason != 'none' or execution.mutation not in ('none', 'applied') or
            type(successor) not in (f.PublicDecision, c.RunOutcome)):
        raise RewardError('Expected one reconciled public full-run transition')
    before = None if before_combat is None else public_summary(before_combat)
    after = None if after_combat is None else public_summary(after_combat)
    won = lost = 0
    hp_fraction = 0.0
    if before is not None and not before.completed:
        if after is None:
            raise RewardError('Ongoing fight lost its result measurement')
        combat = measure(action, execution, before, after)
        won, lost, hp_fraction = combat.combat_win, combat.combat_loss, combat.win_hp_fraction
    elif after is not None:
        if before is not None and before.combat_ref == after.combat_ref:
            if after != before:
                raise RewardError('A completed fight cannot change or resume')
        elif after.completed:
            won, lost = int(after.outcome == 'victory'), int(after.outcome == 'defeat')
            hp_fraction = after.hp/after.max_hp if won else 0.0
    kind = successor.kind if type(successor) is c.RunOutcome else None
    return ShapedRunRewardComponents(won, lost, hp_fraction,
        int(action.kind == 'end_turn'), int(action.kind == 'use_potion'),
        int(kind == 'victory'), int(kind == 'defeat'), int(kind == 'abandoned'))


def measure_act_run(action, execution, successor, before_combat, after_combat, before_act):
    """Pay only an accepted edge into a new public act-completion decision."""
    if before_act is not None and (type(before_act) is not int or before_act not in (1, 2, 3)):
        raise RewardError('Invalid previous public act completion')
    base = measure_full_run(action, execution, successor, before_combat, after_combat)
    after_act = completed_act(successor)
    if before_act is not None and after_act is not None and after_act != before_act:
        raise RewardError('One action cannot clear two different acts')
    return ActRunRewardComponents(**asdict(base),
        act_cleared=int(after_act is not None and after_act != before_act))
