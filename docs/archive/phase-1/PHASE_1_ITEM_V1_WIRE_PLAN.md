# Item V1 wire and host integration packet

- Date: 2026-09-05. Baseline `638bd70`, selected 23cf checkout.
- State: independently frozen for implementation.
- Authority: the user requested continued development and testing after the isolated item implementation. This packet implements the next repository integration boundary. No additional user approval is required for the described reversible repository/fixture work.

## Outcome and preserved boundaries

Connect the accepted item core to a strict Python controller through a versioned serialized protocol. Execute a real core -> C# producer -> byte response -> Python parser/controller exchange with synthetic public surfaces. Preserve every byte under the accepted `successors/item_v1` tree and old 0.8.0 source/wire/host/defaults. New implementation belongs in sibling `bridge/Sts2AgentBridge/successors/item_wire_v1`, with explicit projects and its own identity. Existing build inputs may be referenced only as exact hash-bound inputs; never edit or regenerate their pins.

This is a protocol/application-service and programmatic host packet. It does not add a listener, configuration loader, ModEntry, game bootstrap, live CLI/credential discovery, installer or package. No target inspection/assembly execution, live action, profile/save/Cloud access, retained live corpus or remote Git. Future authentication, bounded HTTP parser/listener, Godot frame dispatcher, pinned bootstrap/surface/package and campaign composition remain explicit gates, not implied by application-service fixtures. Future runtime uses a separate exact default-disabled configuration schema/path and credential scope; it must never inherit enabled r0a configuration. Missing/disabled exposes no listener. The current frame queue can time out after claiming work while mutation continues: every non-success after action submission, or lost action response, is terminal/nonretryable unknown mutation. Never reuse v0 retryable backend_fault/mutation_state:none for that case.

## Frozen candidate protocol

- Protocol name `item_probe_v1`; schema_version integer 1; core version `item_v1`.
- Routes: GET `/probe/item-v1/public/item-decision`, POST `/probe/item-v1/public/item-action`. No reset/session-start route. No body for either. Action metadata carries exact decision_id and action_id; no nonce supplied by the actor. All other method/route combinations or unexpected/missing action metadata return fixed invalid_request without core access.
- The future runtime owns one service/core instance and fresh 32-lowercase-hex nonce per successor runtime activation (bootstrap start through teardown). A controller invocation never creates or replaces it. The service creates one core session in its constructor; reads and actions operate on that same instance. No replacement/factory on request, no action retry. Pure service calls must be marshalled to the Godot frame thread by future runtime composition; this packet executes only fake adapters.
- Every response is a canonical UTF-8 JSON object, no BOM/newline/whitespace, with member order below. Duplicate/unknown keys, wrong types (including bool as int), escaped spellings, non-ASCII values, noncanonical integers, reordered keys/arrays, excess bounds or a noncanonical whole encoding are rejected by the host. Body maximum 4096 bytes, checked by producer and consumer. Conservative grammar/caps are exactly the frozen item core's.
- Common prefix fields in order: `schema_version`, `protocol`, `version`, `session_nonce`, `surface_ordinal` (always 1), `status`.
- waiting/unsupported: common prefix only; status `waiting` or `unsupported`.
- ready: common prefix, then `decision_id`, `offers`, `potion_slots`, `legal_actions`. Offer fields in order: `index`, `kind`, `key`, `enabled`. Offers are sorted by native RewardsSetIndex; no renumbered slot. Kind is potion/relic. Potion slots preserve nulls/order/capacity. Legal actions are the exact advertised eligible subset in offer order, never empty for ready. Host validates producer invariants and independently recomputes the accepted core's canonical decision digest; it selects only advertised actions.
- accepted: common prefix with status `accepted`, then original `decision_id`, `action_id`. This is a dispatch receipt, not collection. Exact echoed correlation required.
- rejected/uncertain: common prefix only with that status. Core apply `unsupported` maps to common-prefix unsupported. Invalid actor input never enters response fields.
- resolved: common prefix with status `resolved`, then original `decision_id`, `action_id`, `offer_index`, `kind`, `key`, `result` (always `collected`). No ready fields/actions. Match every field to the original offered action and exact accepted receipt. A resolved result before this controller received its receipt is rejected, never adopted.
- application error: common prefix with status `error`, then `code` from `invalid_request` or `internal_failure`. Exceptions never enter output. Invalid service arguments return error/invalid_request before core access. Serializer or unknown core-result failure uses an independently safe fixed error/internal_failure encoder; it never recursively serializes the bad value and never retries or reconstructs a mutation.
- The producer has no reflection-based generic serialization. Explicitly project recognized immutable core outputs only and validate limits; serializing a result itself never touches native adapters.

## Host controller and uncertainty

Implement a programmatic one-collection controller with an injected body exchange callable `(method, route, decision_id, action_id, deadline) -> bytearray`, plus monotonic clock/sleep seams for fixtures. There is no default connector or filesystem/credential access in this packet. The transport caller will own authentication and credential lifetime in future composition.

Use one 15-second total deadline and 0.1-second waiting polls. Bound total read exchanges to 256 (pre and post combined); neither a new response nor accepted dispatch resets either bound. Check the shared deadline immediately before AND after every exchange, and before/after every sleep. Sleep at most the smaller of 0.1 seconds and remaining time. A late response cannot become accepted or reconciled. Count the sole action attempt at exchange entry; count acceptance only after validating its exact receipt; count reconciliation only after exact correlated resolved output. The default provider selects the first advertised legal action once. There is no phase scan, fallback, control-derived action, repeated action, or adoption after error. Waiting is the only state eligible for another read. Initial ready allows one action; after acceptance any ready/changed session/unrelated resolved is an error. Bind nonce from the first valid response, including waiting, and reject changes throughout.

Success output is exactly `{"schema_version":1,"status":"passed","milestone":"item_v1_collection","item_kind":"potion|relic","attempted":1,"accepted":1,"reconciled":1}` (kind is the actual fixed enum value). Failure output is exactly `{"schema_version":1,"status":"failed","code":C}` with a closed enum: `invalid_response`, `unsupported_state`, `action_rejected`, `action_uncertain`, `deadline_exceeded`, `read_limit_reached`, `transport_failure`, `internal_failure`. No partial acceptance, IDs, keys, raw bodies, native references, timing, exception text or state history is returned/logged. Suppress no needed errors silently: classify fixed failure, stop immediately, preserve the attempted/accepted distinction in fixture assertions. Keyboard/cancellation exceptions still trigger cleanup and then propagate without a success result.

A designated exchange transport exception maps to transport_failure; null/immutable/non-exact-bytearray responses and malformed/canonical/correlation failures map to invalid_response; a valid application error (either code) or unexpected ordinary controller exception maps to internal_failure. KeyboardInterrupt/SystemExit/GeneratorExit propagate after cleanup. The exchange callable owns and zeroes any buffer on its exceptional exits. Ownership transfers only when an exact bytearray returns; the controller then zeroes it on all paths, including malformed/error/late-response/cancellation exits. The host must not retain response histories. Decoded public values may exist transiently for validation/correlation only. The serialized success report above is the sole accepted persistent result.

## Ownership and executable acceptance

Coordinator owns this contract, shared status/decisions and integration. After freeze:

- C# lane owns only `item_wire_v1/producer` and its `producer_tests`, explicit pure projects and the protocol service/codec. It references unchanged item core, never native/game. Include a bounded synthetic stdio fixture endpoint for cross-language tests only, with literal scenario inputs and no native adapter or dynamic loading.
- Python lane owns only `item_wire_v1/host` and `host_tests`, stdlib only, Python 3.10+, explicit programmatic API and strict parser/serializer/digest/controller. Its executable tests require no ML imports, credentials, game or network.
- Coordinator owns `item_wire_v1/check.py`, `Directory.Build.props`, identity/vector inventories and cross-language joining. Reviewed literal vectors, maximum-size proof and exact source hashes precede final integration. Synthetic stdout bodies contain fixture values only and are not live corpus.

Required tests exercise actual new paths: potion/relic success, delayed readiness/reconciliation, closed-overlay retained result, full belt and unsupported mixed screen, pre-apply stale state, reserved replay/uncertain click, lost/rejected/mismatched receipt, unexpected ready or unsolicited resolved, session/correlation/key/index drift, fixed deadlines/read caps, exact byte/key/number/shape bounds, malformed/duplicate/private-canary payloads, null/non-buffer exchange failures, all cleanup exits and unchanged old/item-core identities. Cross-language fixtures must feed C# output from the real core into the real Python controller and verify actual action index/count. Add negative controls proving strict consumers reject mutated producer bytes rather than accepting both sides of the same bug. No extra tests after gates pass without a concrete new failure/change/concern.

## Freeze acceptance

Independent review accepted the semantic packet at SHA-256 `e138680c587914bc0ded9734bdd48cbcbb7b55354117c407953b12cf6edd1df1`. The status line and this record are the only subsequent changes. Producer and host ownership are activated as specified; no live gate is selected.


## Implementation disposition

This frozen packet is implemented and independently accepted. The
[missing-room acceptance ledger](research/PHASE_1_MISSING_ROOM_ACCEPTANCE.md)
records the 14-input source inventory, 9 producer groups, 27 host tests,
17 cross-language cases, full regression and two matching fresh builds.
Future live transport, configuration, frame dispatch, bootstrap, package and
campaign remain outside this packet.
