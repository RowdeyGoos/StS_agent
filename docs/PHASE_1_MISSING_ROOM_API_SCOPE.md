# Missing-room static API and first implementation gate

- Date: 2026-09-05
- Baseline: `ea2d675`, `codex/phase1-actor-ready-integration`, selected 23cf checkout.
- Authority: the user requested parallel shop/item/event development, reviewed
  proposal handoffs, then instructed the coordinator to proceed with exact
  game-API verification and shared-interface work. This scope makes that
  repository/static work concrete; no additional user approval is needed for
  these read-only checks or isolated repository implementation.
- Current phase: static fact discovery; production contract freeze follows
  independent review of the facts. The first candidate slice is direct item
  acquisition without parent continuation, full-inventory replacement or skip.

## Exact inputs and operations

Use only the pinned arm64 `sts2.dll` and `GodotSharp.dll` in the known game data
folder as immutable source/compile references. Verify SHA-256 before reading
metadata: respectively
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18` and
`0e4897ecdfb31456a97c7d8028dfb8d7dbdc632e2f73fc9b438d7b266a139289`.
The repository build manifest defines their exact install-relative paths.
Use the existing isolated .NET SDK and a disposable metadata inspector based on
repository `MetadataNames`/`IlDecoder`, with offline restore. It must use
`PEReader`/metadata inspection, never load target assemblies for execution,
invoke game methods or initialize Godot. No dependency download or remote Git.

First enumerate only type names relevant to item offers/inventory, merchant
controls, event option presentation/lifecycle and their existing public UI
bases. Then select exact types/members before reading signatures and IL.
Inspection is bounded to at most 80 selected types and 200 selected method
bodies, including generated bodies belonging to the selected methods. Follow
only direct callees necessary to establish control dispatch, public projection,
passivity, collection/debit ordering or completion. Do not expand into profiles,
saves, Cloud, seeds, history, platform identities or unrelated content. A call
into an excluded family is a stop for that dependency, not authority to follow it.

Keep raw metadata/IL only in disposable analysis output; commit source-backed
member/behavior summaries and hashes, not copied target method bodies or game
assets. This is static target-code evidence, never live or differential evidence.
Every actor field must be shown to represent current player-visible information
or an approved mapping from it; CLR-public access alone is insufficient.

## Parallel responsibilities

The coordinator owns the inspector, scope, shared-contract decisions and all
integration writes. Read-only lanes may independently audit item facts, event
facts and shop facts after exact type selections are available, or review the
shared compatibility surface from repository source while the inspector is
prepared. They return bounded findings; no lane changes contracts or controls
without a reviewed successor packet and exclusive ownership.

The API report must identify supported direct controls, rejected alternatives,
uncertain asynchronous transitions and precise absent witnesses. Static evidence
may reduce a proposal's scope. It may not invent a missing skip/replace/exit/step
control, infer action completion from screen disappearance, or treat a receipt
as a reconciled mutation.

## Next gate and fixed exclusions

After reviewed static findings, freeze the smallest useful item observation/
action/result contract and implement it with independent synthetic fixtures in
an isolated, unselected successor component. Preserve the current 0.8.0 artifact,
`live_probe_v0`, D47, all accepted host outputs and `headless_v0`. Any eventual
live-enabled successor requires its complete artifact/surface/reproducibility
and fixture gates and a concrete coordinator campaign within existing authority.
Do not silently load a new capability during discovery.

No game/UI operation, endpoint/credential access, installation/config write,
profile/save filesystem access, Steam Cloud change, retained live corpus,
uncertain-action retry/reconstruction, base-game mutation or remote Git occurs
under this static/repository gate. The previous cleanup remains complete; the
user's waiver of repeated unmodded cleanup launches remains controlling.

## Independent scope review clarifications

The inspector uses canonical manifest-bound paths, rejects symlink/reparse or
non-regular/over-100-MB inputs, reads one handle into a bounded memory image,
and verifies the pinned hash of that image before PE metadata parsing. The
name-only pass uses fixed item/event/shop namespace predicates and deterministic
ordering; no truncation is accepted. A frozen exact type/body list gates every
subsequent signature/IL selection. Generated state machines count toward both
caps and must be linked to a selected method by its metadata attribute or exact
declaring relationship; unrelated generated methods are excluded.

Record exact selected signatures and bounded behavioral conclusions in the
sanitized report; never commit IL, decompiled bodies, string dumps or game assets.
Direct callees outside the frozen family remain named stopped dependencies
until the coordinator explicitly selects and reviews the necessary narrow
extension. This is metadata-only execution: the inspector program may execute,
but target assemblies are never loaded as executable code.

Independent repository review found that the existing differential identity
hashes every C#/project file under `bridge/Sts2AgentBridge/src`, even uncompiled
files. Any first unselected successor therefore belongs under the separate
`bridge/Sts2AgentBridge/successors/item_v1` tree, with its own exact compile list,
assembly name, namespace, tests and source identity. Existing project/solution,
production source, bootstrap/routes, 0.8.0 tests, vectors, surface policy and
package remain byte-exact. Synthetic execution of the future successor requires
a recorded fixture gate after static review, with injected public surfaces and
no game/Godot initialization; it is not part of metadata discovery.
