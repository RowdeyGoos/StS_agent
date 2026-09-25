# Shared agent interface and Gymnasium implementation plan

Created 2026-09-22 against main at `14182eb`. Status: **milestones 1–6 complete;
milestone 7 accepted 2026-09-24 under the assisted campaign scope below**.
This document owns the execution plan for the shared agent
interface. [HF-44–47](HEADLESS_FULL_GAME_IMPLEMENTATION.md#open-assignments) own
the full-game consumer assignments; [status](STATUS.md) owns bridge capability
and evidence. The [public contracts](AGENT_CONTRACT.md) own implemented semantics;
milestone 3's [accepted live slice](evidence/AGENT_BRIDGE_M3_2026_09_23.md) is recorded
separately from authored fixture evidence.

## Outcome and delivery boundary

Build a public decision contract that lets the same policy choose actions in the
headless engine and the live game. Deliver a Gymnasium environment over the
headless adapter, with shared encoding, explicit run outcomes and reproducible
public trajectories. Keep game execution in `game/headless/` and native execution
in the existing production bridge.

The first integrated acceptance case is an Ironclad combat containing Neow's Fury
and its nested card selection, followed by combat rewards and an actionable map.
Use a controlled setup with eligible discard cards; compare optional-zero and
positive selection in focused cases. In addition to the earlier
[representative bridge evidence](COMBAT_CHOICES.md), the new adapter now has its
own [controlled live acceptance](evidence/AGENT_BRIDGE_M3_2026_09_23.md). Its headless
decision mismatch is now corrected with
[focused native evidence](evidence/neows_fury_2026_09_22.md).
Map-node dispatch passed as a separate bounded case because the ordinary composite
clients only verify the map.

The initial deliverable ends after milestones 1–6 below: a full-run headless Gym
environment for the engine's declared five-character/A0–A10 scope, and a live
adapter with explicitly tested coverage. It includes a simple public-only policy
and trajectory loading, without a training algorithm or policy-strength claim.
Live campaign traversal is the subsequent milestone 7, now accepted with upfront
assistance and one recorded bridge-fix reload. Its capability and evidence limits
remain visible.

## Architecture and ownership

Both backend adapters produce the same public decision types and consume a
selection from their advertised candidates. The policy and encoder depend only
on that contract. The headless runner provides reset/seed/step; the live runner
provides attachment, bounded dispatch, reconciliation and owned cleanup.

| Location | Planned responsibility |
| --- | --- |
| `game/agent/contracts/` (implemented) | Versioned structured public types, serialization, validation and shared conformance examples |
| `game/agent/headless/` (implemented) | Read-only v1 slice and v2 full-run projection, public identity mapping and exact command dispatch |
| `game/agent/encoding/` (implemented) | Versioned slice/full-run public vocabularies, candidate features, masks and collation |
| `game/agent/gym_env.py` (implemented) | Slice/full-run Gymnasium lifecycle, spaces, reward and cutoff handling |
| `game/agent/policy.py`, `full_policy.py`, `recording.py`, `dataset.py` (implemented) | Public-only reference choosers, public trajectories and split-checked training samples |
| `game/agent/runner.py`, `workers.py` (implemented) | Bounded owned headless execution, timing and spawn-worker cleanup |
| `game/cli/` and `pyproject.toml` | Installed agent-facing command and optional dependencies |
| `bridge/Sts2AgentBridge/src/` and `components/` | Richer native public observations and existing capability execution |
| `bridge/Sts2AgentBridge/apps/bridge/client/` | Live translation and policy integration through the existing client/controllers |
| `tests/agent/` (contract/adapter checks implemented), existing bridge fixture suites | Contract, privacy, adapter, Gym and cross-language checks |

The contract, producers, chooser, encoding, Gym environment and public recording
are implemented. Keep the contract and headless adapter
standard-library-only. Gymnasium/NumPy belong in an
optional extra; no Torch dependency is needed for this work. Preserve canonical
subpackage imports and `sts-headless-play`. Do not restore the retired simulator
APIs or make the retained `r0i_wire.py` codec the new full-game contract.

Use one owner through implementation, integration and release. Apply the
[working guide](../AGENTS.md#review-and-validation) for independent semantic
review when public-information, protocol or execution semantics change.

## Contract decisions to establish first

### Public state and identity

- Include character, ascension, act/floor, visible map context, HP/max HP, gold,
  deck instances/modifiers, relics/public counters, potion slots and resources.
  Combat adds powers, energy, public card costs/modifiers, piles, enemy entities
  and displayed intents with their visible numeric values. Represent Stars/Forge,
  Osty and ordered orbs explicitly.
- Project fields by an explicit public allowlist. Exclude seeds, RNG, hidden draw
  order, future encounters/rewards, unrevealed event assignments and native/private
  continuation data. A public map question mark must not disclose its resolved
  room. Public history contains only information actually observed or independently
  knowable under the [target](TARGET.md#scope-and-information).
- Distinguish known-empty, not-applicable and unknown/unavailable values. Define
  required fields for each supported decision profile. Missing required live
  information makes that profile unsupported; never manufacture zero values.
- Give publicly distinguishable entities public references. Preserve duplicate
  card identity and stable enemy identity through deaths/summons. Current native
  enemy indexes are compacted among living enemies, so index equality cannot be
  assumed across backends. Keep backend bindings outside model features.
- Preserve meaningful visible ordering; canonicalize collections whose internal
  order is hidden. Raw allocation IDs, opaque decision tokens, collection ordering
  and candidate ordering must not leak hidden state or private creation history.

### Decisions and execution

- A policy receives public state, decision kind, selection context and semantic
  legal candidates. Each candidate identifies its operation and public arguments;
  a separate control binding maps it to the exact engine command or native action.
  Catalog IDs use a shared vocabulary with explicit native-to-headless mappings.
- Model nested selections, select/deselect, confirm, skip and native cancel as
  distinct legal operations when the game offers them. Preserve count bounds,
  selected originals, target identity and automatic-versus-manual confirmation.
  Do not enumerate every possible card subset as a single flat action family.
- One policy step chooses one semantic action and stops at the next agent choice
  or actual game outcome. Automatic effects and transport/UI acknowledgments may
  be drained; another meaningful reward, event or selector choice goes back to the
  policy, including when it currently has only one candidate.
- Preserve differences between game legality and backend execution support.
  Advertise coverage separately and fail an incomplete requested profile
  explicitly. Silently removing a legal choice cannot establish adapter parity.
- Keep `ready`, `waiting`, completion, rejection, unsupported and uncertain/faulted
  execution distinct. Dispatch acceptance requires later reconciliation. Only a
  confirmed stale rejection with no mutation permits bounded re-observation;
  uncertain mutations stop the host and must never be retried.
- Version public semantics independently from encoding, trajectories and native
  wire routes. Validate negotiated versions before action dispatch. Extend or
  version affected existing bridge routes; keep one router, client and package.

## Milestones and acceptance

### 1. Define the first contract and verify both producers

**Completed:** 2026-09-22, with independent semantic review and focused/native
validation. Production bridge translation is delivered in milestone 3.

**Depends on:** current engine/bridge only. **Maps to:** HF-44.

Create the shared public types, candidate schema, outcome taxonomy and a small
set of valid/invalid examples. Inspect the first slice's actual engine commands,
native public fields and controller callbacks. Record a compact mapping beside
the contract: field/action, engine source, native source, visibility and support.
Cover all five character resource shapes without waiting for all live families.

**Delivered:** [public types, validation and producer mapping](AGENT_CONTRACT.md),
authored valid/invalid examples and all five resource shapes. The bounded HF-48
[Neow's Fury correction](evidence/neows_fury_2026_09_22.md) replaces random discard
returns with optional selection. Fourteen native OnPlay cases cover empty and
populated piles, zero/positive selection, upgrades, hand bounds and combat ending;
headless tests cover continuation, RNG and rejected forged snapshots. Existing
catalog fingerprints reject incompatible old continuations without a format bump.

Resolve the first uncertainties immediately: numeric intent visibility, power
stacks, card upgrades/modifiers, deck/pile visibility, stable entity references,
and access to each nested decision. Use existing native references or a focused
source inspection. Avoid designing the entire training stack before testing the
first producer/consumer agreement.

**Acceptance:** the Neow's Fury discrepancy is resolved with focused evidence;
first-slice decisions can be expressed without private snapshots;
every required field has a justified public source or a named bridge gap; unknown,
empty and absent states and malformed/version-mismatched inputs have clear behavior.

### 2. Implement the headless adapter and public-only chooser

**Depends on:** milestone 1. **Maps to:** HF-44 and the first HF-47 execution slice.

**Completed 2026-09-22:** [`HeadlessAdapter`](../game/agent/headless/adapter.py)
and the [public-only chooser](../game/agent/policy.py) execute the bounded
combat → Neow's Fury selection → rewards → map sequence, including subsequent
map dispatch. [Adapter tests](../tests/agent/test_headless_adapter.py) cover all
five starter resource shapes, off-character zero resources, duplicate cards and
offers, target identity, stale/illegal/reset/restore rejection, read-only
observation, hidden-state invariance and visible changes. Independent semantic
review covered public sources and command ownership. This is headless fixture
evidence; it adds no native/live conformance claim. See the
[producer boundary and named gaps](AGENT_CONTRACT.md#headless-producer).
No adapter checkpoint interface is exposed in this milestone.

Project directly from `RunEngine` and its owned state. Derive candidates from
`legal_actions()` and dispatch only through `run.apply()`, preserving run/combat
handoffs. Maintain public history and identity mapping in the adapter. Avoid
serializing a private snapshot and subtracting a blacklist of hidden fields.
If adapter continuation is exposed, store its public history/mappings alongside
the private engine checkpoint in a separate versioned checkpoint envelope, and
invalidate old dispatch bindings after reset/restore. Keep that envelope outside
policy inputs and the public trajectory format.

Implement a small chooser that receives only the public contract. The existing
`choose_demo_action(engine)` reads engine internals and therefore cannot serve as
the public-only acceptance policy unchanged. Use the same new chooser interface
for subsequent live integration.

**Acceptance:** the combat → nested selection → rewards → map slice runs through
the adapter. Focused fixtures cover all five character resources, duplicate cards,
target identity and illegal/stale selections. Repeated observations leave the
engine and RNG unchanged. Hidden-only state changes preserve the semantic public
view and candidate set; changed visible state remains distinguishable. Comparing
identity tokens uses normalized public references, not native hash equality.

### 3. Integrate the same policy with the bridge for the first slice

**Depends on:** milestones 1–2. **Maps to:** shared live integration for HF-44/47.

**Completed 2026-09-23, including controlled live acceptance and cleanup.** The
existing production router exposes `agent_v1` decisions/actions and its client runs the same
`game.agent.policy.choose_action` callback. The
[native producer boundary](AGENT_CONTRACT.md#native-producer) is explicit: supported
card previews and public powers/inventory only, no owned potions, and one bounded
combat/reward/map slice. Broader native content remains unsupported.

Five authored paired decisions cover Neow's Fury, two selections, confirmation
and the deterministic return to combat. Native-reader fixtures, Python host
fixtures, shared-client socket POST checks and independent semantic review cover
the projection and execution boundary. This is inert/fixture evidence, not a
live game result. Review also corrected off-table preview modifiers and Neow's
Fury deselect/reselect ordering; private continuation schemas are now combat v48
and run v69. The combined release passed all 78 check groups. The
[controlled native acceptance](evidence/AGENT_BRIDGE_M3_2026_09_23.md) then completed
combat, two-card selection, gold collection/reward leave and a separate map
transition: all 16 actions reconciled, followed by verified owned cleanup. The
same callback passed headless first; it uses the shared chooser for combat,
selection and map with a gold-then-leave reward override. Live card-offer selection
and broader content remain unverified. Live feedback also corrected premature
parent completion; a fresh native act map resolved a later setup-sensitive stall
without another package change.

Extend existing native readers with the required public fields, preserving owner
frame access and coherent observations. Join room/inventory and combat information
only when they belong to the same decision context; revalidate before dispatch.
Add the live contract translator inside the existing client.

Expose policy callbacks wherever a controller currently selects cards/rewards or
follow-up options mechanically. Preserve native session ownership, parent/child
bindings, deadlines, attempted/accepted/reconciled counts and cleanup. Normalize
precommitted versus interactive selections only where their decision timing and
available information agree; otherwise extend the existing capability or declare
that case unsupported.

Build a paired scenario harness using explicit matching public setups. Compare
normalized observations, candidates and selected deterministic transitions. RNG-
dependent outcome equality requires matched pinned RNG/state evidence; equivalent
observations alone do not imply the same hidden world or random result.

**Acceptance:** Python/C# and shared-client fixtures pass for the first slice,
including delayed completion, nested ownership, stale/no-mutation rejection,
uncertain dispatch and cleanup failure. One independent semantic review covers
the aggregate public/execution change. Gate and prepare the combined package for
this stable candidate, then run the
same public-only chooser through one controlled native slice and finish cleanup.
Record fixture and live results separately. Follow
[live development](LIVE_DEVELOPMENT.md#prepare-and-run-within-the-users-scope) for
current authorization and manual setup; this plan is not live-run authorization.

### 4. Add lossless encoding and the first Gymnasium environment

**Depends on:** milestone 2; milestone 3 feeds back contract corrections.
**Maps to:** HF-45 and the Gym portion of HF-47.

**Completed 2026-09-23:** the [versioned public encoding and Gym environment](AGENT_ENCODING.md)
provide fixed candidate-index actions, masks, lossless public fields/links, strict
capacity errors and independent seeded resets over the current supported slice.
The default episode ends at an actionable map with truncation and reward zero.
Environment cutoffs preserve the final public decision for bootstrapping; actual
full-run victory alone earns one. The aggregate agent/package suite passed 177
tests, including Gymnasium's checker, and independent semantic review completed.
The core wheel also installs without Gymnasium/NumPy. Broader decision coverage
and training-library integration are not implied by this first profile.

Encode public entities and candidate semantics separately, with reference indexes
and availability masks. Keep variable-length collections in the structured
contract. Provide a versioned padded training profile with fixed spaces and a
candidate-index action; derive its capacities from inspected reachable cases and
explicit supported bounds. Reject capacity overflow explicitly with its reason;
never clip cards/candidates or misreport overflow as game defeat. The full public
adapter remains usable outside any particular tensor-capacity profile.

Prototype capacity handling before publishing the encoding: exercise large decks,
many targets, repeated offers and multi-selection. If a finite profile cannot
cover a claimed scope, use a ragged representation/collator or narrow that profile
explicitly. Gymnasium has [composite and variable-length spaces](https://gymnasium.farama.org/api/spaces/composite/);
compatibility with a training library must be tested separately.

Implement `reset(seed=..., options=...)`, `step(action)` and `close()` following
the [Gymnasium API](https://gymnasium.farama.org/api/env/). Keep action sampling,
policy RNG and game RNG independent. Define these outcomes:

| Situation | Environment behavior |
| --- | --- |
| Full-game victory | `terminated=True`, reward `1` |
| Actual run defeat/abandonment | `terminated=True`, reward `0`, explicit outcome |
| Ordinary transition or combat victory within a run | Reward `0`; episode continues |
| External decision/time budget or authored slice/single-act endpoint | `truncated=True`, reward `0`, explicit reason; no full-game victory claim |
| Unsupported observation/capacity, backend fault or uncertain dispatch | Typed failure; no fabricated transition or game outcome |
| Invalid candidate or stale binding | Reject before game mutation; preserve the public decision and report the rejection |

For the full-run victory objective use undiscounted episodic return; reward
shaping and alternative objectives are later explicit choices. Never place
private seeds, snapshots, RNG or backend credentials in policy-visible Gym `info`.
Any invalid-action wrapper behavior must be documented and tested without changing
game legality or introducing implicit strategic choices.

**Acceptance:** reproducible resets and semantic traces, space membership,
candidate/mask round-trips, overflow handling, terminal/truncation/error cases,
safe close, and independence of two environments. Use Gymnasium's
[environment checker](https://gymnasium.farama.org/api/utils/) plus masked rollouts;
account explicitly for the checker's unmasked action sampling when validating a
restricted action profile. The direct game CLI runs without installing Gymnasium.

### 5. Extend the contract through full headless runs and supported live families

**Depends on:** milestones 2–4. **Maps to:** completion of HF-44/45 coverage.

**Implemented:** opt-in `full_run_v2` headless graph, exact command dispatch,
public-only chooser, lossless fixed encoding and `FullRunEnv`. The
[coverage census](AGENT_CONTRACT.md#command-and-pending-surface-coverage) separates
every engine command/pending family from legacy bridge capability and live
evidence. Normal-HP five-character/region/A0/A10 fixtures and controlled endings
are separate evidence. See [validation and limits](AGENT_ENCODING.md#validation).
The accepted live `agent_v1` contract/package is unchanged; v2 native projection,
potion control, rest cancellation and full-run orchestration are explicitly
outside that profile. Trajectories, the installed agent CLI and worker delivery
are implemented in milestone 6.

Extend each family through projection, candidates, encoding and dispatch together:

1. Potion use/discard, ordinary/extra rewards, reroll/sacrifice, relic pickups and
   their nested choices; treasure and actual map-node selection.
2. Rest options and selectors, purchases/removal/restocking and their children.
3. Event/Ancient pages, card offers/bundles, repeated and multi-card selections,
   custom minigames, event combat/resumption and abandonment confirmation.
4. Act transitions, A10 second boss and the Architect ending; all five characters'
   resource-specific decisions and modifiers.

Track every current game command and pending-decision shape in the contract's
coverage table. For each family record headless support, bridge observation and
action support, fixture evidence and live evidence separately. Wire the reference
chooser for every headless decision family. New gameplay content using an existing
mechanic must not need another per-card projection/encoder registration.

**Acceptance:** every legal command in the supported headless scope has an exact
candidate/dispatch mapping and lossless encoding within its declared profile.
Targeted scenarios cover rare decisions plus both Act 1 regions, representative
A0/A10 transitions and all characters. Bounded normal-HP public-policy rollouts
handle real defeat honestly; controlled endpoint fixtures establish victory
semantics without requiring a weak demonstration policy to win naturally.
Adapter coverage is complete only when all supported command/decision families
are covered, not merely when several sampled campaigns pass.

Live gaps such as Smith/Cook cancellation, potion-use control, missing observations
or preselected child choices must be resolved in the existing bridge or declared
outside its current profile. Inventory known live gaps from source and
[status](STATUS.md#implementation-gaps-versus-remaining-live-tests); do not infer
support solely from headless coverage or create speculative caller requirements.

### 6. Deliver trajectories, commands and the integrated package

**Depends on:** milestones 4–5. **Maps to:** HF-46/47 and relevant HF-49/50 delivery.

**Completed 2026-09-24:** versioned public JSONL trajectories, strict split/identity-aware
loaders, exact training-action mapping, installed `sts-agent-play`, private audit
separation, bounded spawn workers and cancellation-safe publication. See
[execution, format, timing and validation](AGENT_EXECUTION.md). The existing live
entry point already selects the shared policy with `--capability agent`; the
accepted bridge's transitive inputs are unchanged. The affected integration,
independent semantic review, clean core/Gym package checks and matched worker
rollouts passed; validation and timing are recorded in the execution guide.

Add a versioned public trajectory writer/loader containing decision observations,
all candidates, chosen actions, reconciled transitions and actual outcomes.
Keep build/rules/encoding/policy identity, scenario/split references and evidence
labels in artifact metadata. Store private replay seeds or snapshots in a
separately controlled audit path that policy loaders cannot read. Headless traces
provide the initial dataset; retained live corpora require
their own explicit scope under the live guide. Canceled writes remain visibly
incomplete and must not replace a valid finished artifact.

Add an installed `sts-agent-play` command over the existing engine factories and
new adapters; preserve `sts-headless-play` for direct gameplay. Extend the existing
live client entry point to select the shared policy. Start with one headless
worker, then verify a bounded two-worker run with independent state/seeds and
clean cancellation. Measure reset, observation/candidate creation, step and
complete rollout throughput before choosing later optimization work.

**Acceptance:** a multi-act public trajectory round-trips without losing actions,
observations or its terminal/cutoff reason; incompatible versions reject. A clean
Python 3.10+ installation works both without and with the optional Gym extra.
Document working commands, declared capacities and remaining live exclusions.
Run the final affected Python integration. Reuse the earlier bridge release gate
if its transitive inputs are unchanged; otherwise gate the new stable combined
candidate once. Verify package/source identity and owned installation/cleanup
when live work is authorized. Update usage, capability and evidence in their
owning guides.

### 7. Complete live campaign traversal

**Accepted by the user on 2026-09-24.** The existing bridge has a bounded
[traversal controller](../bridge/Sts2AgentBridge/README.md#campaign-traversal),
versioned act/ending handoffs, native chest Open/Skip and closed-shop leave.
The accepted Profile 3 Ironclad A0 campaign used the agreed upfront HP, damage
cards and two potions. The policy handled all gameplay without manual cards or
mid-run assistance. It used Fire twice, Strength and Vulnerable potions, including
collected rewards, then stopped at Waterfall Giant's nonnumeric HP display. One
normal save/reload installed the correction and restarted that fight from its
native checkpoint. The corrected controller completed all three bosses and the
ending: 643/643/643 actions across 82 stages in 672.271 seconds, with no further
intervention or controller replacement. Cleanup passed with zero overlays and
429 unchanged base files.

The user accepted this as sufficient campaign evidence and removed the need to
repeat a fresh run solely for an uninterrupted process. The original result
retains `continued_victory` and `full_campaign_verified: false`; acceptance does
not change the strict same-controller meaning of that field or the earlier
200/200/199 failure counts. The four potion uses keep their v5 release identity;
the v6 continuation commanded no potions. The
[M7 record](evidence/AGENT_CAMPAIGN_M7_2026_09_24.md#milestone-acceptance)
retains the acceptance decision, original artifacts, assistance and cleanup.
Earlier campaigns with manual fight assistance remain separate historical evidence.

This traversal policy composes existing native controllers; it does not extend
the shared v1 projection to the full headless v2 profile or certify strategic
quality. It is subsequent scope to the completed shared-interface/headless Gym
delivery. Preserve native ownership, task reconciliation and persistent budgets
when addressing actual remaining failures, including intermittent cold-start reads.

Establish supported run entry/reset separately; the current live adapter attaches
to a prepared run and cannot promise headless-style seeded reset. A strict fresh,
single-controller result remains distinct from this accepted assisted campaign.
Training algorithms, search and strategic win-rate evaluation then have their own
benchmarks under [TARGET](TARGET.md).

## Execution order and validation discipline

### Full shared live interface follow-through — in progress

The user requested the remaining shared interface and bridge gaps on 2026-09-24,
after milestone 7 acceptance. Baseline work is committed as `1093aca`, `222dcb8`
and `dbd7861`. The full headless profile is complete; the native campaign controller
still uses its own choices and is not yet a producer of `full_run_v2`.

The first bridge corrections, committed in `4a03c3c`, extend terminal rewards to
32 entries under schema 9, add exact Fake Mango pickup under schema 10, and
implement native selectorless removal continuation. Focused native/router
and shared-client tests passed, including all 65 actions for 32 card rewards.
The original ten-entry merchant rewards passed live after native Continue;
automatic removal passed after the outer-request correction (`b7ee84b`): two
parent actions reconciled, no child selection, and an actionable map. Owned cleanup
passed with zero overlays and 429 unchanged base files. Representative live checks
remain distinct from fixture evidence.

The remaining implementation must provide full public native observations and
semantic candidates across combat, potions, rewards, maps, shops, rests, events,
Ancients and the ending; expose nested selections to the same policy callback;
and retain exact parent/child ownership, version negotiation, reconciliation and
public-only recording. Native Smith/Cook cancellation and Dream Catcher/Tiny
Mailbox reward continuation now have an interactive room-module implementation
and offline checks. Each native child is separately exposed to its callback.
Representative live checks passed on 2026-09-25: immediate/preview cancellation
for both options, combined card/potion collection, and separate card Skip/parent
dismissal, with 20/20/20 actions and complete owned cleanup. The controlled rest
client is not yet connected to the full shared policy. The Dig pool audit found no
normal-game pickup-screen caller among its Common/Uncommon/Rare relics; broader
injected pickup screens remain a contract limit.
These changes belong in the existing native modules, router and client. Completion
requires a shared-policy native run through the affected decisions, appropriate
paired/privacy/adversarial fixtures, one stable combined release and owned cleanup.

This follow-through remains open. The accepted assisted campaign is not evidence
that the full shared native profile already exists.

The integration slice, fixed-space Gym consumer, full headless profile and
operational delivery span the completed milestones **1 → 2 → 3 → 4 → 5 → 6**.
Milestone 7's assisted live campaign is accepted separately. Broader native
coverage and policy evaluation retain their own explicit evidence and limits.

During implementation, run focused `tests/agent/` and affected engine tests.
Select bridge checks through `check.py --component core|cards|items|rooms|events`
and the existing `--check` mechanism as appropriate, including shared host/router
consumers. Once stable, run:

```bash
python3 -m compileall game tests
PYTHONPATH=. python3 -m pytest -q
```

Use the [existing bridge release gate](../bridge/Sts2AgentBridge/README.md#one-release)
for a changed production package. Obtain one independent semantic review per
aggregate change that affects public information or native execution, rerun checks
invalidated by corrections, and reuse attributable unchanged evidence. Source
inspection, synthetic fixtures, native reference comparisons and live execution
retain their distinct evidence labels.

Record available implementation, review, validation, release-preparation and user-
wait times in the normal change summary. No calendar estimate or throughput target
is claimed before the first measured slice. Documentation-only changes require
only diff, link and factual checks; a plan does not itself authorize live actions.
