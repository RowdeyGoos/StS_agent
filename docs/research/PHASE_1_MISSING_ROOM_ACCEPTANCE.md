# Missing-room capability acceptance

- Date: 2026-09-05; selected checkout 23cf, branch `codex/phase1-actor-ready-integration`.
- Previous live cleanup remains complete (2026-09-05 12:20:50 UTC). No campaign is active.
- User requested parallel shop/item/event development and instructed the coordinator to proceed.

| Packet | State | Evidence and boundary |
| --- | --- | --- |
| Three recovered proposals | Integrated design input | Shop `e411e0a`, item/event corrections `ea2d675`; specifications, not executable or live evidence. |
| MR-API-01 static discovery | Accepted static evidence | Scope `951620a`; pinned images; 47 selected types/102 actual bodies; independent item/event/shop audits; exact signatures/output hashes retained, no game code execution. |
| MR-ITEM-V1 contract | Frozen | Independent acceptance of semantic body `f955712311994dba6055dd473b8200dc6ca122dddcfb0baf223c0f7312b76869`; precise pre-dispatch binding, retained item-local reconciliation, one reservation, permanent failures, explicit read cap. |
| MR-ITEM-V1 implementation | Accepted for isolated integration | Ten pure-core fixture groups pass; independent aggregate review accepted the source-bound tree; two fresh builds match; native adapter compile-only; no old artifact or live route change. |
| MR-ITEM-WIRE-V1 | Accepted offline integration | Frozen service/host protocol; 9 producer groups, 27 host tests and 17 actual cross-language cases; two source-snapshot builds match; no listener/bootstrap/live package. |
| Shop actions / event progression | Unfrozen | Shop signal/back/FTUE seams and generic lineage-bound event progression remain explicit missing facts. |
| Live successor | Unselected | Requires complete routing/version/surface/package/reproducibility and concrete campaign gates. |

## Current validation

Static item/event/shop findings are in [the result](PHASE_1_MISSING_ROOM_API_RESULT.md)
and [exact selection record](PHASE_1_MISSING_ROOM_API_SELECTION.json). The
[contract](../PHASE_1_ITEM_V1_CONTRACT.md) preserves existing 0.8.0 source,
wire, vectors, outputs, policy and package. Existing Python regression: **1,112 passed in 111.67 seconds**; compileall of
`game` and `tests` passed with bytecode redirected to disposable scratch.
Old bridge source/solution/contracts/tests/package and host source have no diff
against `951620a`. All 56 checked document links resolve. The 132 output hashes
and 47/102 exact selections verify.

Independent aggregate review accepted result SHA-256
`b81bd4c00d32482f3f9cd86547acd8293ec0d2beeb807532426907c107f1487b`,
selection `378f2e1f059d3b99924c18f1382b5843256aedc0f56dcec0e7f6c3eee6c3d9f5`,
and corrected shop proposal `cd49eae53760bdaa3105fcca003798774f0218da0b86509c88c6afd8d9ec70f5`.
Item executable results and independent implementation review are complete below.

## MR-ITEM-V1 executable and integration result

Implemented only under [`successors/item_v1`](../../bridge/Sts2AgentBridge/successors/item_v1).
The pure core owns immutable public observations, canonical snapshot hashes,
exact native-index action mapping, immediate public/reference revalidation,
one reservation installed before dispatch, and retained reward-local
reconciliation. It rejects uncertain dispatch without retry and permanently
latches failed reconciliation. The native adapter projects a topmost item-only
reward screen and invokes its existing ForceClick control; it never runs as part
of this gate. No bridge registration, route, configuration, host consumer,
installation or package entry was added.

Independent review corrected the compressed eligible-action mapping, complete
validation exception boundaries, inconsistent claim facts, bounded native
inventory copying, unknown/map/context guards, and two fixture construction
errors. The final review found no remaining blocker. Ten fixture groups execute
the actual core session with in-memory captures/delegates, covering public hash
sensitivity and immutability; native indices and duplicate keys; full-belt false
claims; exact slot/reference/capacity changes; stale inputs; mixed unsupported
rewards; asynchronous collection and closed overlays; one reservation and
reentrant/uncertain no-retry behavior; exact read-256 completion/expiration;
retained identity changes; malformed captures; and fixed output/canary checks.
These are **synthetic component evidence**, not live or differential evidence.

Both implementer and coordinator ran the exact offline checker from fresh
disposable directories. Each returned:

```json
{"schema_version":1,"status":"passed","suite":"item_v1_offline","core_check_count":10,"native_adapter":"compile_only","sdk_version":"9.0.303","source_manifest_sha256":"3b37c6646fce5ad076703829ffd91f8a4d03e51083431727b517b51af8ce9a99"}
```

The checker verifies the source inventory, exact SDK version and exact target
DLL sizes/hashes, opens references without following symlinks or blocking on
nonregular files, and compiles only from bounded verified byte copies in
private temporary storage. It clears package sources and isolates CLI/package
and artifact paths. It verifies the test dependency list excludes Native, sts2
and GodotSharp before executing the pure test program, then separately compiles
the adapter. Both projects compiled with zero warnings/errors. No target or
native adapter assembly executed. Eleven additional coordinator checks used
only temporary mock files to exercise scratch containment, traversal/symlink
rejection, nonregular FIFO rejection, exact size/hash checks and valid input.

The final source JSON SHA-256 is
`435219714fa6e667738685f9909396839c46c21612a50bc84a0fc58e584c938a`;
its canonical ten-input listing digest is the value in the checker result.
The independent aggregate reviewer verified its exact inventory and every
file hash, explicit project compile lists, standalone build properties,
absence of bootstrap/initializers/dynamic loading, and pure test dependency
boundary. The coordinator's fresh invocation satisfied the review's final gate.

Two fresh build directories produced byte-identical assemblies:

| Assembly | SHA-256 |
| --- | --- |
| ItemV1.Core | `2ef7d77e53204857f83b2a55dbd265856af0ec012c3614f59faa26183f04912f` |
| ItemV1.Tests | `d1b9305b695ba1cf37f551d326f356d75559f15ca03bea6dc2c037c54b1e4eda` |
| ItemV1.Native | `61107f7d2762234dab6fabf7307a6b4ee9f3fa689462505a34eca4ad241e5515` |

This is reproducibility of these isolated assemblies, not acceptance of a new
live bridge package. The old 0.8.0 source inventory remains 48 files with SHA-256
`a0ca37bb2d0ad36fcb68eafe5163ac8174074b0e6f861c69c2ac357873f75f2a`,
matching the frozen differential fixture identity. Existing regression remains
**1,112 passed in 111.67 seconds**, plus successful Python compileall; the new
C# groups are reported separately. No existing Python/bridge source or tests
changed after that regression run.

### Reproducing the offline gate

Use the existing approved SDK and the exact pinned arm64 game-data directory;
choose an unused scratch directory beneath `/private/tmp` (the checker refuses
an existing directory). For example, from the selected integration checkout:

```bash
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/successors/item_v1/check.py \
  --dotnet /private/tmp/sts-sdk-resume.6AJGPQ/sdk/dotnet \
  --game-data-dir '/Users/rowdeygoos/Library/Application Support/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.app/Contents/Resources/data_sts2_macos_arm64' \
  --scratch /private/tmp/item-v1-review-001
```

### Remaining gates

Item V1 is unselected and cannot be reached through the current live bridge.
The service/wire/programmatic-host gate is now complete below. A live successor
still needs reviewed authenticated transport, configuration, frame dispatch,
bootstrap/surface/package gates and a concrete campaign. Full potion inventory, item replacement
or skip, mixed gold/card reward screens, parent event continuation/completion,
and shop mutations remain unsupported. The historical room timeout is still
unclassified; this packet makes no causal claim about it. Normal cleanup and
the user's waiver of repeated unmodded launches remain unchanged.


## 2026-09-05 — MR-ITEM-WIRE-V1 accepted offline integration

The user requested continued development and testing. The coordinator froze
[the wire/host packet](../PHASE_1_ITEM_V1_WIRE_PLAN.md) at semantic SHA-256
`e138680c587914bc0ded9734bdd48cbcbb7b55354117c407953b12cf6edd1df1`.
Implementation is isolated under
[`successors/item_wire_v1`](../../bridge/Sts2AgentBridge/successors/item_wire_v1),
based on integration commit `638bd70`. The commit containing this record owns
this integration wave. The accepted `item_v1` tree and old 0.8.0 inputs are
byte-identical; no existing contract, vector, host, package or default changed.

The C# application service owns one real item session and explicitly serializes
bounded canonical `item_probe_v1` responses. The Python controller consumes only
an injected mutable-body exchange, independently checks decision digests and
receipt/result correlation, makes at most one action attempt, and reports
collection only after its exact accepted receipt and reconciled result. One
15-second deadline and 256 total reads cover the entire invocation. All owned
response buffers are zeroed, including late-response and cancellation exits.
Neither component creates a live listener, discovers credentials or launches
or loads the game.

Independent review corrected and verified:

- readiness on the last permitted read now stops before POST, because no
  reconciliation read remains;
- one syntactically valid POST reserves the service attempt before core access,
  so a rejected candidate cannot be retried with a later candidate;
- receipt validation retains the pre-dispatch context across synchronous
  reentrant reads, and internal projection failures remain terminal;
- the fixture's exceptional decode/append paths zero their owned buffers and
  stdin-close failures still reap the child;
- the offline checker verifies the old bridge inventory directly and requires
  exact producer, host and cross-language summaries.

All final implementation and coordinator files passed independent review. The
producer writer and a separate reviewer ran the actual C# service/core tests.
The coordinator and independent aggregate reviewer then ran the exact checker
from two fresh verified source copies, `/private/tmp/item-wire-coordinator-a`
and `/private/tmp/item-wire-independent-b`. Both returned producer **9 groups**,
host **27 tests**, and **17 cross-language cases** across eight synthetic
scenarios. Those cases execute the actual C# core/service, send its serialized
bytes through the actual Python controller, and assert native action indices
and dispatch counts. They cover potion/relic success, delayed readiness and
reconciliation, closed overlays, full belts, stale state, uncertain clicks,
corrupted bodies/receipts, late/lost receipts, and rejection of a resolved
result by a second controller. Literal synthetic vectors cover potion, relic
and maximum-size ready/accepted/resolved exchanges. The largest fixture body
is **2,890 bytes**; even an overestimating combination of longest field values
is **2,906 bytes**, below the 4,096-byte cap.

The checker takes no game input. It snapshots bounded verified source bytes,
uses the exact SDK 9.0.303, clears package sources, disables NuGet auditing and
parallel/shared build processes, and isolates CLI/package/artifact paths. It
checks the dependency list contains only Core, Wire and Wire.Tests before
execution. An empty scratch directory supplies the unchanged core's optional
PathMap value; no native or game assembly is referenced or executed. Twelve
coordinator mock-only source/scratch checks and three independent fixture
cleanup probes passed. The old 48-file inventory and accepted 10-input item
inventory match their existing pins in both fresh checker runs.

Exact new identities:

| Input or assembly | SHA-256 |
| --- | --- |
| Fourteen-input canonical source inventory | `4769c86b2270df0e540c8eb48f535847dc4848dd6b4fe4017b9214459d38bfa7` |
| source_identity.json | `c930337e74b4eed9f41ba00e804a950a7334a33a96ded7531361312bf5115c10` |
| Literal synthetic vectors | `e1b73c958eb5537941e8405ad0eb237899e1c675f2df96b61c720d090e298018` |
| Core rebuilt in this source-snapshot gate | `c959b997e881de37fba1ae7eff8a185f5e7f95c3fe09c2adf00c51291adff683` |
| Wire | `bb22f7bccbfd6cabb799d1783206fd8a6ddc5441bf2df29ae7a1767d0f737948` |
| Wire.Tests | `e3be6aef1dd731f0a633a56a9c7d655fc449cd338ee6d64a9a2aaf3eda18a8d9` |

All three assemblies match byte-for-byte between the two fresh gates. These
are the new isolated build identities; no historical artifact is replaced.
The historical Core build included a Git-derived informational-version suffix;
the source snapshot has informational version `1.0.0`. Independent generated
assembly metadata comparison explains that hash difference without source drift.
Every authored source hash is recorded in the new manifest.

Full repository regression passed **1,139 tests in 107.74 seconds**, comprising
the prior 1,112 tests and 27 new host tests; the C# groups and cross-language
cases are counted separately. Python compileall passed with bytecode directed
to scratch. The subsequent producer/checker corrections were covered by both
final offline gates; existing Python and host sources did not change after the
full regression. No repeated broader test run is claimed.

To reproduce from the selected checkout, use Python 3.10+ and an unused physical
scratch path under `/private/tmp`:

```bash
/Users/rowdeygoos/code/github/RowdeyGoos/StS_agent/.venv/bin/python -B -I -S \
  bridge/Sts2AgentBridge/successors/item_wire_v1/check.py \
  --dotnet /private/tmp/sts-sdk-resume.6AJGPQ/sdk/dotnet \
  --scratch /private/tmp/item-wire-review-001
```

Evidence is **synthetic component and cross-language integration**, with no
live or differential promotion. The next item gate is separate default-disabled
authenticated transport/configuration and frame-thread composition, followed by
pinned bootstrap/surface/package/reproducibility and a concrete campaign.
Post-submission transport failures must remain terminal unknown mutation,
including a frame-queue timeout after work is claimed. Existing r0a credentials
or enabled configuration must not activate this successor. Shop controls,
full-belt replacement/skip, mixed rewards and parent event progression remain
unsupported. The historical timeout is unclassified. No game setup was needed,
no campaign ran, and the last cleanup and user waiver remain unchanged. No
profile/save/Cloud access, retained live corpus, remote Git or model escalation
occurred.
