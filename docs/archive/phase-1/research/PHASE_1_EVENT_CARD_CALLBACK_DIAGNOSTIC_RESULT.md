# Phase 1 event card-callback diagnostic result

- Date: 2026-09-06
- Status: metadata-only capture passed; rows remain review-bound
- Reviewed scope SHA-256:
  `58f91c813420ac6e319b80bfaaa9db73291601d68ffab7741a529e4f87ae2921`
- Reviewed tool source manifest:
  `3a64ea4f4ede20e35035adf9b40f55f8978a18bef8a41eb929ad73db3298d5d5`
- Reviewed scanner DLL: 71,168 bytes,
  `3c84de8f20d178875b8e2c34d7c90c19063e7462de4c25fe9fe3f23909df566a`
- Reviewed capture manifest:
  `d2b1ce75ab3da77443c58776a4afaf0e05fb75dfadeb554000574dbb2a826dca`

## Persisted result

The one authorized diagnostic invocation completed successfully. The assembly
was read only as pinned metadata and IL and was never loaded or executed. No
gameplay, operator/profile/save, Cloud or network access occurred.

The private create-only output is
`/private/tmp/event-card-callbacks-capture-08be47c191934886a0103cd5`:

- `result.json`: 246,733 bytes, mode `0600`, SHA-256
  `e8c6f9aad5035daa21e7329b89669c652c9845ae07049d9f1274b1cd26c762ca`;
- `stderr.bin`: 0 bytes, mode `0600`, SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- `summary.json`: 202 bytes, mode `0600`, SHA-256
  `5ab4d5d51857346443a769cb6fe8da57facc89ad7c6fb46047cb77cd97750487`.

The exact bounded counts are:

- 5 selected bodies, 5 initial-options bodies;
- 12 event callback bodies and 4 removal-helper bodies;
- 26 bodies and 1,316 decoded instructions total;
- 9 unambiguous constructor candidates, 2 unresolved constructors and 14
  lexical string candidates.

## Exact direct selected bindings

Four selected callbacks have direct constructor candidates whose key and
delegate are adjacent in the complete initial-options body:

- `AromaOfChaos.MaintainControl()` ->
  `AROMA_OF_CHAOS.pages.INITIAL.options.MAINTAIN_CONTROL`;
- `BrainLeech.ShareKnowledge()` ->
  `BRAIN_LEECH.pages.INITIAL.options.SHARE_KNOWLEDGE`;
- `SapphireSeed.Eat()` ->
  `SAPPHIRE_SEED.pages.INITIAL.options.EAT`;
- `Wellspring.Bathe()` ->
  `WELLSPRING.pages.INITIAL.options.BATHE`.

These rows establish only key-to-callback construction. They do not by
themselves establish selector admission, eligible-domain completeness or
completion.

`ZenWeaver.GenerateInitialOptions()` directly binds
`BreathingTechniques`, which is not the selected removal caller. Its two other
constructor segments are unresolved with reason `string_count` because each
segment also reads a dynamic-variable cost key. The complete instructions do
show direct function pointers for `EmotionalAwareness()` and
`ArachnidAcupuncture()` immediately followed by the lexical option keys
`ZEN_WEAVER.pages.INITIAL.options.EMOTIONAL_AWARENESS` and
`ZEN_WEAVER.pages.INITIAL.options.ARACHNID_ACUPUNCTURE`, respectively, before
their exact constructors. Independent stack/dataflow review is still required.

## Selected operation facts and gaps

- `AromaOfChaos.MaintainControl()` constructs upgrade preferences with count
  1, awaits `FromDeckForUpgrade`, takes `FirstOrDefault`, awaits
  `CardCmd.Upgrade` when nonnull, and then calls `SetEventFinished`.
- `SapphireSeed.Eat()` first awaits a heal, then uses the same upgrade-count-1,
  `FirstOrDefault`, awaited-upgrade and `SetEventFinished` sequence.
- `Wellspring.Bathe()` constructs removal preferences with count 1 and a null
  event filter, awaits removal and `RemoveFromDeck`, then awaits `AddGuilty`
  before `SetEventFinished`. The extra awaited mutation needs separate review;
  this result does not authorize a removal-only delta policy.
- `ZenWeaver.RemoveCardsAndProceed(count,cost)` passes its callback-supplied
  `count` into removal preferences, awaits removal and `RemoveFromDeck`, then
  awaits `LoseGold(cost)`. It does not call `SetEventFinished` itself. The exact
  `EmotionalAwareness` and `ArachnidAcupuncture` state-machine bodies are needed
  to bind concrete counts/costs and the parent completion witness.
- `BrainLeech.ShareKnowledge()` reads a redacted dynamic-variable key as the
  reward creation count, creates the reward list, uses count-1 noncancelable
  selection, awaits one `CardPileCmd.Add`, previews the add and calls
  `SetEventFinished`. The exact dynamic-variable key/value contract and a
  complete runtime reward-domain proof remain missing.

The retained selector-helper evidence also shows that an upgrade, removal or
simple-grid reward helper can return empty or complete without opening a screen
when no candidate exists or when eligible count does not exceed `MinSelect`
and manual confirmation is false. A child-backed production row must reject
that selectorless branch or separately support a direct effect; no such direct
effect is authorized here.

## Smallest follow-up evidence

A finite follow-up can remain limited to:

1. the exact `EmotionalAwareness()` and `ArachnidAcupuncture()` source methods,
   their attribute-bound state-machine `MoveNext` bodies, and their direct call
   to `RemoveCardsAndProceed(int,int)`; and
2. the exact `ldstr` operand at offset 41 (`0x29`) in the already captured
   `BrainLeech.ShareKnowledge` state-machine body, feeding
   `DynamicVarSet.get_Item` immediately before
   `DynamicVar.get_IntValue` and `CardFactory.CreateForReward`.

No other event, arbitrary callee, resource or localization content is needed.
The follow-up must be independently scoped and reviewed before another target
read. Until its result is accepted, all five proposed rows remain disabled;
census-positive events without a complete mapping remain whole-event
unsupported before dispatch.
