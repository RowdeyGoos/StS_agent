# Public encoding and Gymnasium environment

Milestone 4 adds [`PublicEncoder`](../game/agent/encoding/codec.py) and
[`StsEnv`](../game/agent/gym_env.py) over the existing
[public contract and headless adapter](AGENT_CONTRACT.md). Neither implements game
rules. Install the optional dependencies with `python -m pip install -e '.[gym]'`.
The engine, public contract, adapter and `sts-headless-play` remain standard-library
consumers; importing them does not import NumPy, Gymnasium or Torch.
Milestone 5 adds the opt-in [full-run profile and environment](#full-run-profile-and-environment)
while preserving the original slice and live contract.
Milestone 6's [public trajectories and training loader](AGENT_EXECUTION.md)
consume this encoding without changing its spaces, semantics or capacities.

## Fixed spaces and public semantics

The format is `sts_public_graph_v1`. Its default padded profile has **256 action
slots**. An action is an integer indexing the current candidate table, so a slot's
meaning comes from its operation and public entity arguments in that observation.
`action_mask[i] == 1` identifies an advertised legal candidate. All candidates
survive encoding; masked padding is never converted to a game action.

The observation is a Gymnasium `Dict` of integer arrays. It represents the complete
public run/context as a typed tree, with separate entity-reference, exact content
text and candidate tables. It is not a private snapshot or a flattened JSON byte
string. The fixed field, node-type, action and reference-namespace vocabularies
are declared in [`schema.py`](../game/agent/encoding/schema.py).

| Array | Default shape | Meaning |
| --- | --- | --- |
| `layout` | `(6,)` | Format version and the five capacity dimensions |
| `nodes` | `(16384, 5)` | Parent node index, field ID, sibling position, value type, payload |
| `node_mask` | `(16384,)` | Present tree nodes |
| `references` | `(512, 2)` | Public namespace and defining node index; zero definition means a historical reference without a current descriptor |
| `reference_mask` | `(512,)` | Present references |
| `strings` | `(512, 96)` | Exact UTF-8 content names, labels and enum values, padded with zeros |
| `string_lengths`, `string_mask` | `(512,)` each | Byte lengths and present strings |
| `candidates` | `(256, 3)` | Operation ID, subject reference index, target reference index |
| `action_mask` | `(256,)` | Present legal candidates |
| `outcome` | `(2,)` | Backend outcome/reason codes; zeros for a public decision |

Table links are one-based, with zero reserved for no link/padding. Sibling positions
are zero-based and preserve visible order. Masks are `int8`, text bytes are `uint8`
and all other arrays are `int64`. Public integer magnitudes above `2**31 - 1` raise
`CapacityError`; values are never converted through float32. The default arrays
occupy 740,672 bytes per observation, before Python overhead.

Known zero, known empty, known absent, not-applicable and optional unknown origin
links remain distinct through their public `Observed.status/value` fields. Padding
masks do not replace those availability semantics. Missing required public fields
still raise `UnsupportedDecision` before encoding.

Raw reference ordinals, candidate reference names and input candidate order are excluded from
features. References receive local table indexes in public traversal order;
candidates sort by operation and those indexed arguments. Renaming all references
or permuting candidates therefore leaves the tensors unchanged. Duplicate cards,
offers and powers keep distinct references, with every origin, target, selection
and history link preserved. Meaningful list order, including hand, selection and
orb order, remains intact. Reference indexes are local to an observation.

`encode(decision)` returns `EncodedDecision`. Only its `observation` goes to a
model. `candidate_refs` maps each action slot back to the original public candidate
for exact adapter dispatch; `reference_refs` records the corresponding public
names for inspection. These are control-side correspondence, not extra features.
`decode(observation)` reconstructs the entire public contract with canonical local
reference names and candidate order. Losslessness means equality of public values,
ordering, distinct entities and links modulo that deliberate renaming/reordering.
No original decision is cached inside the decoder. It validates links, masks,
padding, types, versions and canonical re-encoding.

`collate(observations)` validates and stacks a nonempty batch without changing any
candidate or mask. Different capacity profiles cannot share a batch. Custom
`EncodingProfile` capacities change the layout identity and spaces; record that
identity alongside a model. Learned feature extraction and checkpoints are now
implemented for the full-run v2 profile in the [training guide](AGENT_TRAINING.md).

## Capacity evidence and limits

The profile is explicitly finite. A reachable 128-card engine deck plus its 128
combat copies uses 7,316 nodes in the initial prototype. The default was then tested
against these larger combined cases:

| Case | Nodes | References | Candidates | Evidence |
| --- | --- | --- | --- | --- |
| 128-card deck, ten hand cards, eight targets, 256 history events | 9,752 | 266 | 81 | Authored target/history stress over a real headless decision |
| Neow's Fury selector with 127 eligible discard cards | 7,468 | 259 | 128 | Headless play opens the real selector; two selections and confirmation remain representable |
| Eight reward entries with 32 duplicate-definition cards in one open offer | Within profile | Distinct offered cards | 33 | Authored public-contract stress, beyond current live offer bounds |

These cases establish capacity for the stated inputs, not a universal deck, history
or full-run bound. Overflow reports its dimension, required amount and capacity.
It never clips a collection, drops a candidate or reports defeat. The structured
adapter remains usable with a larger profile or a future ragged consumer. Content
names use exact bytes instead of per-card encoder registrations or collision-prone
hashing; their byte length and table count are also bounded explicitly.

## Gymnasium lifecycle and outcomes

The default `StsEnv` starts an authored Ironclad combat on a two-combat map with
Neow's Fury, two Strikes, Defend and a supported reward-card pool. It stops at the
first actionable map. This exercises the current producer's declared slice, not a
generated full campaign. Pass `engine_factory(seed)` to provide a fresh exclusively
owned engine; unsupported legal families/content still raise `UnsupportedProfile`.

```python
from game.agent.gym_env import StsEnv
from game.agent.policy import choose_action

with StsEnv() as env:
    observation, info = env.reset(seed=2)
    while True:
        decision = env.encoder.decode(observation)
        candidate = choose_action(decision)
        action = decision.candidates.index(candidate)
        observation, reward, terminated, truncated, info = env.step(action)
        if terminated or truncated:
            break
```

For random legal actions, seed `env.action_space` independently, then use
`env.action_space.sample(mask=observation['action_mask'])`. A caller-owned policy RNG
is independent too. `reset(seed=...)` seeds Gymnasium's episode-seed generator,
which seeds a fresh engine; game execution and action sampling use separate RNG
objects. Repeated explicit seeds reproduce semantic traces; `reset()` continues the
episode-seed generator. Seeds, snapshots, RNG and dispatch bindings never appear
in observations, `info` or ANSI rendering.

Constructor settings are `max_decisions=256`, `time_limit_seconds=None` and
`stop_at_map=True`. `reset(options=...)` may override these three settings for one
episode; the next reset returns to constructor defaults. Decision budgets count
reconciled actions. Time budgets use a monotonic clock, checked before dispatch
and after the synchronous action finishes; they do not interrupt a running command.

| Result | Reward | Flags and behavior |
| --- | --- | --- |
| Full-game victory | `1.0` | `terminated=True` |
| Actual defeat or abandonment | `0.0` | `terminated=True`, explicit outcome |
| Ordinary transition or combat victory | `0.0` | Episode continues |
| Environment decision/time/map cutoff | `0.0` | `truncated=True`; final coherent public decision and legal mask are retained for bootstrapping, with the outcome in `info` |
| Backend authored slice/act endpoint | `0.0` | `truncated=True`; the adapter currently supplies an outcome-only observation |
| Invalid/padded index or stale binding | `0.0` | Both flags false; unchanged cached public decision and explicit non-mutating rejection |
| Unsupported/capacity/fault/uncertain execution | No transition returned | Typed failure; reset required |

Use undiscounted episodic return for the full-run victory objective; there is no HP
or combat-win shaping. True backend outcomes take precedence over simultaneous
environment cutoffs. Outcome-only observations have no fabricated state or legal
actions. At environment cutoffs the retained mask describes the final state, but
the episode is closed and `step` requires a reset. A factory already at an endpoint
returns that outcome in reset `info` and likewise requires another reset before a step.

The Gym API follows the [environment lifecycle](https://gymnasium.farama.org/api/env/).
Plain unmasked sampling may choose padding: the environment reports rejection,
does not spend a game decision and does not substitute a strategic action. Use
masks in rollouts; an optional wall-clock budget can bound repeated invalid calls.
Python integers, NumPy integer scalars and zero-dimensional integer arrays are
accepted. Bools, floats and nonscalar arrays are rejected.

`info` contains only the encoding identity, validated public execution report and
public outcome. Backend failures and interrupts stop further dispatch, including
interrupts after mutation; commands are never retried automatically. Invalid/stale
rejections preserve the cached decision. A stale exclusive-owner violation needs a
new reset rather than an implicit refresh. `close()` is idempotent and releases the
owned engine/frame; reset may start a fresh episode afterward.

## Full-run profile and environment

[`FullRunEnv`](../game/agent/gym_env.py) uses the
[`full_run_v2` decision contract](AGENT_CONTRACT.md#full-run-v2-profile),
[`FullRunEncoder`](../game/agent/encoding/full.py) and the same guarded lifecycle.
It starts an ordinary-HP generated campaign, including Neow, and continues through
the Architect or actual defeat. All five characters, Overgrowth/Underdocks and
A0–A10 are configurable. The default budget is 4,096 reconciled decisions; there
is no map cutoff. The public-only demonstration chooser is deliberately simple.

```python
from game.agent.gym_env import FullRunEnv
from game.agent.full_policy import choose_action

with FullRunEnv(character="defect", first_act="underdocks", ascension=10) as env:
    observation, info = env.reset(seed=2)
    while info["outcome"] is None:
        decision = env.encoder.decode(observation)
        action = decision.candidates.index(choose_action(decision))
        observation, reward, terminated, truncated, info = env.step(action)
        if terminated or truncated:
            break
```

The format is `sts_public_graph_v2`. The array meanings, exact UTF-8 vocabulary,
reference normalization, candidate sorting, masks and strict decoder are shared
with v1. V2's field/action vocabulary and layout version are separate; a v1 encoder
cannot consume a v2 profile. Its finite default `FullRunProfile` has:

| Dimension | Capacity |
| --- | --- |
| Tree nodes | 131,072 |
| Public references | 16,384 |
| Distinct strings | 4,096 |
| Bytes per string | 256 |
| Candidate/action slots | 2,048 |

Each padded observation occupies 6,789,184 bytes before Python overhead. One
reachable 128-card deck plus its 128 combat copies uses 27,186 nodes, 257 refs,
88 strings and 6 candidates. Rare-event/pickup/potion tests and the campaign
matrix exercise the same profile. These are explicit capacity cases, not a proof
that arbitrarily growing decks or indefinite history always fit. Every overflow
still raises `CapacityError`, with no clipping or fabricated game outcome.
Larger `FullRunProfile` capacities can be supplied explicitly; changing them
changes the layout identity and prevents mixed-profile collation.

`FullRunEncoder.pack(public_decision)` uses the same traversal, exact typed
values, reference normalization, candidate mapping and capacity checks, but
allocates only populated table rows. The original `encode()` pads those shared
tables to the unchanged Gym layout. This is an in-memory learner path, not a new
recording format; it never clips oversized states. The
[learned feature encoder](AGENT_TRAINING.md#milestone-3-usage-and-implementation-choices)
keeps these exact packed tables alongside explicitly lossy neural scalar features
and a frozen training vocabulary. Raw reference ordinals and per-frame string
indexes are not model features.

Use `full_policy.choose_action` with v2 and `policy.choose_action` with v1.
`HeadlessAdapter(..., decision_profile="full_run_v2")` remains usable without
NumPy/Gymnasium. `FullRunEnv(engine_factory=...)` accepts the same positional-seed
factory contract as `StsEnv`; callers retain responsibility for a fresh exclusively
owned engine. Reward, rejection, cutoff, error, independent RNG and close behavior
are unchanged. Opening/closing a reward child is a counted presentation decision
but does not advance engine state or RNG.

The separate [CombatTrainingEnv consumer](AGENT_TRAINING.md#milestone-1-usage-and-implementation-choices)
reuses this profile for one owned fight and supplies combat-task termination and
a configurable [training reward](AGENT_TRAINING.md#milestone-2-usage-and-record-semantics),
defaulting to +1 for combat victory. It keeps the canonical run outcome separate. All
three environments expose `public_state`, the immutable structured decision
behind their encoding; external cutoffs retain that final decision for bootstrapping.

## Validation

[`test_encoding.py`](../tests/agent/test_encoding.py) checks all five resource
shapes, lossless fields/links, reference renaming, candidate permutation, hidden-state
invariance, duplicate offers, large selectors, every capacity dimension, numeric
precision, malformed tensors, outcomes and batch collation.
[`test_gym_env.py`](../tests/agent/test_gym_env.py) checks the
[Gymnasium environment checker](https://gymnasium.farama.org/api/utils/), masked
rollouts, exact duplicate selection, invalid/stale actions, real combat victory and
defeat, synthetic full-run outcome mapping, cutoffs, mutation-then-interrupt,
operational failures, two-environment/RNG independence, options and safe close.
Checker sampling of padded slots exercises the documented rejection behavior;
the checker also reports its advisory about constant layout metadata bounds.

For milestone 4 on 2026-09-23, the aggregate agent/package suite passed **177 tests in 5.50 seconds**
using Gymnasium 1.0.0 and NumPy 2.4.6; `compileall game tests` passed. Independent
semantic review and correction recheck took **5m56s** and left no concrete blocker.
The wheel was built and its core installed without optional dependencies for CLI
and adapter checks. With the tested optional dependencies, the installed wheel
also completed the documented 17-action slice rollout with reward zero. Final
wheel SHA-256 is `48b6b4ede060167441d5e7b669dbf51ce5a8201b8d5115fe584ad90a88fa9df7`;
the build/install command took 0.844 seconds. Implementation time was not separately
measured. These are headless/packaging results. The accepted milestone 3
bridge sources and manifest remained unchanged; milestone 4 added no live or
full-campaign coverage. Its wheel identity is historical, preceding v2.

Milestone 5's fixtures census all 40 engine command classes, 65 event definitions,
63 potion definitions and 1,075 card-level previews. They cover exact dispatch,
modal rewards, repeated offers, removal/rest cancellation, selectors, acquired
identity, public counters, hidden draw/future-page invariance, infinite HP and
reviving enemies. The campaign matrix uses all five characters, both Act 1 regions
and A0/A10 with ordinary HP. Controlled A0 Overgrowth and A10 Underdocks routes
separately establish all act transitions, the A10 second boss, Architect victory
and Gym's sparse terminal reward. Controlled enemy defeats and boosted fixture
HP are not policy-win evidence.

Independent semantic review ran 20:33:47–21:05:54 UTC (about 32 minutes including
correction waits), found public-information/identity issues that were corrected,
and ended with no concrete blocker. A later identity regression prompted a bounded
correction/recheck at 21:19:46–21:25:33 UTC (5m47s), also ending without a blocker.
The corrected focused agent/package checks passed **346 tests in 50.74 seconds**.
The broader agent/package run passed **365 tests in 538.63 seconds**, including
the full Gym campaign matrix; the focused correction suite additionally covers
the last identity fixes and four regressions added after that run began.
The 20 ordinary-HP campaign cases all ended in genuine defeat (84–317 decisions,
2,838 total); this is execution coverage, not a success-rate result for a trained
policy. The Gym checker and controlled endpoints passed alongside that matrix.

The repository-wide run completed in **1,773.68 seconds** with **8,043 passing
tests** and one sandbox-only failure: the existing ephemeral socket test could
not bind `127.0.0.1:0`. That exact test passed separately with the required socket
permission (**1 passed in 0.01 seconds**). The broad run began before the final
identity corrections; the final 346-test focused run covers those changes and
their added regressions. Both Gym checker advisories concern constant layout
metadata bounds. Final compilation and diff checks passed.

The final Python wheel SHA-256 is
`41c889d4463512457492e28e2b38b69f2c43caa962c448e3dc8f6ae6910537ca`.
Its build/install steps took 0.44/0.27 seconds. The installed package passed a
full-profile event identity check with optional dependencies disabled and a
20-decision Defect/A10 Gym rollout ending in an explicit budget cutoff. All
393 bridge source inputs and their inventory digest still match the accepted
milestone 3 manifest, so no native rebuild/install or additional live acceptance
is claimed. Implementation and test runs overlapped; their elapsed times are not
additive, and implementation time was not separately measured. No live setup or
user wait was required.
