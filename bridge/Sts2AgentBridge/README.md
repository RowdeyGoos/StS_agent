# Live bridge usage

One production mod, **Sts2AgentBridgeUnified**, contains the live capabilities.
`apps/bridge/` owns runtime, client, package and operational tools; `components/`
holds capability modules and `src/` holds shared core adapters/codecs.

Start with [support and known limits](../../docs/STATUS.md). This guide owns
**commands and runtime operation**, not test chronology. Read the
[live development guide](../../docs/LIVE_DEVELOPMENT.md) before build/install/live work.

- [Runtime and routes](#runtime-and-routes)
- [Development checks](#development-checks) and [release](#one-release)
- [Installation](#installation-client-and-cleanup), [client modes](#client-modes),
  [shop policies](#shop-policies), [event policies](#event-policies),
  [reward policies](#reward-policies), and [cleanup](#cleanup)

<a id="runtime-and-capabilities"></a>

## Runtime and routes

| Module | Existing interface |
| --- | --- |
| Core combat, rewards, map, rest/basic rooms | `/probe/v0/health`, `/probe/v0/manifest`, `/probe/v0/public/*` |
| Shared public agent decisions | `/probe/agent-v1/public/decision` and `action`; bounded combat/selection/reward/map profile |
| Event combat continuation | `/probe/event-combat-v2/public/decision`; owned child `/probe/event-combat-v2/public/item-decision` and `item-action` |
| Combat discard/exhaust choice | `/probe/combat-choice-v1/public/decision` and `action` |
| Combat pile choice, including visible Draw | `/probe/combat-choice-v2/public/decision` and `action`; same exclusive owner |
| Campaign combat choices, including mandatory offered cards | `/probe/combat-choice-v3/public/decision` and `action`; same exclusive owner |
| Potion/relic collection | `/probe/item-v1/public/item-decision` and `item-action` |
| Shop, standard room flows and additional rest options | `/probe/room-flows-v1/public/decision` and `action` |
| Interactive rest options, selectors and Heal rewards | `/probe/rest-v3/public/decision` and `action`; the same exclusive room module |
| Standalone card selection | `/card-selection-v1/parent`, `parent/action`, `child`, `child/action` |
| Generic events and their children | `/probe/generic-event-v7/public/decision` and `action` |

All routes use one authenticated loopback listener at `127.0.0.1:43117` and one
owner-frame queue. Native feature sessions are created only when their route is
requested. Generic events prepare their 34 observational hooks across successive
reads, one target per read. Preparation returns the existing waiting response;
no option is published or armed until installation finishes. The session allows
at most 35 preparation reads, preserves exclusive partial ownership and checks
for foreign patches before every step. Partial installation is cleaned up by the
same module owner. The frame-result deadline is 500 ms. The session owns its parent and child
operations until the
native result reconciles and disposal succeeds; another capability receives
`capability_busy`. The standard event parent retains its item-child route.
Core actions likewise fence unrelated operations until their decision reconciles.
Combat ownership retains the exact queued native action through its execution and
nested selectors. Changed HP/energy or a closed selector does not establish
completion; end-turn also waits for turn advancement and coherent readiness.

Clean completion releases the module and keeps the host available for the next
capability. An uncertain mutation, failed response delivery or failed cleanup
stops the host. There are no automatic mutation retries.
An authenticated GET cancelled before the owner-frame callback is claimed can
receive one internal replacement submission in the same exchange. The cancelled
callback cannot execute later. Recovery retains the existing module and pending
action, consumes another read reservation and is capped at eight replacements
per bridge process. Each submission retains its 500 ms frame-result deadline;
the connection lifetime is unchanged. POSTs and callbacks already claimed are
never retried. A second failure, exhausted budget or expired connection stops
the host under the existing cleanup rules.

Unresolved authenticated read failures in the owner-frame queue return a terminal
`kind: error` with one fixed code: `dispatch_unavailable`, `dispatch_busy`,
`dispatch_timeout_before_claim`, `dispatch_timeout_after_claim`, `dispatch_fault`
or `dispatch_invalid_result`. Failed read replies also carry up to 15 fixed-name
stage timings, each capped at 3,000 ms, with the active stage at snapshot time.
They measure time between markers (including compilation or called work), not
CPU profiling or the exact instant of deadline expiry. They are per-read and
contain no game state or request fields. These diagnostics contain no exception/native data
and do not authorize retry or handoff; the host still stops and cleans up any
late callback. POST failure behavior and queue deadlines are unchanged.

Event-combat resumption failures retain terminal `backend_fault` and add a closed
`resume_diagnostic` value identifying the rejected callback, task, ownership,
layout, UI, travel or item-settlement boundary. The native observer preserves the
first failure. Unknown enum values normalize to `diagnostic_unavailable`; no
native values or exception text are emitted. This metadata does not relax guards
or permit retry. Event diagnostic headers separately distinguish ownership
predicates from combat-entry callback, run, rewards, encounter, state, parent,
player and node checks. These closed labels report the actual evaluated boundary;
a combat rejection is not inferred to be an ownership failure.

Process-wide limits are 131,072 reads, 8,192 action reservations and 64 feature
sessions, with stricter limits inside individual controllers. The production core
reward reader permits **64 terminal reward screens per game process**, at most
eight entries and 17 accepted actions for schemas 1–8; schemas 9–10 admit 32 entries
and 65 accepted actions. Starting another client resets
none of these counters. Event-owned resume-item children use a separate path and
do not consume this core reward counter.

A core `stale_decision` rejection with `mutation_state: none` permits a fresh
observation: native dispatch did not occur. Once its response is fully sent, its
reservation is released; a fresh selection still revalidates native legality and
consumes the bounded attempt budget. Other rejections remain terminal.

The existing route/body versions remain meaningful protocol contracts. The
manifest reports bridge version `1.0.0` and Harmony support. Internal historical
namespace names do not denote separately installed mods.

## Development checks

Use Python 3.10+ and the existing environment. From the repository root:

```bash
.venv/bin/python -B bridge/Sts2AgentBridge/check.py --suite sources
.venv/bin/python -B bridge/Sts2AgentBridge/check.py --component events --suite python
.venv/bin/python -B bridge/Sts2AgentBridge/check.py --component events --suite test \
  --dotnet /ABS/dotnet --game-data-dir /ABS/data_sts2_macos_arm64
```

Select `host`, `core`, `items`, `rooms`, `cards` or `events` for focused behavior
checks. `all` is the default. `sources` checks the complete explicit source graph;
`python` runs the affected Python fixtures; `test` adds affected C# behavior and
producer/client integration. `build` compiles only the one production DLL.
A narrow correction can run its individual existing fixture directly.

List exact check names without an SDK or build, then select only the relevant
checks during development. Repeat `--check` to select more than one:

```bash
.venv/bin/python -B bridge/Sts2AgentBridge/check.py --component events --list-checks
.venv/bin/python -B bridge/Sts2AgentBridge/check.py --component events \
  --check test:components/events/direct_input_tests/DirectTransformInput.Tests.csproj \
  --dotnet /ABS/dotnet --game-data-dir /ABS/data_sts2_macos_arm64
.venv/bin/python -B bridge/Sts2AgentBridge/check.py --component events \
  --check events:host_native --event-group offers \
  --dotnet /ABS/dotnet --game-data-dir /ABS/data_sts2_macos_arm64
```

`--event-group` selects related integration cases; repeat it to combine groups.
The listing includes the available groups. Unknown check names fail before any
check executes. Selected checks build their required fixtures automatically and
record their selection in `result.json`; they do not produce a release manifest.
Selection is explicit, not automatic dependency-impact analysis: include the
affected host, native and shared-router checks for changes crossing those boundaries.

Event integration runs up to four isolated Python workers by default, each still
starting and disposing a fresh C# process for every scenario. Related baseline
and comparison cases remain together. The larger `reward_sets` group is scheduled
as four independent parts; selecting that group still runs all its cases.
When both are selected, the native event regression suite overlaps integration
after their fixtures have been built. This adds one C# test process alongside
the integration workers. Failures stop the peer suite and prevent release output;
logs remain separate for each check. Builds and other check groups stay sequential.
Use `--jobs 1` to disable both kinds of overlap for serial diagnosis, or
`--jobs N` (1–8) to bound integration concurrency. The full event matrix runs when
`--event-group` is omitted. Per-check timings can overlap, so their sum need not
equal the full gate's elapsed time.

The checker pins .NET SDK **9.0.303** and read-only `sts2.dll`, `GodotSharp.dll`
and `0Harmony.dll` identities. It uses no NuGet feeds and isolates outputs under
`/private/tmp/sts-bridge-*`. Native fixtures use inert game objects; target-game
assemblies are not executed. Test loopback listeners may need sandbox permission.

New features extend the shared modules and relevant tests. They do not create
another launcher, listener, operator tree, package, source copy or release gate.
Do not run gameplay checks for documentation-only changes.

## One release

Once behavior is stable, run:

```bash
.venv/bin/python -B bridge/Sts2AgentBridge/check.py --suite release \
  --dotnet /ABS/dotnet --game-data-dir /ABS/data_sts2_macos_arm64
```

The release suite always runs all checks and all event integration groups;
`--check` and `--event-group` are rejected. Use focused checks while correcting a
feature, then one complete gate for its stable release candidate. Parallel
integration changes scheduling, not release coverage or native ownership checks.

This runs the integrated checks, verifies a reproducible production binary, checks
its compiled entry point/dependency surface, compares the results-screen hook and
fixture declaration against pinned game PE metadata, and exercises package mutations and
owned installation/cleanup. It derives `apps/bridge/package/identity.json` from
the candidate once; package and operational tools share that binding.

A successful gate writes `bridge-release.json`, `result.json` and the three
package files into its printed scratch directory. The release manifest binds
exact source/test inputs, toolchain, references, results and binary/package
identities. Retain its printed SHA-256 separately. Failure cannot emit an accepted
release manifest. Keep one [current release record](releases/current/README.md);
Git retains earlier records. Development corrections do not need manual freezing.

The release also binds the actual `game.agent.contracts` and `game.agent.policy`
sources consumed by the live agent client. They remain shared repository modules;
there is no copied bridge policy. Changing either invalidates release verification.

To place accepted artifacts in the fixed install-input directory:

```bash
.venv/bin/python -B bridge/Sts2AgentBridge/apps/bridge/package/publish.py \
  --release-manifest /ABS/bridge-release.json --release-sha256 <accepted-hash> \
  --dll /ABS/release-output/package/Sts2AgentBridgeUnified.dll
```

This verifies current release sources and package identity, then creates
`/private/tmp/sts-unified-bridge-release` exclusively. It never overwrites or
adopts an existing directory. It does not install or launch the game.

## Installation, client and cleanup

Within the user's requested live scope, the single operational entry point is:

```bash
.venv/bin/python -B bridge/Sts2AgentBridge/apps/bridge/operations/run.py \
  --release-manifest /ABS/bridge-release.json --release-sha256 <accepted-hash> \
  --mode install
```

It creates only the owned `Sts2AgentBridgeUnified` overlay and the fixed
`Library/Application Support/Sts2AgentBridge/unified/` configuration/credential.
Existing legacy overlays and campaign state are conflicts, not files to adopt or
delete. Native dependencies and the game build remain pinned. Configuration is
fixed; credentials are generated by the owned installer, not hand-entered.

After installation and the user's requested game setup, use one client:

```bash
.venv/bin/python -B bridge/Sts2AgentBridge/apps/bridge/client/run_live.py \
  --release-manifest /ABS/bridge-release.json --release-sha256 <accepted-hash> \
  --expected-state-sha256 <current-owned-state-hash> --capability events
```

## Client modes

`--capability agent` uses the same public-only chooser as the headless adapter.
It handles supported combat, nested card selection and rewards, then stops at an
actionable map. Add `--agent-dispatch-map` for a separate bounded case that selects
one legal node and stops after native completion. It reports attempted, accepted
and reconciled counts independently and stops on uncertainty. Its 180-second run
limit and native ownership/budgets remain active.

This profile requires the bridge observer to start before combat setup and an
explicitly supported deck/inventory; arbitrary reward offers can be unsupported.
See the [native producer boundary](../../docs/AGENT_CONTRACT.md#native-producer).
The [controlled live slice](../../docs/evidence/AGENT_BRIDGE_M3_2026_09_23.md) passed
with the same callback on headless and live backends, using a gold-then-leave reward
override through `run_agent(policy=...)`. That result does not cover live card-offer
selection by the default CLI chooser. A native debug fight needs a valid map
starting context; the accepted setup used a fresh act map. The optional
[Gymnasium environment and fixed public encoding](../../docs/AGENT_ENCODING.md)
are implemented for the headless slice; this does not broaden live coverage.

| `--capability` | Behavior / required starting surface |
| --- | --- |
| `campaign` | Prepared Ironclad A0 → bounded multi-act traversal; requires `--campaign-setup controlled_extra_hp` or `normal_hp`; optional `--campaign-entry resume` continues a native checkpoint |
| `combat` | One bounded combat, including supported nested discard/exhaust choices |
| `combat-choice` | One already-open supported combat selector |
| `combat-map` | Combat → terminal rewards → independent actionable-map check |
| `rewards` | Terminal reward parent → reconciled native Proceed; no additional map probe |
| `events` | Owned event session; stop at its reported destination |
| `event-map` | Event → `map_handoff` → independent actionable-map check |
| `event-combat-map` | Event combat entry → combat → terminal rewards/map, or owned Resume callback → resumed event/map |
| `cards`, `items`, `room-event` | Corresponding standalone bounded controller |
| `shop` | Ordinary merchant inventory already open → policy → close/Leave |
| `rest` | One additional rest option through the legacy precommitted controller; requires `--rest-option` |
| `rest-interactive` | One rest option with a callback for every selector and reward decision; requires `--rest-option` |
| `core` | Read one `--route`, or submit its advertised `--decision` and `--action` |

A core accepted receipt is acceptance, not completion: reconcile through its
decision route. `events` may end at `combat_handoff`, `combat_resume_handoff`,
`map_handoff`, `run_abandoned` or `run_won`; entry alone is not combat victory.
Architect admission and the ending passed under the recorded controlled-campaign
scope. See [status](../../docs/STATUS.md).
The composite modes retain earlier stage counts/results if a later stage fails.
Defeat prevents reward control. None of the `*-map` modes selects a map node.

Map verification allows five seconds/100 reads and requires a validated actionable
`/probe/v0/public/map-decision`. Only `waiting` permits another read; a late response
cannot pass. `/probe/v0/public/screen` recognizes main menu/settings and is not a
map-readiness probe. The shared client spaces exchanges by at least 60 ms within
existing budgets; rate-limited or uncertain requests are never retried.

Combat IDs bind the exact native combat instance, so identical consecutive openings
have different opaque IDs. Clients echo the 64-character lowercase hex ID. Known
no-mutation stale rejections allow bounded fresh observation; they do not permit
replay of an uncertain action. Combat/choice bounds and contracts are in
[combat choices](../../docs/COMBAT_CHOICES.md).

### Interactive rest

`--capability rest-interactive --rest-option smith` selects Smith, exposes its
native eligible cards, then confirms the selected card. `--rest-selection-policy
cancel` cancels immediately; `preview-cancel` selects the native required count
and cancels from the preview. The same choices apply to Cook's two-card selector.
Selection and deselection are individual protocol actions. Cancellation settles
only after the unchanged deck/inventory and original enabled rest controls return.

`--rest-option heal` retains ownership through the native healing task and its
rewards, including Dream Catcher cards and Tiny Mailbox potions. The existing
`--reward-policy first-card|skip-card` chooses the card behavior; an explicit
reward dismissal returns to the rest site after Skip or when potions cannot be
collected. Full-belt replacement is not exposed in this rest protocol.
Unopened card offers remain hidden. Reward collection uses the shared reward
reader with the exact rest-owned set, screen, menu and native continuation.

The Python controller accepts `run_rest(request, provider)`; every ready option,
selection or reward decision goes to that callback. The CLI's controlled chooser
is for validation; it is not the full shared policy. Other options are Lift,
Kindle, Dig, Clone and Hatch. Dig permits one owned deck/enchantment selector
of at most three cards. Unknown enabled options or unsupported follow-up screens
stop the session. Limits are 64 deck cards, 8 reward entries, 128 accepted inputs,
4,096 reads and a 120-second client budget per option. Completion returns at the
rest site without pressing its final Proceed. Parent completion, child results,
and cancellation remain distinct; uncertain actions are never retried.

### Campaign traversal

`--capability campaign --campaign-setup controlled_extra_hp` attaches to a manually
prepared Ironclad A0 run at its first event or map, with floor at most one and
max HP above 80. The flag records the setup; it does not grant HP, create a run,
change its seed or reset the game. `normal_hp` accepts the same entry without
requiring an HP increase. Profile selection and launch follow the live guide.

The default `--campaign-entry fresh` retains that entry requirement. After native
Continue, `--campaign-entry resume` accepts a supported ready surface at a later
floor or act. It starts a new segment with the same profile/HP and subsequent
run/act/floor continuity checks. It neither reloads a save nor retries or adopts
an uncertain action from a failed host. Reload the native checkpoint in a fresh
game process after a failed attempt, following normal owned cleanup and setup.
The result records `entry_mode`, the entry scene and only the acts and bosses
observed in this segment. A native ending reached in resume mode reports
`continued_victory` with `full_campaign_verified: false`, even if all bosses
happened to be observed. Prior partial runs are separate operational evidence.

Campaign combat accepts an actionable decision with zero living enemies, as
occurs between Test Subject's lives. It continues using only native-advertised
legal actions, including End Turn; an empty enemy list alone never means victory.
Standalone combat retains its earlier nonempty-enemy profile.
Combat decisions containing a native `InfiniteWithoutNumbers` health display
use **schema 2** on the existing route. Every enemy then includes `hp_display`
(`numeric` or `infinite`); infinite enemies have `hp: null` and `max_hp: null`.
Neither the response nor its opaque identity includes the native hidden health
sentinel. All-numeric, waiting and unsupported decisions retain schema 1.
`InfiniteWithNumbers` remains numeric because the native UI shows those values;
unknown display modes are unsupported. Schema 2 also covers a terminal defeat
with a surviving infinite-health enemy. Campaign clients explicitly accept this
extension; standalone combat and shared `agent_v1` retain their numeric profile.
The campaign ends turns when every remaining enemy displays infinity and avoids
potion use in that phase. Mixed encounters retain finite targets. Native legal
actions, task completion and the actual combat ending remain authoritative.
Initially empty terminal rewards use the native reward set's sole player and
exact run/room/screen binding. Proceed is offered only when the native button is
usable; a nonempty set whose buttons are still loading remains waiting. The
campaign reward route verifies the native act/ending transition before completion.

The declared policy is `native_campaign_smoke_v6`: prioritize an advertised legal
Frantic Escape card against The Insatiable's instant-kill mechanic, then redirect
a recommended card targeting Parafright to The Obscura when the same card has a
legal target action on the living summoner. Other combat recommendations are
unchanged apart from the visible-infinity handling above. Collect gold and potions when capacity is available, skip optional combat cards, heal at
rest sites, leave shops without purchases, open chests and decline their relics,
and prefer advertised
Leave/Ignore/Refuse/Proceed event options. Map routing prefers rest sites,
ordinary fights, shops, treasure, elites, unknowns, ancients, then bosses. Other
event choices use the first legal action and supported child controllers.
This tests native traversal; the shared `agent_v1` projection and headless
`full_run_v2` policy/encoding keep their separately declared coverage.
Combat children use `combat_card_choice_v3`, which admits visible draw-pile
grids such as Séance and mandatory one-of-one-to-three offered cards such as
Knowledge Demon's status choice. Public candidates follow native displayed-holder
order, never hidden draw order. Offered choices use `pile: offer`, bind the native
result task and do not imply that a card was added to a pile or deck. Ordinary combat retains the v1 selector contract.

Campaign combat also uses `combat_potions_v1` through the existing core owner.
`GET /probe/combat-potions-v1/public/decision` returns `waiting` or `ready` with
an opaque `decision_id`, the matching `combat_decision_id`, public inventory rows
(`slot`, `id`, `supported`) and `legal_actions`. `POST .../action` takes the usual
decision/action headers: `use:S` targets self/no creature; `use:S:T` targets the
advertised living enemy index. Up to eight inventory slots and six living enemy
indices are supported. The exact native potion and creature, not a later occupant
of those indices, remain bound through execution.

The first manual-use slice supports Blood Potion, Block Potion, Dexterity Potion,
Energy Potion, Explosive Ampoule, Fire Potion, Flex Potion, Fruit Juice, Heart of
Iron, Liquid Bronze, Regen Potion, Speed Potion, Strength Potion, Vulnerable Potion
and Weak Potion. Automatic potions remain native; other manual types, including
card offers, draw/autoplay and pile selectors, have no advertised use actions.
The policy uses damage/stat potions when available, defensive potions against
attack intents, energy at one or less with cards in hand, and healing at 80% HP or
less. Targeted uses prefer The Obscura and then larger enemies to avoid spending
potions repeatedly on respawning minions. This is a smoke policy, not an optimized
potion-saving strategy. Full inventory uses `skip-full`; it never discards to make
room and does not buy shop potions.

A queued receipt is followed by `waiting` until that exact native UsePotionAction,
its raw effect task and execution/completion tasks succeed and the exact potion
is removed. Only successful hook cleanup produces `resolved` with the matching
decision/action IDs. Early inventory removal and changed HP are insufficient.
Another capability, card action, chooser or outer event continuation cannot take
ownership while the potion is pending. Unresolved disposal retains a revocation
guard so a delayed action cannot execute after the host stops. Failures terminate
the host without retry; a pre-dispatch stale rejection certifies no mutation.
The adapter allows 256 accepted potion decisions per process; the client allows
24 attempts per combat and 30 seconds/640 completion reads per potion, within
campaign budgets. Each combat stage records a `potions` list and separate
`potion_attempted`, `potion_accepted`, `potion_reconciled` counts. Combat-v0 and
`agent_v1` action/encoding contracts retain their earlier scope.

The read route `/probe/campaign-v2/public/decision` reports public scene, act,
total floor, character, ascension and HP with an opaque run binding. Its action
route advertises `open_chest`, then `skip_relic` under a fresh decision ID, or
`proceed` for a no-purchase leave from an untouched, closed shop. Opening a chest
allows its normal automatic gold reward. Skip is advertised only after native
Open reaches the relic chooser and its delay/tutorial tasks finish. Open is
reconciled at that visible decision, while its pending native task stays owned
across both POSTs. The exact queued null-index relic choice and Proceed task must
complete before map handoff. Single-player Skip intentionally leaves Open suspended on the
collection's pending picking task; the adapter verifies that dormant state, the
native skipped flag and unchanged owner/collection immediately before cleanup.
It never completes or cancels that task artificially. Reads never dispatch; foreign
owners, unexpected extra reward overlays, tutorial interference and incomplete
cleanup stop the host.
This explicit chest sequence replaced the pre-acceptance `campaign_v1` route;
prior attempts retain their original policy and route identities. Chest relic
selection is outside this policy.

The closed-shop action reuses the existing shop identity and inventory
reconciliation with a campaign-only entry; the ordinary shop mode still expects
an open inventory. Modal/tutorial interference stops it. Terminal rewards use
`/probe/reward-v2/public/decision` and `/action`: completion distinguishes `map`,
`act` and `ending`. The existing v1 reward route rejects an act transition before
input. Native Proceed/vote/task completion, exact owner and destination, and hook
cleanup must all succeed before another capability can take ownership.

The campaign stops at 90 minutes, 320 stages, 8,192 POSTs or 131,072 reads. Each
combat retains a 15-minute, 96-round, 512-accepted-action limit. Process budgets
are persistent: 8,192 combat actions, 80 map actions, 160 room actions and 64
terminal reward screens (up to 32 entries and 65 accepted actions under schemas 9–10), 1,024
v2/v3 combat-selector episodes (32 inputs each), plus
the unchanged 64 feature-session limit. Starting another client resets none of
these native counters. Ordinary bounded client modes keep their tighter limits.

The controller records known attempted/accepted/reconciled counts on failures,
including bounded nested combat-choice summaries and their separate child counts,
never retries uncertain input, and requires fresh entry, observed boss victories
in all three acts and the native Architect `run_won` chain before reporting full victory.
An ending handoff alone is not victory. Unsupported content and cleanup failures
stop execution. Stage summaries are operational evidence, not training trajectories;
retaining live observation corpora requires separate scope.

`--choice-policy first-select` (default) fills a combat selection to its maximum;
`minimum` confirms as soon as native controls permit it. These are mechanical
policies, not strategic-quality claims. Controllers preserve separate attempted,
accepted and reconciled parent/child counts, including on failure.

Recognized read failures retain `read_diagnostic` with the fixed runtime code and
bounded stage timings described above. Raw response bodies and exception/native
data are not retained. Diagnostics do not relax stop/cleanup behavior.

## Rest options

Use `--capability rest --rest-option lift|kindle|dig|cook|clone|hatch` with the
unified client's usual release/installation arguments. These additions are
implemented and validated offline in source; the existing release is unchanged.
Build/package the combined bridge before installing through the normal workflow.

Cook removes the first two removable originals by default. Add
`--rest-cook-slots 0 3` to choose specific **zero-based original deck slots**, in
increasing order. The chosen pair must be advertised as legal; unavailable pairs
stop before input. Dig handles one native deck/enchantment pickup selector by
choosing the first eligible originals up to its native maximum (at most three).
Other pickup follow-up surfaces stop without attempting unrelated input.

The existing room-flow routes select `flow_kind: rest`, `version: rest_v2`.
Ready observations contain `phase: choose_option`, `decision_id`, `options`
(`action_id`, `counter`, `enabled`, `amount`), `cards` (`slot`, `key`, `upgrade`,
`removable`), `legal_actions`, and null `result`. The digest binds the session,
option order/counters/amounts/flags and public card list. Actions are `lift`,
`kindle`, `dig`, `clone`, `hatch`, or `cook:<first-slot>:<second-slot>`.
Cook publishes all legal pairs within the 64-card starting-deck bound; selected
native models are bound separately to reject same-valued replacements.

| Option | Reconciled effect | Public counter |
| --- | --- | --- |
| Lift | Same Girya, +1 | Lifts used |
| Kindle | Same Pumpkin Candle, +5 | Remaining combat count |
| Dig | Exact new relic and completed native pickup callback | Relic count |
| Cook | Exact selected originals removed and +9 max HP | Max HP |
| Clone | Copies of all Clone-enchanted originals, verified through native insertion results; add-time upgrades allowed | Deck count; `amount` is the number of copies |
| Hatch | Exact Byrdpip obtained and every original egg transformed into Byrd Swoop | Relic count |

Accepted actions return `waiting`/`action_waiting` until their native effect and
`AfterSelectingOptionAsync` finish. Hooks must detach before `complete` is
published. Completion has empty options/cards/actions and a `result` containing
the accepted `decision_id`, `action_id`, `before`, and `after`. The client returns
`handoff: rest`; it does not press Proceed or consume additional Miniature Tent
options. A stale binding, wrong effect, failed task, lost receipt or failed cleanup
stops without retrying the action. Native Cook cancellation is not exposed.

`rest_v2` replaces the unreleased Lift/Kindle-only `rest_v1` contract to add card
identities, target pairs and non-counter effects. Other room-flow versions retain
their existing semantics.

Focused checks: `--component rooms --suite test` covers core/native and Python/C#
integration; `--component rooms --suite python` covers controller failures.
The unified tests and `shared_client:socket` exercise the public parser, client
and router for all six actions. Native fixtures use inert game surfaces with real
Harmony; the existing pickup fixtures cover the shared card-input driver.
Production builds use pinned game references. These are not live gameplay results.

## Shop policies

Use `--capability shop` for the ordinary merchant, not Fake Merchant's event.

| Flag | Default | Meaning |
| --- | --- | --- |
| `--shop-max-purchases 0..8` | `1` | Total purchases, including removal; zero closes/leaves without buying |
| `--shop-purchase-policy` | `cards` | `cards`, `potions`, `cards-and-potions`, `relics`, or `all`; eligible affordable offers in slot order |
| `--shop-gold-reserve G` | `0` | Gold retained after each purchase/removal |
| `--shop-removal-policy` | `skip` | `first` removes the first eligible original in deck order before other purchases |
| `--shop-potion-policy` | `skip-full` | `replace-first` discards an eligible original potion to make room; new pickups are protected |

For example, add `--capability shop --shop-purchase-policy all
--shop-max-purchases 5 --shop-gold-reserve 75` to buy up to five supported items
while retaining 75 gold. Removal consumes the same purchase budget: raise the
limit for removal plus buying. Removal and purchasing leave the inventory open;
close and native Leave are separate actions.

`shop_v6` publishes potion slots, relic keys, removal candidates and capacity hints,
all bound into the decision ID. Exact model/owner, native price/debit, stock or
callback-certified restock, task completion and retained survivor inventories are
checked before continuing. Replacing a potion has a separate receipt and guarded
native discard. Eight purchases, eight discards, close and Leave fit eighteen
reservations; the controller retains all counts on failure.

Removal precommits to `remove:<deck-slot>` and verifies the native preview and
exact deletion; grid order need not match deck order. Supported relics have the
pinned no-op pickup callback, the exact Potion Belt +2-slot effect, or one of the
five supported clone/enchantment selectors. Selectors use eligible originals in
deck order up to the native maximum (domain 1–64); other pickup callbacks are not
implicitly supported. Restock requires the fresh model/key/price from the native
completion callback. See [status](../../docs/STATUS.md#combat-map-and-rooms) for
the supported relics and separate live coverage.

## Event policies

`--event-option <stable-id>` selects an exact legal **first** parent option, then
uses first-legal choices. Missing/illegal/ambiguous options stop before input.
For example, the initial Dummy training option is
`BATTLEWORN_DUMMY.pages.INITIAL.options.SETTING_2`; `SETTING_1` selects its potion
branch. Use `event-combat-map` to drive the fight and owned callback through map.
Automatic upgrades are not certified merely because the callback completed.

Fake Merchant starts with its inventory closed. Its default event policy opens,
buys affordable supported relics in slot order, closes and leaves. An exact initial
Foul Potion choice can instead start combat; it is unavailable after shopping.
Crystal Sphere must also be entered through an owned ordinary event choice. Its
default provider selects the big tool and first legal hidden cells, resolves earned
rewards and exits. Custom providers receive its public `crystal_sphere` child view.

`--abandon-policy cancel` is the default for Trial's owned confirmation popup.
`confirm` explicitly ends the run and requires verified `run_abandoned`. Use
`events` for terminal outcomes; a map-requiring stage cannot accept them as a map.
Generic parent bodies use `generic_event_v10` over the existing v7 routes.

The final event `effects: unverified` describes the latest parent action, usually
Proceed. Cumulative `completed_card_children`/`completed_item_children` retain
verified child completions. [Generic event contracts](../../docs/GENERIC_EVENTS.md)
define discovery, ownership, custom screens, callback resumption and exact effects.

## Reward policies

Potion flags have **different scopes and defaults**:

| Flag | Scope | Default | Other values |
| --- | --- | --- | --- |
| `--potion-policy` | Terminal rewards in `rewards`, `combat-map`, non-resuming `event-combat-map` | `stop-on-full` | `skip-full`, `skip-all`, `replace-first` |
| `--event-potion-policy` | Owned event/mixed/resume reward screens using `item_policy_v1` | `skip-full` | `skip-all`, `replace-first`, `stop-on-full` |
| `--shop-potion-policy` | Ordinary shop | `skip-full` | `replace-first` |

`skip-full` collects/buys potions that fit; `skip-all` leaves all potion rewards
even with free slots. `replace-first` protects new pickups and independently
reconciles an eligible original-potion discard before collection. Capacity-first
paths use supported Potion Belt gains before replacement. Native Skip/Proceed must
be legal; no policy invents a skip action. Event/resume policies do not extend
Crystal Sphere's own full-inventory behavior.

`--reward-policy first-card` (default) or `skip-card` governs ordinary terminal
card menus. Both collect supported gold/items and direct special cards. Unsupported
uncollected rewards stop the flow. Terminal reward bounds are 45 seconds, 512 reads,
17 accepted/25 attempted actions for schemas 1–8, or 65 accepted/73 attempted
actions for schemas 9–10, and eight known no-mutation stale rejections,
subject to the process-wide limits above.

Results retain verified collections, special cards, discarded potions, skipped
potions and capacity gains. Skips count only after verified native exit; an
accepted click alone is not an effect. Ready schemas distinguish special cards,
item identity, potion slots, capacity, exact Fake Lee’s Waffle healing and
Strawberry’s +7 max HP/+7 HP, and Bowler Hat’s modified gold gain; waiting,
completion and receipt schemas keep their own versioning. See the
[terminal reward reference](../../docs/GENERIC_EVENTS.md#terminal-combat-rewards)
for exact wire/effect semantics and versioned entry limits. Expanded screens use
the unified client, whose response bound is 64 KiB; the retired standalone probe
transport retains its original 4 KiB bound.

## Cleanup

Normal quit and stopped-process/closed-listener verification precede cleanup.
Use the installation command with `--mode quarantine`, then `--mode purge`, each
with `--expected-state-sha256` from the preceding owned state. Preserve release
source/package bindings until the installed campaign is closed. Cleanup verifies
exact ownership, state lineage and unchanged base files. Failed disposal or
unresolved native work cannot be reported as a clean handoff.

## Historical references

[Release history](releases/history/README.md) retains original identities; Git
retains the removed source trees and feature workflows. Commit `1d63e74` contains
the four interim consolidated app releases. Do not restore them as dependencies.

Original `contracts/live_probe_v0`, Python consumers and semantic fixtures keep
their paths. `tests/core_reference/` is a test-only assembly without a mod entry
point. The old `tools/run_gate.py` and R0a `verify_live_campaign_inputs.py` workflow
are retired. The latter binds documentation and inputs in its original checkout;
see the [documentation archive](../../docs/archive/README.md#original-bytes-and-paths).
Old operator/launch workflows are historical, while the actual core exchange/
manifest helper is compatibility-tested against the unified listener. Use the
entry points above for current work.
