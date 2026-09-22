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
| Event combat continuation | `/probe/event-combat-v2/public/decision`; owned child `/probe/event-combat-v2/public/item-decision` and `item-action` |
| Combat discard/exhaust choice | `/probe/combat-choice-v1/public/decision` and `action` |
| Potion/relic collection | `/probe/item-v1/public/item-decision` and `item-action` |
| Shop and standard room flows | `/probe/room-flows-v1/public/decision` and `action` |
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

Clean completion releases the module and keeps the host available for the next
capability. An uncertain mutation, failed response delivery or failed cleanup
stops the host. There are no automatic mutation retries.
Authenticated reads that fail in the owner-frame queue return a terminal
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

Process-wide limits are
16,384 reads, 512 action reservations and 64 feature sessions, with the existing
stricter limits inside each module.

In particular, the persistent core reward reader permits **three terminal reward
screens per game process**, at most eight entries per screen, with 17 accepted
actions per screen and 51 total.
Starting another client invocation does not reset this counter. A fourth screen
currently returns the generic `unsupported_reward` before offer inspection.
Budget these screens when combining live tests; use a fresh game process for the
next batch. Event-owned resume-item children use a separate path and do not consume
this core counter.

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

| `--capability` | Behavior / required starting surface |
| --- | --- |
| `combat` | One bounded combat, including supported nested discard/exhaust choices |
| `combat-choice` | One already-open supported combat selector |
| `combat-map` | Combat → terminal rewards → independent actionable-map check |
| `rewards` | Terminal reward parent → reconciled native Proceed; no additional map probe |
| `events` | Owned event session; stop at its reported destination |
| `event-map` | Event → `map_handoff` → independent actionable-map check |
| `event-combat-map` | Event combat entry → combat → terminal rewards/map, or owned Resume callback → resumed event/map |
| `cards`, `items`, `room-event` | Corresponding standalone bounded controller |
| `shop` | Ordinary merchant inventory already open → policy → close/Leave |
| `core` | Read one `--route`, or submit its advertised `--decision` and `--action` |

A core accepted receipt is acceptance, not completion: reconcile through its
decision route. `events` may end at `combat_handoff`, `combat_resume_handoff`,
`map_handoff`, `run_abandoned` or `run_won`; entry alone is not combat victory.
Architect currently fails live admission; see [status](../../docs/STATUS.md).
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

`--choice-policy first-select` (default) fills a combat selection to its maximum;
`minimum` confirms as soon as native controls permit it. These are mechanical
policies, not strategic-quality claims. Controllers preserve separate attempted,
accepted and reconciled parent/child counts, including on failure.

Recognized read failures retain `read_diagnostic` with the fixed runtime code and
bounded stage timings described above. Raw response bodies and exception/native
data are not retained. Diagnostics do not relax stop/cleanup behavior.

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
17 accepted/25 attempted actions and eight known no-mutation stale rejections,
subject to the process-wide limits above.

Results retain verified collections, special cards, discarded potions, skipped
potions and capacity gains. Skips count only after verified native exit; an
accepted click alone is not an effect. Ready schemas distinguish special cards,
item identity, potion slots, capacity and exact Fake Lee’s Waffle healing; waiting,
completion and receipt schemas keep their own versioning. See the
[terminal reward reference](../../docs/GENERIC_EVENTS.md#terminal-combat-rewards)
for exact wire/effect semantics and the eight-entry limit.

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
