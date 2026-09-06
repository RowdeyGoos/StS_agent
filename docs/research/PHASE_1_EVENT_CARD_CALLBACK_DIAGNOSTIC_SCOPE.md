# Phase 1 event card-callback diagnostic scope

- Date: 2026-09-06
- Status: proposed; synthetic gates pass; target not read by this packet
- Baseline: `920ec84`
- Preserved failed-scope bytes:
  `PHASE_1_EVENT_CARD_CALLBACK_ATTEMPT_2_SCOPE.md`, SHA-256
  `faca6e77b28471e2a83fce08bd14b388ad3d4a1419cdc3bf3c47026bb55ef5a4`
- Attempt 2 result SHA-256:
  `b1757b24a146d53df96a8ff49283ac18c8289ba193b53e61ce605057203046ce`

## Purpose

The second reviewed invocation stopped before emitting evidence because an
`EventOption` constructor segment did not satisfy the scanner's exact
key/callback binding rule. The fixed error does not establish which constructor
or whether it belonged to a selected callback. This diagnostic revision decouples bounded evidence
capture from semantic binding acceptance. It preserves complete selected,
initial-options, callback and removal-helper bodies even when one constructor
is unresolved. It does not turn any candidate into a production registry row.

The target, exact five selected source/state-machine bodies, ten caller-result
callsite rows, selected config SHA-256
`cfc57aa9ef8fc35b818e6d2b2ab1fddf384f84904ed6c4c19e30e1e9173e4589`,
accepted caller-result SHA-256
`c6340b67d61bd01f447bd4bad320e3ef26abf323a04b1db51f4a0050dc245f6e`,
removal-helper chain, body selection and all bounds remain those in the
preserved attempt-2 scope.

## Constructor and string evidence

For each exact `EventOption` constructor in the five complete
`GenerateInitialOptions` bodies, the tool emits one of:

- an `option_bindings` candidate when its segment has exactly one direct
  same-event MethodDef function pointer followed by exactly one key-like
  string; or
- an `unresolved_options` row containing only event type, constructor identity,
  constructor offset and one fixed reason:
  `callback_count`, `callback_shape`, `string_count`, `key_shape`, or
  `operand_order`.

The tool reports the actual direct-constructor count as the sum of exact
binding and unresolved counts and limits each array and their sum to 40. Zero
direct constructors is a valid evidence result: complete selected,
initial-options, callback and helper bodies still survive. An unresolved row is
evidence of missing proof, not an option identity or supported action.

To permit later manual dataflow review when the callback is cached or built in
a closure, the tool separately emits `string_candidates` only from the five
exact initial-options bodies and the already bounded same-event
`callback_candidate`/`callback_target` bodies. Each row binds role, event,
source method, body method, IL offset and an exact 1..96 ASCII key-like operand
matching `[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*`. The array is capped at 160.
These are lexical candidates only. Every other `ldstr` remains the fixed
`user_string` marker in body instructions, and no resource or localization
content is read.

No candidate is usable until independent review establishes the exact stack
and delegate dataflow from a key through its constructor to the exact selected
callback, plus selector-present/nonzero-domain, eligibility, preview and
post-await completion predicates. Events with incomplete mappings remain
whole-event unsupported before dispatch.

## Fail-closed and privacy boundary

The scanner still verifies the exact selection and prior result pins before
opening the target, hashes the same physical 9,363,456-byte `sts2.dll` to
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`
before `PEReader`, zeros image bytes on every post-allocation path, and never
loads or executes the assembly. It retains these caps:

- exactly 5 selected and 5 initial-options bodies;
- at most 64 event callback and 8 removal-helper bodies, 82 total;
- at most 2,500 instructions per body and 100,000 aggregate;
- at most 40 binding candidates, 40 unresolved constructors and 160 string
  candidates;
- no truncation and no looser retry after mismatch or overflow.

There is no target execution, gameplay, operator/profile/save, Cloud, network,
resource, localization or debug-data access.

## Exact tool and capture packet

The tool remains in `/private/tmp/event-card-callbacks-b`:

- `Program.cs`: `f2bdadd1b4f8bc6f32253195b506631704e9c11fa751df407e3e5b86263cd64e`;
- `IlDecoder.cs`: `58a15d83f6b97916ab5f63b2b765f29cd8d46e380d5a270bf8c91dd333d25933`;
- `MetadataNames.cs`: `f7b481088f436e9ada05fc269101cd98b05326122798ff6043eeab8286517d23`;
- project: `c21c689cf0292d7a0c305a1e9bbf4b6465c0450f7c1238fb260a5fe3aac17cf1`;
- selection: `cfc57aa9ef8fc35b818e6d2b2ab1fddf384f84904ed6c4c19e30e1e9173e4589`;
- runner: `087a143c76c9028bd07114ea0b1c596493c1d2eec7e1559d783aec0180e40ba3`;
- complete 14-input source manifest:
  `3a64ea4f4ede20e35035adf9b40f55f8978a18bef8a41eb929ad73db3298d5d5`.

The built bundle is:

- DLL, 71,168 bytes:
  `3c84de8f20d178875b8e2c34d7c90c19063e7462de4c25fe9fe3f23909df566a`;
- deps, 424 bytes:
  `0a059cd277ab0f19ed704a0a0d7ac716e0277fb24219a44650fa11e8c4897558`;
- runtime config, 257 bytes:
  `9b93bb9ae8b1f2d369e6bfd31f183e2db18031236ff1171bb899522aea902297`;
- copied selection:
  `cfc57aa9ef8fc35b818e6d2b2ab1fddf384f84904ed6c4c19e30e1e9173e4589`.

The tool's inert gate passes exact 15 checks. One scenario constructs a
valid selected option followed by a closure-bound disabled option whose
constructor segment contains an extra string. The selected binding and all
bodies survive, the second constructor is reported unresolved, its key-like
operand is retained as a lexical candidate, and it is never emitted as an
unambiguous binding. Another delegates all option construction outside both
exact `GenerateInitialOptions` bodies and proves zero constructor rows still
preserve both selected bodies, both initial-options bodies, callbacks and
helpers. The prior unrelated/selected generic-arity collision controls remain.

The capture wrapper remains in
`/private/tmp/event-card-callbacks-capture-b` and retains its private
create-only, fsync-before-validation, bounded-pipe and 60-second boundaries:

- wrapper: `eb1d9d92c17278845f29f6bc1106af5551b2af35a9b8362e795547844414e8a8`;
- fixture runner:
  `1852ec326ed2eb68e61274688c113f56e01f1173d7c9357f35cf972b86d91c10`;
- two-input manifest:
  `d2b1ce75ab3da77443c58776a4afaf0e05fb75dfadeb554000574dbb2a826dca`.

Its inert capture gate passes exact 3 checks. Independent review must accept
these exact bytes before the root coordinator may authorize one metadata-only
target invocation. A successful result still requires independent row-level
review before any implementation or live action.
