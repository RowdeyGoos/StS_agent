# Shop and event implementation increment

Date: 2026-09-05. Baseline: `bfb0170` in the selected 23cf checkout on
`codex/phase1-actor-ready-integration`. Status: active implementation increment;
actual modules, wire, hosts and the aggregate functional gate are independently accepted.

The user explicitly selected actual shop and event development and asked for
parallel work. The earlier proposals are inputs, not completed capabilities.
This increment must deliver working code, independent fixtures and integration
for both lanes. Track code, fixture, package and live status separately.

## Outcomes and ownership

Use one new `bridge/Sts2AgentBridge/successors/room_flows_v1` tree. Preserve
old 0.8.0 and every byte of all five frozen item successor trees. Use exact
source links to accepted reusable components; do not duplicate an item release
stack for each feature. A single combined release follows actual module and
host integration. No live campaign is active.

| Owner | Exclusive files | Outcome |
| --- | --- | --- |
| Shop lane A | `room_flows_v1/shop/{core,native,tests}` | Already-open shop, zero or one affordable ordinary-card purchase, explicit inventory close, explicit room leave. |
| Event lane B | `room_flows_v1/event/{core,native,tests}` | Rendered options, bounded changed-choice continuation, one item child, retained parent revalidation, explicit synthetic Proceed exit. |
| Coordinator | Common interfaces, wire/routes, Python hosts, integration fixtures/checker, composite runtime and later release; all shared docs | One coherent, tested integration with accepted item reuse. |
| Reviewer R | None | Independent contract, implementation and aggregate acceptance. |

Writers use the shared selected checkout with strictly disjoint paths. No broad
formatting, staging or commits; coordinator integrates only reviewed files.
Contracts precede consumers; the first read-only tasks identify exact native
selectors. Activate writers immediately after their factual and interface
dependencies pass. Shop does not wait for the event child implementation.

## Bounded static follow-up

The current development instruction authorizes necessary read-only target API
verification and isolated implementation; no new user confirmation is required.
Use only manifest-pinned arm64 `sts2.dll` and `GodotSharp.dll`, respectively
SHA256 `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`
and `0e4897ecdfb31456a97c7d8028dfb8d7dbdc632e2f73fc9b438d7b266a139289`.
Verify the bounded byte image before PEReader metadata parsing. Reuse the
previous reviewed inspector source; build it offline with SDK 9.0.303 in a new
physical `/private/tmp` directory, with certificate generation suppressed.
Never execute or load target assemblies as code.

Freeze exact selected type/method names before each inspection. At most 60
types and 160 actual method bodies across this follow-up, including generated
bodies and overloads. Allow only direct dependencies needed for shop native
control wiring, rendered price/deck reconciliation, event rendered text,
synthetic Proceed construction and map transition. Prior disposable outputs
may be reread only after their recorded hashes pass. Do not expand into save,
profile, Cloud, seed, history, platform identity, unrelated content or networking
implementations. Encountered excluded callees remain stopped dependencies.

Commit only sanitized signatures, behavior facts, source/selection/output
hashes and test evidence. Raw target IL remains disposable. No game operation,
endpoint or credential read, operator/config write, retained live corpus,
uncertain-action replay, remote Git or broader capability occurs in this gate.
Native adapters may compile against exact pinned references; pure fixtures use
in-memory bindings and never initialize Godot or execute game assemblies.

## Shared behavioral boundaries

The coordinator freezes exact discriminated shop/event observations and
correlated action receipts/results before consumers are written. Actor-visible
text is bounded transient input, never retained in summaries or a corpus.
Native object references stay private. Host exchange counts are separate from
producer reservation budgets. Reserve before dispatch; no retry, adoption or
new mutation after uncertainty. Immediate recapture must match public facts
and retained native bindings. Pending effects are checked before foreground
classification. Rendering disappearance alone proves no acquisition or exit.

Shop purchases reconcile exact card acquisition and gold debit with native
stock disposition; card removal and potion/relic purchases stay outside this
first slice. Closing inventory and leaving are distinct actions. Event changed
choices preserve permanent structural ABA reservations; text-only changes and
item completion never renew a reserved option. There is no fabricated event
step ordinal. A single typed controller-owned item continuation must bind the
same run/player/event parent and use the actual frozen item service/result;
it makes no target-authored causal claim. Parent exit requires a separately
verified exact synthetic Proceed prestate and its action-bound map transition.

## Acceptance and live readiness

Run real module state machines with stale bindings, async ordering, ABA,
duplicate/reentrant/throwing actions, item uncertainty, cap and boundary cases.
Compile the actual native adapters against pinned game references. Exercise
actual C# service bytes through strict Python hosts, including the frozen item
child service and host. Test route isolation and shared deadline/action
accounting. Preserve every predecessor source identity and run appropriate
regression once the combined code settles.

Independent review is required before integration. One composite transport,
bootstrap/package and transactional cleanup path follows accepted functional
integration; live readiness requires their actual checks, not module fixtures
alone. Only then give the user the precise shop/event screen to prepare. Normal
bounded campaign cleanup remains required; repeated unmodded relaunch is waived.

After the event subtree was accepted and frozen, its writer took only the
coordinator-delegated room_flows_v1/check.py task. Shared docs, manifest freeze
and aggregate acceptance remain coordinator-owned. See the
[functional acceptance ledger](research/PHASE_1_ROOM_FLOWS_V1_ACCEPTANCE.md).
