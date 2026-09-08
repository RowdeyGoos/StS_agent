# Generic event release v9 acceptance

2026-09-08. User requests fixing the v8 geometry diagnostic gap to continue
live testing. The contract is docs/PHASE_1_GENERIC_EVENT_RELEASE_V9_CONTRACT.md,
independently accepted at SHA256
`c74fb8dc3229c8f9b9e3153909b6416b85202bda6fd1d098bc716672d8c8a2ea`.
All30 predecessor inventories remain frozen; existing campaign is closed.

This increment adds37 finite stage codes, values78–114, preserving0–77 exactly.
It replaces only the derived transform adapter and the diagnostic enum/codec
within the56-source gameplay/release composition. No selection predicate is
relaxed and no raw/numeric geometry data or new target API is introduced.
The v8 actual failure cause is still unknown. Successful offline diagnostics
are not successful live off-screen selection.

## Focused preparation

Independent review accepted the exact contract, then reviewed the finite
transport delta and corresponding enum/codec vocabulary. Longest header word
is33 bytes; the bounded parser limit changes32 to33 while keeping the strict
allowlist and1024-byte whole-header limit. Exhaustive115-value coverage plus
34-byte extension, unknown, case and whitespace rejection pass23 transport tests.

Runtime fixtures pass966 assertions in
`/private/tmp/generic-release-v9-runtime-a/result.json`. Protected client fixtures
pass13 tests; conflict fixtures pass68 checks and transactional lifecycle/fault
fixtures pass41. Initial client fixture run found a stale v8 synthetic-directory
name; corrected only the v9 fixture and reran successfully. No live credential
or installation access occurred. These checks do not yet constitute aggregate
acceptance; native diagnostic coverage, policy, candidate/frozen gates and final
review remain pending.

## Native diagnostics, production and policy

Actual-adapter inert fixtures passed194 assertions, retaining all89 v8 probe
checks. Of37 added codes,28 are exercised through session admission; nine defensive
or retained-proof checks use the actual private helper in the inert test assembly.
That fixture-only reflection is absent from production. Coverage includes getter
exceptions, deterministic first-failure order, diagnostic reset, depth32 admission,
and the unchanged162 rectangle reads for one retained proof pass. Evidence:
`/private/tmp/generic-release-v9-native-a/result.json`.

Two production-only compilations are byte-identical390144-byte DLLs, SHA256
`e8c7856b29d2acee24e867b1f7c748e4bd9e83e189449c3b5b38e7b31aac75a3`;
`/private/tmp/generic-release-v9-production-candidate-a/result.json` records56
source identities. Source projection:
`10684a9161d0283c87c7ead6f3701d0b61ba722126bb35cd4494c129612c36d7`.
No production/game/Godot assembly executed during these checks.

Policies extracted separately from both copies match1664144 bytes, SHA256
`45cd4b72f93c99335e8618d3a3239761865861f3e1025b8381338efa19f964b3`.
They bind2150 method bodies and14907 metadata rows, metadata projection
`8649041101cb8d71d481d0d407f87725756087dc78d6ad17395151c9ec78f95b`.
Independent review verified all115 enum values/mappings, cached native accessor,
six diagnostic callsites and the same18 geometry helper/API callsites as v8.
No target member-reference API was added. Both production verifier runs and378
negative/semantic verifier checks pass; evidence in
`/private/tmp/generic-release-v9-verifier-a/` (verify-first/verify-second/mutations stdout).

Canonical package identities: manifest352 bytes SHA256
`c2df30bf27f9c381305f73893b77f5813a8b8c48fb257161b479cfda4bd31112`;
ZIP390924 bytes SHA256
`8f896d71770ec079ebc369980b1416e338fbfb1fce60143e813c9ce057604d8a`.
Artifacts are pinned in package/transactional code but not published or installed
at this checkpoint. Complete candidate and frozen acceptance follow next.

## Candidate acceptance and source freeze

Candidate-a stopped while compiling unchanged frozen G7 native code: SDK Roslyn
CSharpDetectPreviewFeatureAnalyzer raised AD0001 MissingMethodException for
CheckLangVersionForConstantValue. Evidence:
`/private/tmp/generic-release-v9-root-candidate-a-g7/log-012.txt`.
No source, compiler flag or dependency change followed. Fresh candidate-b passed
that compilation and every subsequent gate. This was an offline compiler
exception, not a card/input failure or an approval-review rejection.

Complete candidate result `/private/tmp/generic-release-v9-root-candidate-b/result.json`,
SHA256 `76c6e450fb6224bdee4d5b200e26bf444c54d86d9c9a24764d4eacf7baf93dea`,
passes194 native probe assertions,966 runtime,378 verifier,52 socket scenarios,
23 transport and13 protected client tests;4 operator,13 bootstrap and41 native
release checks;41 transactional,68 predecessor-conflict,17 runtime-boundary and7
clean-install fixtures;5 package checks/9 mutations and5 provenance mutations.
Socket additions cover actual-adapter scroll-height and transform rejection
through the authenticated header to Python, each with258 reads, one parent POST
and zero child/card input. Retained no-clip/no-eligible cases also carry precise
codes. All52 scenarios passed, including successful exact-original transformation
on inert targets, diagnostic reset, deferred changes and no uncertain retry.

Frozen G7 regressions separately pass3815 native,1718 item,2650 transform,
171 wire,118 host and201 integration checks (139 actual-native with inert targets).
These retain their predecessor scope; they are not additional v9 live evidence.
Candidate production pair matches the initial pair exactly.

Source frozen as successor31:73 owned files plus source_identity.json,
71 derived/49 reused/0 independently created provenance records. Inventory
`733316f29243300256be3fe1bc60330900a5f4d3048078d11480eeb1aeffcaa0`;
manifest SHA256 `53a6cc7186f13f12cb3a9f4d0437c85be99ed600b0162deca31f2deee8aebb2d`.
All30 predecessor inventories remain unchanged. Complete source-frozen aggregate
and final acceptance must pass before publishing/installing this campaign.

## Complete source-frozen acceptance and installed readiness

Full frozen result `/private/tmp/generic-release-v9-root-frozen-a/result.json`,
SHA256 `c019a320a38fe66cc5c0a3278361d57e1ef651dbbcd744e0edb159c6e1aae4af`,
passes the same complete matrix and additionally validates frozen client source
before credential access. The unchanged G7 compilation passed again; the earlier
compiler analyzer exception did not recur. All six production compilations
(initial pair, candidate pair, frozen pair) match390144 bytes/e8c7856b….
Independent final review rehashed every current file against both frozen
snapshots, all30 predecessor inventories, full contract and all six DLLs. No
remaining publication or installation blocker was found.

Fresh operational preflights passed: stopped game (three process samples), closed
port (two samples),429 unchanged base files/0 overlays with projection
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Root published exactly the three canonical artifacts to
`/private/tmp/sts-generic-event-v9-release`, then installed once through the
frozen transactional manager. No automatic game launch occurred.

Campaign GENERIC-EVENT-V9-SMOKE-V1, phase installed, mods_parent_created=true.
Fresh current installed-state SHA256:
`e64573ebd1733943a2454fd6cc5a72678eca3899ce84bb6ce51a0c5968e15711`.
State root:
`/Users/rowdeygoos/Library/Application Support/Sts2AgentBridgeCampaign-generic-event-v9-smoke-v1`.
Operator folder: Sts2AgentBridge/generic_event_v9; overlay: Sts2AgentBridgeGenericEventV9.
The manager generated fresh private credentials; the coordinator did not read
or expose their contents. Frozen client source and installed metadata validation
passed without reading credential contents.

Overlay verification passed429 unchanged base files and2 owned overlay files,
same base projection. Sanitized outputs:
`/private/tmp/generic-release-v9-install-result.json` and
`/private/tmp/generic-release-v9-overlay-verification.json`.
Preparation is complete; no live client invocation or game launch has occurred.

Tell the user to launch manually on Profile3, single-player, same window and
resolution, ordinary20-card deck, fresh Aroma of Chaos initial Let Go/Maintain
Control choices untouched, console/popups closed. Runtime geometry decides
eligibility; deck count alone is no guarantee. Wait for readiness, verify actual
UI and fresh require-running, then exactly one invocation:

```sh
/Users/rowdeygoos/code/github/RowdeyGoos/StS_agent/.venv/bin/python -B bridge/Sts2AgentBridge/successors/generic_event_release_v9/client/run_live.py --expected-state-sha256 e64573ebd1733943a2454fd6cc5a72678eca3899ce84bb6ce51a0c5968e15711
```

Run from the active23cf worktree with loopback permission. No uncertain retry,
manual child completion or prior-selector adoption. After the invocation, normal
UI quit, wait-stopped, code-first quarantine using this installed hash, then purge
using the newly returned quarantine hash, and final unchanged429-file clean-base/
0-overlay plus stopped/closed checks complete root-owned cleanup. Never reuse a
historical state hash. These cleanup steps remain pending for this installed
instance. Successful live off-screen selection remains pending.
