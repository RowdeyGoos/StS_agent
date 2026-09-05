# Item V1 release and live-readiness plan

- Date: 2026-09-05; baseline c5d6ab9 in the selected 23cf integration checkout.
- State: implemented, independently accepted and source-frozen; one live potion collection passed and cleanup completed.
- Outcome: finish the bounded item release, operational tools and preflight so a fresh item reward can be tested.

The user's standing authorization for bounded live campaigns persists. This plan adds no game capability: one first-legal item action through the frozen host, with no retry or adoption after uncertainty. Preserve every byte of old 0.8.0 and all four frozen successor trees. No profile/save filesystem access, Cloud change, target method discovery, retained live corpus, remote Git, old uncertain-action replay or browser-policy bypass. User-assisted launch remains available. The repeated unmodded launch/quit check is waived by the user; never report it as passed.

## Ownership and dependencies

New sibling: bridge/Sts2AgentBridge/successors/item_release_v1. Lane A owns verifier/, verifier_tests/ and policy/. Lane B owns operations/ (manager, synthetic fault fixtures, package helper, base/runtime companions). Coordinator owns package/, client/, client_tests/, Directory.Build.props, check.py, source_identity.json and documentation. Reviewer edits no implementation. Existing agents are reused. Contract acceptance precedes implementation. Policy extraction from the already accepted candidate is a separate read-only audit output, reviewed and hash-frozen before release acceptance; the shipping verifier never learns or emits policy.

All paths, package identities and fixed APIs below are shared contracts. Owners can choose internal implementation details without reopening the contract. Integration must run actual code and negative fixtures, then independent review. No packet completion is an excuse to stop before live-readiness.

## Immutable release identity

Candidate Sts2AgentBridgeItemV1.dll: 95232 bytes, SHA256 09ea93cd86a4ca502c27357171f7a7efdaf2bcf91a0a3fcffec96ef79745b9f6. Its exact 24 source-link projection has SHA256 131404a87a94800c1e9dbda3ef936abf44452befb5f41643b8b392cf6909ba88. The fourth source inventory remains a07c2fc58dad78655629f7cd1686a6b9ad108e996e728e80cf2f999733ab602e, manifest SHA256 77aa278f7c7c2cba2523c5c4d474fb2f45eb76dfa3d1faa7feb914a96e4c47ab.

Canonical manifest Sts2AgentBridgeItemV1.json is UTF-8, two-space indentation, these keys in this order, LF after every line including final closing brace:

```json
{
  "id": "Sts2AgentBridgeItemV1",
  "name": "STS2 Agent Bridge Item V1",
  "author": "StS Agent Project",
  "description": "Restricted one-action item collection bridge for StS agent research",
  "version": "1.0.0",
  "has_pck": false,
  "has_dll": true,
  "dependencies": [],
  "affects_gameplay": true,
  "min_game_version": "0.107.1"
}
```

Manifest 340 bytes SHA256 03163de389a7212c39f18c54ace292b8b105e3c7396bf08c871203f6c33978d4. ZIP Sts2AgentBridgeItemV1-1.0.0.zip is exactly 95936 bytes SHA256 349c24fa02da4a11e19fa4dd6a08100b805d9c5dbe84b89cd4e3de120a412beb. Exactly two stored entries, DLL then JSON, under Sts2AgentBridgeItemV1/. Timestamp 1980-01-01 00:00:00, create_system3, external_attr=(S_IFREG|0644)<<16, no extra/comment/directory entries/Zip64. No PDB, PCK or dependency assembly. Release artifact root is fixed /private/tmp/sts-item-v1-release. Require a new empty owned root when publishing verified artifacts; never overwrite/adopt an uncertain release output. Verification binds bytes, layout, metadata and no linked inputs.

## Whole-assembly verifier

Framework-only net9 metadata program using PEReader, never loading or resolving candidate or target assemblies. Verify only; no policy generation/update/override mode. Bind candidate identity, exact source closure and a complete reviewed policy projection. Default deny unknown or changed assembly references, type/member/signature/specification/definition rows, attributes, interfaces, generics, method implementations, native imports, resources/files/exported types/FieldRVA, user strings and raw initialized data. Bind each method body's header, locals, opcodes/operands, branches and exception regions. Reject unsupported structures; exact body/metadata digests are acceptable when accompanied by decoded inventories and sensitive semantic checks. Final exact artifact hash is mandatory, not a substitute for semantic tests.

Only the two frozen item routes. Exactly the 13 read-only native imports, owner, signatures, module, Cdecl and SetLastError metadata from the bootstrap contract. Preserve the two inherited internal StartForTests overloads but permit only the one-argument-to-two-argument edge. No other incoming call, delegate or token exposure to either; IsAllowedTestEndpoint must have zero incoming references. Both are nonvirtual/internal and absent from callbacks/entrypoints. Reflection/dynamic invocation that could defeat this finite incoming-reference proof is forbidden. This proves absence of candidate-origin entry to these methods, not resistance to an external in-process attacker. Public frozen API and callback roots are enumerated and bound.

Exact copies of MetadataNames.cs and IlDecoder.cs may be used, with hashes f7b481088f436e9ada05fc269101cd98b05326122798ff6043eeab8286517d23 and 58a15d83f6b97916ab5f63b2b765f29cd8d46e380d5a270bf8c91dd333d25933. Do not reuse the old production policy or alter any frozen source. Synthetic tests can compile verifier source with test-only expected identity inputs, so mutations exercise semantic categories before the final artifact pin; no such override in release CLI. Test changed metadata/body/refs/native flags/routes/test-method reachability/source missing/extra/link/hash and malformed PE. Production must reject all mutations as well.

## Transactional operations

Copy and narrowly rebind the accepted old manager, its actual synthetic fault fixtures, tool_common package helpers, clean-install and runtime checks into operations/. Never import mutable old tools. Keep the accepted fixed UID501 and OS-account home equality check, command modes install/quarantine/purge and durable predecessor-hash transitions. No arm/disarm, recovery, repair, adoption or generic new transition. Installation writes the exact enabled config only inside the explicitly authorized campaign, then publishes the verified code last. Missing/disabled/invalid config remains inert in production; no standing enabled installation is created.

Campaign ID ITEM-V1-COLLECTION-SMOKE-V1. State-root name Sts2AgentBridgeCampaign-item-v1-collection-smoke-v1. Operator tree Library/Application Support/Sts2AgentBridge/item_v1, exactly config.json and credential.hex. Config is exactly 139 bytes, no newline: {"schema_version":"item_probe_v1_transport_config_v1","enabled":true,"bind_address":"127.0.0.1","port":43117,"token_file":"credential.hex"}; SHA256 240f57a37801fd13dedb4cc823163a50a9745fc8053f23318614d995749570b8. Fresh credential is exactly64 lower-hex ASCII bytes. Overlay is Contents/MacOS/mods/Sts2AgentBridgeItemV1 containing only the exact DLL and JSON. Artifacts are the three fixed files above at the fixed release root.

Require the whole operator parent absent before install, plus absent new overlay/state, stopped game, closed43117 and the accepted clean base projection. Existing old r0a/config/overlay or foreign objects are a stop boundary, never co-installed, adopted, moved or deleted. Preserve code-first quarantine, exact owned generated-file purge, inode/device binding, exclusive publication, durable state generations and conservative failure outputs. The manager owns a newly created whole operator wrapper only because absence is required. Keep all existing fault checkpoints and add item identity/path/old-schema/wrong-package controls. ACL traversal must be bounded and reject allow/unknown/error while permitting deny-only; no unbounded or permissive unknown-tag loop. Recheck mutations and cleanup outcomes, never reinterpret uncertainty as success.

Base verifier keeps the accepted 429-file projection d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0 and target manifest identity. Overlay mode accepts only the new exact pair. Runtime checks retain the fixed game executable/UID and port; closed/listening alone does not identify code or process ownership, so combine with overlay/base and process checks. No profile/save enumeration.

## Fixed live client

client/run_live.py production CLI accepts exactly --expected-state-sha256 <64lowerhex>; no path, port, credential, item, retry or output-location option. Resolve UID501 home from OS account, use only the fixed installed campaign state/operator/overlay identities, and fail closed before credential transfer unless durable installed state and exact owned files match the supplied predecessor identity. Reuse the new manager's read-only state/identity validation through an explicitly exposed function; it must not mutate any state or invoke any install/cleanup operation.

Secure credential read uses retained no-follow descriptors and parent-name binding for the fixed chain, same owner/mode/type/link/ACL/stability requirements as bootstrap, exact enabled config and exact64 mutable lower-hex credential. Read using mutable buffers with no credential string/hash/log. Release the whole read lease and check all cleanup results before calling frozen item_transport_v1.transport.run_authenticated_collection exactly once. That function owns/zeros the transferred bytearray; client also zeroes on every pre-transfer failure. Fixed frozen transport and host imports only, verified source identities. No controller wrapping that retries, adopts or changes the action. Emit only the frozen controller's bounded sanitized success/failure summary; client preflight failure uses schema_version1/status failed/code item_client_preflight_failed. No decision/body/nonce/item-key/path/credential output. Keyboard interrupt emits only interrupted and zeros owned buffers.

Client tests use new owned synthetic roots and injected facts/syscalls, never actual home or production43117. Exercise descriptor replacement, links/modes/ACLs/old config/wrong state/read mutation/close failure/zeroing/no invocation on failure/exact single transfer plus the frozen host's success and uncertain failure through disposable ephemeral loopback. Test-only root/socket overrides are absent from production CLI.

## Integration and live readiness

Coordinator checker inventories this new tree and all four frozen predecessors/old48, verifies source links and project closure before build, uses pinned SDK9.0.303 with isolated offline restore and the two accepted target compile references only. Snapshot into fresh physical /private/tmp; no target execution. Run verifier positives/negative fixtures, manager full synthetic fault suite, client tests, package mutation fixtures, reproduce canonical artifacts and compare exact identities. Run relevant Python regression suite, syntax and documentation links. Independent review covers implementation, extracted policy, mutation effectiveness and cleanup fixtures. Freeze new inventory only after accepted results; rebuild final outputs from frozen inputs.

After these pass, read-only operational preflight checks supported capture/process state, stopped game/closed port, clean exact base, source/package identities and absence of operator/overlay/campaign conflicts. The first operational write starts a maximum30-minute campaign including teardown. Install exact package transactionally, ask user to launch manually on Profile3 and show a fresh untouched item-only reward screen (no mixed card reward or previously attempted item); leave reward offers visible. If potion is the first legal/only offer, require an empty potion slot. The frozen host selects first legal action; user must not click an offer. Ask for screen setup only after tooling and installation are ready, with precise state instructions. Verify supported screenshot and runtime/build/overlay preconditions, then at most one client invocation. An uncertain result ends action testing, never a retry or adoption.

Retain only sanitized bounded acceptance summary and necessary artifact/state identity records, no live corpus. Quit normally using supported UI, wait for stopped game and closed port, quarantine code first, purge exact owned campaign objects, verify clean base/stopped/closed. Honor the waived unmodded relaunch check. If the user is unavailable or the exact fresh screen is unavailable, stop at ready with actionable setup instructions and perform required cleanup before the deadline; do not leave an active installation indefinitely. Report evidence as live only after the one actual accepted summary; package/fixture success is readiness, not live item success.

## Contract acceptance

Independent review accepted semantic SHA256 9d7d25840fb8910448bd0f8215f4eabdc081c8151a96eb3649f4db3025103b34 before implementation. Only the status line and appended acceptance/evidence notes change after that freeze. The client source-manifest check detects drift; final operational preflight separately binds the externally recorded release manifest and tool hashes. It is not a self-authenticating trust root.

## Release disposition

The [acceptance ledger](research/PHASE_1_MISSING_ROOM_ACCEPTANCE.md) records the final 26-input inventory, exact policy and package, independent reproduction, 31 verifier/10 CLI/11 client/5 package/38 manager/17 runtime checks, 1155 Python regression tests and the independently reviewed two-file preflight startup correction. All four predecessor trees remain frozen. The release is ready for the bounded live campaign; no live collection result follows from these gates.

The bounded campaign subsequently passed exactly one potion collection and fully cleaned up by2026-09-05 18:34:28 UTC; the ledger records the sanitized summary and exact cleanup. The release readiness gates alone did not establish that live result. Relic collection and parent room completion remain unpromoted.
