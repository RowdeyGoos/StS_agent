# Live bridge

One production mod, **Sts2AgentBridgeUnified**, contains all supported live
capabilities. `apps/bridge/` owns its runtime, client, package and operational
tools. `components/` holds editable capability modules; `src/` retains the shared
public combat/reward/map/room adapters and codecs. The four former feature apps
and the separate original production project are retired.

Read [current status](../../docs/STATUS.md) for evidence and
[live development](../../docs/LIVE_DEVELOPMENT.md) for the working process.

## Runtime and capabilities

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
same module owner. The 500 ms frame-result deadline is unchanged. The current session owns its parent and child operations until the
native result reconciles and disposal succeeds; another capability receives
`capability_busy`. The standard event parent retains its item-child route.
Core actions likewise fence unrelated operations until their decision reconciles.

Clean completion releases the module and keeps the host available for the next
capability. An uncertain mutation, failed response delivery or failed cleanup
stops the host. There are no automatic mutation retries.
Authenticated reads that fail in the owner-frame queue now return a terminal
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
screens per game process**, with 17 accepted actions per screen and 51 total.
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

Transformation now uses direct native input for every eligible allocated holder.
The test-only card16 restriction is removed; exact holder/model ownership,
native legality, preview membership, deferred input and effect checks remain.
Generic single/multi-upgrade selectors now also accept allocated holders beyond
the viewport, retaining native clickability and exact preview/effect checks.
This does not support cards without allocated holders or certify every selector.
The upgrade extension has a live Sapphire Seed single-upgrade result for
off-screen Defend slot 20 in a 23-card eligible domain; see the
[combined batch](../../docs/evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md).

Crystal Sphere is implemented in the working checkout through the existing generic
event controller. Enter using an advertised ordinary event choice; the default
policy selects the big tool, reveals legal cells, resolves earned rewards and uses
the native Leave/map path. Custom providers receive `crystal_sphere` child views.
See the [sphere contract](../../docs/GENERIC_EVENTS.md#implemented-offline-crystal-sphere)
for the public projection and limits. The September 12 Uncover Future/gold/map case passed live, including exact
completed-overlay cleanup; other branches retain offline coverage.

The current implementation batch adds `shop_v6` restock/replacement and native
shop pickup selection (first original deck cards up to the native maximum), plus
`item_policy_v1` for full-inventory event/mixed/resumed rewards. Use
`--shop-potion-policy replace-first` or `--event-potion-policy replace-first` to
replace original inventory potions; new pickups remain protected. Defaults skip
potions that do not fit. The Architect task chain requires a verified `run_won`, but its live admission
currently stops before dispatch with `unsupported_state`; the initial
Fake Merchant screen advertises an explicit Foul Potion fight choice when legal.
These changes passed the combined validation gate. Seven representative shop and full-belt event cases passed live; remaining coverage is tracked in current status.

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

Capabilities are `events`, `event-map`, `event-combat-map`, `combat`, `combat-map`, `combat-choice`,
`rewards`, `cards`, `items`, `shop`, `room-event` and `core`.
The feature modes run their bounded controller; `core` observes one `--route` or
submits an advertised action with `--decision` and `--action`. A core accepted
receipt reports acceptance, not completion; reconcile through the corresponding
decision route. Event choices use the replaceable first-legal host provider.
The client verifies release and owned installation before credential access.

When an authenticated read returns a recognized runtime error, the final result
also retains `read_diagnostic`: its fixed failure code and bounded initialization
stage timings. The original host outcome and action counts remain intact. Unknown
fields, free-form error text and raw response bodies are not retained. This report
does not authorize a retry or change the runtime's stop/cleanup behavior.

Use `--capability shop` with the ordinary merchant inventory open. The default
buys the first eligible affordable card once, then closes the inventory and leaves.
`--shop-max-purchases N` permits zero through eight total purchases in one visit;
zero leaves without buying. `--shop-gold-reserve G` keeps at least G gold after
each purchase (default zero). `--shop-purchase-policy` accepts `cards` (default),
`potions`, `cards-and-potions`, `relics` or `all`. Selection follows slot order
among eligible offers. For example, `--capability shop --shop-purchase-policy all
--shop-max-purchases 5 --shop-gold-reserve 75` buys up to five supported items
while retaining 75 gold, then closes and leaves.

Use `--shop-removal-policy first` to remove the first eligible card in deck order
before buying. The default is `skip`, including with purchase policy `all`.
Removal shares the total purchase limit and gold reserve: with the default limit
of one, `first` removes one card and leaves. For removal plus purchases, raise
`--shop-max-purchases`. The wire action `remove:<deck-slot>` precommits to an exact
public candidate; the bridge opens the native service, selects that model and
confirms its exact preview. Grid order may differ from deck order. This is a
single-player flow supporting one through 64 eligible allocated cards.

Removal verifies the exact price debit, selected-card deletion, unchanged
survivors and other inventory, removal-use counter increment, exhausted service,
completed native wrapper/callback and closed selector. Cancellation, changed
foreground/ownership or uncertain completion stops the host without retrying.
Pending native work cannot be reported as successful cleanup. Exact removal,
separate inventory close/Leave and actionable map return passed live; see
[current status](../../docs/STATUS.md).

Relic purchases support models inheriting the pinned base no-op `AfterObtained`
callback (for example Anchor and Bag of Preparation), plus the exact Potion Belt
+2 empty-slot effect. Existing relics retain their order, identity and keys; the
exact purchased model must be appended and owned by the local player. Pending
reconciliation follows native payment, relic insertion, capacity effect and
completion order. Relics already owned, or gains beyond eight potion slots, are
ineligible. Dolly’s Mirror, Gnarled Hammer, Kifuda, Punch Dagger and Royal Stamp
also support their exact native pickup selectors for decks of 1–64 cards. The
policy selects eligible originals in deck order up to the native maximum, verifies
the exact preview and waits for the native clone/enchantment effect. Other pickup
callbacks remain unavailable until a concrete native caller is supported.

Potion purchases require a free slot and verify exact first-empty insertion,
local ownership and unchanged other inventory. Full inventories leave potion
offers unpurchased while other eligible purchases can continue. Opt into
`--shop-potion-policy replace-first` to discard an eligible original potion before
buying; newly acquired potions are protected. Each discard has its own receipt,
native execution guard and inventory reconciliation. Under `all`, a
supported Potion Belt can make space for subsequent potions. Each purchase
verifies the displayed/native price, exact debit, cleared stock or callback-certified restock, and callback
disposal before the next decision. Existing deck, relics and potion slots remain
checked through close and map return, except the selected purchase's exact effect.

The room routes remain unchanged, with shop body version `shop_v6` and event body
version `event_v1`. Shop player observations include ordered public `potion_slots`
keys/nulls and `relics` keys; offers include `potion_capacity_gain` (zero or two).
The observation also includes `removal_candidates` with original deck slots, keys
and upgrade levels. All are bound into the decision ID. Eight purchases, up to eight original-potion discards, inventory close and native
Leave consume at most eighteen action reservations. `prior_results` carries the latest
reconciliation, while the controller retains all attempted/accepted/reconciled
counts, including on failure. A restocked entry needs its exact fresh model, key
and price from the native completion callback before it can be purchased again.
Mixed ordinary-shop card/potion purchases, exact removal and restocked potion
replacement passed representative live validation through map return. Relic
capacity and pickup-selector purchases still need live coverage. This policy does not evaluate strategic item value.

Use `--capability combat` for bounded combat with nested discard/exhaust choices,
or `combat-choice` to resolve one such selector. `--choice-policy minimum` confirms
as soon as the native control permits it; the default `first-select` fills the
selection to its maximum. Parent combat and child selection have separate
attempted/accepted/reconciled counts, retained on failure. Supported native
surfaces, protocol semantics and limits are in [combat choices](../../docs/COMBAT_CHOICES.md).
Neow's Fury zero and two-card selection with combat resume passed in the
[September 9 live batch](../../docs/evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md).

Use `--capability combat-map` to finish one combat, resolve its gold/card/item rewards,
and verify an actionable map with the same client. Defeat stops before rewards.
The default `--reward-policy first-card` claims gold and chooses the first legal
card; `skip-card` uses the native card skip. `--capability rewards` starts directly
at a reward parent and ends after reward Proceed reconciles; it does not perform
an additional map-readiness check. Neither mode selects a map node. Unsupported
uncollected rewards stop the flow rather than being abandoned by Proceed.

The composite result retains `combat`, `rewards` and `map_handoff` summaries plus
its final `stage` and `code`. A failure never erases earlier reconciled actions or
combat chooser results. Reward gold/card totals count only verified transitions.
Reward bounds are 45 seconds, 512 reads, 17 accepted/25 attempted actions and eight
known no-mutation stale rejections. Existing combat and map bounds also apply.
Both reward policies have shared-socket coverage and completed live from combat
through verified reward effects to an actionable map in that batch.

Combat decision IDs bind the public state to the exact native combat instance.
Identical openings in consecutive combats therefore have different opaque IDs;
repeated reads, waiting periods and event handoff notifications within the same
combat keep the same identity. Native and transport action reservations remain
intact, so old or uncertain actions cannot be replayed. The wire ID remains a
64-character lowercase hex string; clients echo it without computing it.

The shared client spaces exchanges by at least 60 ms, below the listener's
20-per-second authenticated allowance. Pacing consumes the existing exchange
budget; an expired wait or connection cannot send a request. Server rate limits
remain unchanged and rate-limited/uncertain requests are never retried.

Use `--capability event-map` to verify an event-to-map handoff. After an event
resolved with destination `map_handoff` it polls `/probe/v0/public/map-decision` within a five-second
window and 100-read cap, accepting only a validated actionable map. An in-flight
exchange can extend elapsed time by its existing two-second transport limit;
responses arriving after the polling deadline cannot pass. It selects no map node.
Only a `waiting` map response permits another read; errors, unsupported responses,
uncertainty or interruption stop the check. The result retains the full `event`
summary and a separate `map_handoff` status/read count even when that check fails.
A failed event or `combat_handoff` destination never starts the map check.

The checkout's first custom screen is Fake Merchant. Start with its inventory
closed and use `--capability events` or `event-map`. The default first-legal policy
opens the inventory, buys affordable relic offers in slot order, closes and leaves;
a choice provider may select specific published offers or close without buying.
The full six-purchase path needs nine parent actions. This is offline-tested,
support; the combat branch remains separate. Crystal Sphere now supports its
owned tool/reveal, earned-reward and native map-exit path described above.
See the [custom-screen contract](../../docs/GENERIC_EVENTS.md#implemented-offline-fake-merchant-custom-screen).

The checkout also supports `--capability event-combat-map` for a non-resuming
fight started by an owned event choice with zero to eight special-card, potion or
relic extra rewards, with at most one special card (The Lantern Key and Punch Off
Fight branches). It
requires `combat_handoff`, then uses the existing combat/rewards/map controllers.
The result preserves `event` and `combat_flow`; the latter retains each downstream
stage. `--choice-policy` and `--reward-policy` have the same meaning as in
`combat-map`. The default event policy chooses the first legal option: for the
pending Dense Vegetation live case, prepare its Fight page after Rest. Returning
to an event after combat is also supported in the checkout when its exact resume
callback completes, including an owned potion/relic reward or ordered item set.
For `combat_resume_handoff`,
the host verifies the original callback and new event node, then runs one fresh
event session through Proceed/map. Training expiry is reported as `event_resumed`,
not victory. Item collection counts/results are retained in `combat.resume_items`.
Its result retains `combat`, `resumed_event` and `map_handoff` inside
`combat_flow`. The reward controller collects a special card directly with the native reward
button; both card policies do this and record `rewards.claimed_special_cards`.
The same controller collects potions/relics with `collect:<slot>` and records
verified pickups in `rewards.collected_items`. Repeated rewards retain distinct
session identities even when visible slots compact. Item sessions use ready schema
5 for capacity rewards or schema6 for Fake Lee’s Waffle healing, with `item_key`,
`potion_capacity_gain`, public potion slots and schema6’s `heal_amount`; special-card sessions use schema 2. Ordinary sessions
and all waiting/completion/receipt payloads retain schema 1. Full potion inventories
stop with `potion_inventory_full` by default. Resume-time card rewards and nested pickup selectors remain unsupported. Terminal
Fake Lee’s Waffle verifies exact capped ten-percent healing; broader relic pickup
effects remain unsupported. See the [item reward contract](../../docs/GENERIC_EVENTS.md#extra-potionrelic-rewards-and-mixed-collection).

For terminal rewards, add `--potion-policy skip-full` to collect potions that fit
and leave the rest while completing other rewards. Use `skip-all` to leave every
potion reward, or the default `stop-on-full` to stop when one cannot be collected.
This works with `rewards`, `combat-map` and non-resuming `event-combat-map`, with
either card policy. `rewards.skipped_potions` reports the key, reward index and
reason only after verified native Proceed/map completion.
Use `--potion-policy replace-first` to discard the first eligible original inventory
potion when full, verify its removal, then collect the waiting reward. Each removal
is recorded in `rewards.discarded_potions`; newly collected potions are protected.
Replacement is restricted to single-player terminal reward screens. Custom event and resume-time item screens retain
their capacity checks. See the [policy contract](../../docs/GENERIC_EVENTS.md#terminal-potion-reward-policies).

Terminal Potion Belt rewards can now add two verified empty slots. When a waiting
potion does not fit, the controller collects an available Potion Belt before
stopping or replacing a potion. Its reward session uses ready schema 5 with
`potion_capacity_gain`; verified gains appear in `rewards.potion_capacity_gains`.
Existing potions and the gained capacity remain checked through reward completion.
This is offline-tested support for the pinned Potion Belt effect, bounded to eight
slots. See the [capacity contract](../../docs/GENERIC_EVENTS.md#terminal-potion-belt-capacity-pickup).

Owned custom event rewards and resume-time item rewards also support Potion Belt
pickup in singleton, ordered item-set and mixed card/item flows. Each potion must
fit at its original position using initially free slots or preceding belt gains.
These children keep their existing wire contracts and collect order, with no item
skip/discard policy. See the [event capacity contract](../../docs/GENERIC_EVENTS.md#implemented-offline-event-potion-belt-capacity-pickup).

Use `--event-option BATTLEWORN_DUMMY.pages.INITIAL.options.SETTING_2` with
`--capability event-combat-map` for the Battleworn Dummy training case.
Use `SETTING_1` instead for the potion-reward branch, with a free potion slot.
The host collects the owned reward, waits for callback completion and then runs
Proceed/map. This reusable option chooses the exact legal first parent option, then uses first-legal actions;
a missing/illegal requested option stops before input. It also works with `events`
and `event-map`. Automatic upgrade effects are not certified by callback completion.

Both training expiry and victory/potion resumption passed live through map return.
Parent responses now identify protocol `generic_event_v10` over the existing v7
routes. The `events` mode stops at its reported `destination`; combat entry alone
is not a completed fight. See [event combat](../../docs/GENERIC_EVENTS.md#implemented-offline-non-resuming-event-combat)
and [resumption semantics](../../docs/GENERIC_EVENTS.md#implemented-offline-event-combat-resumption).

`/probe/v0/public/screen` recognizes only main menu/settings; its unsupported
result during a run is not a map diagnostic. Use the map decision route above.
The event summary's final `effects: unverified` describes its latest parent action
(usually Proceed); cumulative `completed_card_children`/`completed_item_children`
retain verified child completions. [Generic event semantics](../../docs/GENERIC_EVENTS.md)
explain the distinction.

Normal quit and stopped/closed-listener checks precede cleanup. Use the same
operational command with `--mode quarantine`, then `--mode purge`, each with
`--expected-state-sha256` from the preceding owned state. Preserve the release
source/package bindings until its installed campaign is closed. Cleanup verifies
exact ownership, state lineage and unchanged base files.

The unified bridge has a [representative live module smoke](../../docs/evidence/UNIFIED_BRIDGE_SMOKE_2026_09_08.md):
combat/rewards/map/shop, Smith/card selection, singleton potion collection and a
generic transformation event. Combat needed one UI-assisted chooser; console/UI
fixtures supplied later setups. The generic final effect summary and legacy
screen coverage retain documented limits. This is not an autonomous full-run result.
The earlier controlled V10 card16 result remains the specific off-screen evidence.

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

## Trial abandonment popup

The event client supports Trial Reject → Double Down via an owned
`abandon_confirmation_v1` child. `--abandon-policy cancel` is the default;
`--abandon-policy confirm` explicitly ends the run. `--capability events` reports
`destination: run_abandoned` only after the exact native task completes and the
terminal state is verified. Map stages still require a map handoff. Parent wire
protocol is `generic_event_v10`, with unchanged route names. This feature has
offline validation; no live abandonment test has been performed. See the
[contract](../../docs/GENERIC_EVENTS.md#implemented-offline-trial-abandonment-confirmation).
