# Phase 1 event-card Brain/Zen follow-up result

- Date: 2026-09-06
- Status: metadata-only follow-up passed; no production row was enabled
- Reviewed scope SHA-256:
  `c5c378d83fd6b550c13e55f10e1c93c4f6046afc4ffe563185f0d90f7957d834`
- Reviewed scanner source manifest SHA-256:
  `3a5745be55c139af6004d352c352cf8c043bb8feaf859f4ba02ebbc1f39fc370`
- Reviewed scanner DLL: 53,760 bytes, SHA-256
  `017e87d0bc88dfd4d060c6ddd0193e5ade8ece78e45d0db62d329a39ec6c00e5`
- Reviewed capture manifest SHA-256:
  `18b76763b7dfc57ef93261ce7510ac7d2b3dd6c708e02efaebc6980343b5619b`

## Pretarget invocation correction

The first shell invocation selected the diagnostic fixture bundle rather than
the reviewed target-mode bundle. Its `selection.json` was the intentionally
mutated 2,898-byte fixture with SHA-256
`09dbdf606e707f3a14b7a4fb73d917537334bc72623dabfba1b619962bc2129d`,
not the reviewed 2,897-byte selection with SHA-256
`cf9e66383f9d41b8a061cb3ad8544a2e0b1a4dff43ca0744723962257c0a5a31`.
The capture wrapper rejected it with `file_shape` while verifying its own
bundle, before creating an output directory or starting the scanner. The game
image was not opened. This failed pretarget command is separate from the later
authorized metadata invocation and is not a target retry.

## Persisted result

After a separate exact-bundle review and authorization, one metadata-only
invocation completed. It read the pinned assembly through `PEReader`; it did
not load or execute the assembly. No game process, gameplay, profile/save,
Cloud, package, listener or network operation was involved.

The private create-only output is
`/private/tmp/event-card-followup-capture-841a406cc84f4e879d130eb1`:

- `result.json`: 23,357 bytes, mode `0600`, SHA-256
  `8fd76338f6b6eb64aa1063fa24b5cf77fd66fbaeec062af234bea09186e7cfe9`;
- `stderr.bin`: 0 bytes, mode `0600`, SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- `summary.json`: 217 bytes, mode `0600`, SHA-256
  `92e3a0a8e5587292a8d05640c95999d321eafc7722b0f2d0731c170ada41a655`.

The result binds the exact pinned image SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`,
the reviewed selection SHA-256 above and the prior complete diagnostic result
SHA-256 `e8c6f9aad5035daa21e7329b89669c652c9845ae07049d9f1274b1cd26c762ca`.
It contains exactly two Zen bodies, 140 emitted instructions and 291 inspected
instructions, plus one bounded Brain string-flow row.

## Brain Leech disposition

`BrainLeech.<ShareKnowledge>d__9.MoveNext()` loads the exact key
`FromCardChoiceCount` at IL offset 41. The contiguous reviewed flow calls
`DynamicVarSet.get_Item`, reads `DynamicVar.get_IntValue`, and passes that
integer as the count argument to `CardFactory.CreateForReward`. The number of
generated choices is therefore dynamic; this evidence does not establish a
fixed count.

Combined with the retained complete caller/helper evidence, the callback then
materializes the creation results, constructs noncancelable selection
preferences with minimum and maximum 1, awaits
`CardSelectCmd.FromSimpleGridForRewards`, takes `FirstOrDefault`, awaits one
deck `Add`, previews that add and calls `SetEventFinished`. The retained helper
body returns directly when the generated count is at most the minimum and
manual confirmation is false, while a count greater than 1 follows the local
simple-grid branch.

This makes `SHARE_KNOWLEDGE` a viable bounded add-one row only if native
admission captures the exact `FromCardChoiceCount` value before dispatch,
requires it in the selected range (at least 2 and at most the repository child
domain cap), and proves that the first foreground simple grid is the complete,
ordered, unique set of generated card originals of exactly that size. It must
retain the event/option/controller and generated-card identities through every
child read/apply, reject selectorless completion and replacement or partial
pages, and reconcile the exact selected card through the awaited add and same
event `SetEventFinished`. `RIP` remains a separate unsupported option. No Brain
row is enabled by this result alone.

## Zen Weaver disposition

The exact attributed state-machine bodies are:

- `ZenWeaver.<EmotionalAwareness>d__8.MoveNext()`;
- `ZenWeaver.<ArachnidAcupuncture>d__9.MoveNext()`.

Each body reads one redacted dynamic-variable key, obtains its integer value,
then pushes a constant (`1` for Emotional Awareness and `2` for Arachnid
Acupuncture) before the sole direct call to
`RemoveCardsAndProceed(int,int)`. This proves the dynamic integer is the first
call argument and the constant is the second. The retained helper state-machine
body contains fields named `count` and `cost`, uses `count` to build removal
preferences and uses `cost` for `LoseGold`, but the retained evidence does not
include the source wrapper IL that assigns the two method arguments to those
fields. It therefore does not prove whether the dynamic first argument is
`count` or `cost`; the constants must not yet be described as either removal
counts or costs. Each caller awaits the helper to completion and only afterward
calls `SetEventFinished` on the same event, which supplies the required
post-effect parent witness.

The earlier automatic constructor extractor labeled the two Zen segments
unresolved because it counted the nearby dynamic-variable strings. The complete
retained `GenerateInitialOptions` instructions nevertheless permit bounded
stack review: `EmotionalAwareness` is loaded at offset 68, its delegate is
constructed at 74, its option key is loaded at 79 and its `EventOption` is
constructed at 89; the corresponding Arachnid offsets are 130, 136, 141 and
151. The earlier cost-key loads at 49 and 111 occur before conditional branches
and are not constructor-stack values. This semantically binds the exact
`EMOTIONAL_AWARENESS` and `ARACHNID_ACUPUNCTURE` option keys to their callbacks,
although the generic extractor did not label them as candidates.

The two Zen rows still remain blocked. The dynamic-variable keys at the
redacted caller offset 24 are unknown, and the source-wrapper argument-to-field
assignments are missing. Production admission must also bind the exact
all-affordable three-option initial map, captured dynamic value and complete
eligible removal domain before dispatch. A locked variant remains whole-option
unsupported. Until the wrapper assignment is proved, neither call argument can
be assigned count or cost semantics.

## Claim boundary

This result closes the requested Brain count-key flow and Zen caller completion
bodies. It does not authorize a production row, infer a fixed Brain or Zen
selection count, map the Zen call arguments to the helper's named fields, or
demonstrate runtime/gameplay behavior. The Zen option binding rests on bounded
manual stack review rather than an extractor-produced binding row. Any row
addition still requires a separately reviewed immutable catalog/native change
and executable negative fixtures for the remaining admission and identity
gates.
