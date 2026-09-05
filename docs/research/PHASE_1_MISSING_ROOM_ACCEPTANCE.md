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
A live successor needs reviewed routing/wire/host integration, build/surface/
package gates and a concrete campaign. Full potion inventory, item replacement
or skip, mixed gold/card reward screens, parent event continuation/completion,
and shop mutations remain unsupported. The historical room timeout is still
unclassified; this packet makes no causal claim about it. Normal cleanup and
the user's waiver of repeated unmodded launches remain unchanged.
