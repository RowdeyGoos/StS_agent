# Generic item request and screen — proposed bounded metadata scope

2026-09-08. Proposal for independent review; no target invocation is authorized by
this document alone. This scope resolves the remaining request/creation/completion
facts before a generic item-child implementation contract. It does not change the
25 frozen successors, install a mod, launch the game, or inspect profile data.

## Question and smallest coherent family

The intended first family is one direct potion or relic reward in an exact owned,
nonterminal NRewardsScreen created during an accepted EventOption.Chosen callback.
The actual frozen ItemV1Session proves one reward-local collection. Potion requires
an empty slot and exactly one null-to-exact-offered-model inventory insertion;
relic requires exact ClaimedRelic plus SuccessfullySelected, without an invented
inventory-count rule. Both retain the narrow existing item_v1 claim boundary.

The retained UpdateScreenState body proves an empty nonterminal screen removes
itself from the overlay; its terminal branch marks IsComplete and emits Completed
while retaining the screen's Proceed flow. We must establish how RewardsSet.Offer
creates that screen and what its returned Task awaits. A multi-offer set may need
more than one collection; the frozen one-shot item session cannot certify completion
of that set after collecting only one offer. No multi-offer broker is selected here.

The old event orchestrator's foreground adoption is insufficient: it did not bind
an actual shared request to screen creation or task completion. Its guards also
re-read a retired parent button. The new generic path must retain the existing
G5 parent ownership and opaque post-dispatch controller receipt.

## Target and filesystem boundary

The sole future target is the pinned regular assembly at:

`/Users/rowdeygoos/Library/Application Support/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.app/Contents/Resources/data_sts2_macos_arm64/sts2.dll`

Exactly9,363,456 bytes; SHA256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
The inspector must reject a changed path, symlink at any component, nonregular
file, byte-count mismatch or hash mismatch before metadata interpretation. It
must not load/invoke this assembly or resolve dependencies. Use PEReader and
System.Reflection.Metadata only. Do not copy this target into the repository.
No alternative target, scan, package, asset, resource, profile, save, backup,
Cloud, network or live application access is included.

Prepare a fresh disposable tool root only after independent scope acceptance:
`/private/tmp/generic-item-inspector-a`. Preserve all earlier tools and captures.
The separate future create-only capture root is
`/private/tmp/generic-item-target-a`. Only root may perform one target invocation
after the exact frozen source/bundle and synthetic evidence receive independent
review. No automatic retry or broadened follow-up is authorized.

## Exact retained selector sources

These retained files under `/private/tmp/sts-mr-api-v47tiwjy` were rehashed against
`docs/research/PHASE_1_MISSING_ROOM_API_SELECTION.json` before this proposal:

| File | SHA256 |
| --- | --- |
| RewardsSet.members.json | `966d4e5669323b5116eb298b16018557e658e0bcae3e6f7f6bc1bb3688711261` |
| NRewardsScreen.members.json | `4ac64095648fd4e87c8a47d1ce801da97c31e5fccf018a5ff3a99edb1651b20d` |
| Reward.members.json | `2ffffc36522617098bac176f5dbd4326213a43b86689ca02444882a1a219aa6c` |
| NRewardButton.members.json | `d269ef964cf1a95655e822aba0d1323dc454263745ae2b916bd555285b0c1a12` |
| NRewardButton--OnRelease.il.jsonl | `209b697ca6aaa33c1f388c4b33154ceefea0070b024540d413315c6b8a3fed72` |
| NRewardButton+\<GetReward\>d__26--MoveNext.il.jsonl | `027317330c69eafb6c400b9178b6e34168ad9b89845ea01e399aef4921a59d2c` |
| Reward+\<SelectUnsynchronized\>d__33--MoveNext.il.jsonl | `5dc930e5d3e5c5dd64b78ddd35caea50e4dd1065834f488e4ecc632d2d20c0cc` |
| NRewardsScreen--UpdateScreenState.il.jsonl | `8646c7cba87728b9e92140c82dfdf63f17c10d5b33461a3738a98813c49cf6f8` |

RewardsSet.Offer's retained method declaration identifies its exact generated
state-machine type as RewardsSet+<Offer>d__33. The three proposed bodies are not
present in the retained missing-room selection. The existing GetReward body
already proves the ordinary button path awaits synchronized selection and then
emits RewardClaimed or re-enables/emits RewardSkipped. It does not need rereading.

## Exact body selection — seven bodies only

Each identity must resolve uniquely, including the exact declaring type,
parameter types and return type. Missing, ambiguous or bodyless matches fail the
entire capture. Emit only method token, signature, visibility/static/instance
attributes, return type and bounded decoded IL:

1. `MegaCrit.Sts2.Core.Rewards.RewardsSet.Offer()` → `System.Threading.Tasks.Task`.
2. `MegaCrit.Sts2.Core.Rewards.RewardsSet+<Offer>d__33.MoveNext()` → `System.Void`.
3. `MegaCrit.Sts2.Core.Nodes.Screens.NRewardsScreen.ShowScreen(MegaCrit.Sts2.Core.Rewards.RewardsSet,System.Boolean,MegaCrit.Sts2.Core.Runs.IRunState)` → `MegaCrit.Sts2.Core.Nodes.Screens.NRewardsScreen`.
4. `MegaCrit.Sts2.Core.Rewards.RewardsSet.get_Player()` → `MegaCrit.Sts2.Core.Entities.Players.Player`.
5. `MegaCrit.Sts2.Core.Rewards.RewardsSet.get_Rewards()` → `System.Collections.Generic.List<MegaCrit.Sts2.Core.Rewards.Reward>`.
6. `MegaCrit.Sts2.Core.Rewards.RewardsSet.get_DisallowSkipping()` → `System.Boolean`.
7. `MegaCrit.Sts2.Core.Rewards.Reward.get_ParentRewardSet()` → `MegaCrit.Sts2.Core.Rewards.LinkedRewardSet`.

The first and third public declarations already establish instance Offer and
static ShowScreen. The second selection is the exact compiler-generated method
identity identified by the retained Offer metadata, not recursive discovery.
Do not select any other generated method or follow calls found in the output.

These bodies must answer: when the reward list is generated/populated relative
to screen creation; exact RewardsSet/player/run association; what the Boolean
argument means in this creation path; whether the local nonterminal screen is
actually created; what remote/custom/test or selectorless branches exist; what
the Offer Task waits for; and whether a singleton collected reward can complete
that task and resume the owned parent callback. Any unresolved answer remains a
gap; it does not authorize another body automatically.

## Getter purpose and exact field projection

The four getter bodies support exact request-domain/player binding, retaining the
skip rule and excluding linked rewards with additional effects. Their public
instance signatures are already in the rehashed immediate member inventories;
no bodies for these getters exist in the retained missing-room selection/output.
Inspecting their bounded bodies establishes whether they are passive reads before
observational use. Any unproved callee remains a gap and must not be recursively
followed. No separate method-declaration rows are emitted because the seven body
rows already include exact method attributes and return types.

Emit one exact field declaration, token/type/attributes only, no field value:
`MegaCrit.Sts2.Core.Rewards.RewardsSet.testSelector` →
`System.Func<MegaCrit.Sts2.Core.Rewards.RewardsSet,System.Threading.Tasks.Task>`.
The retained declaration is public/static. It is needed for rejecting an active
custom test selector in the future adapter. No private fields or field values
are projected. Do not emit a full type/member catalog, properties, MethodImpl rows,
interfaces, resources, strings, event lists or unrelated declarations.

## Bounds, redaction and capture

The first three bodies are capped at2,500 instructions each; the four getters
are capped at64 instructions each. The total ceiling is7,756. Exactly seven body
rows and one field row are allowed, with no separate declaration rows. Reject
malformed IL, unsupported metadata shapes, duplicate identities and any output
that exceeds the fixed schema. Member operand names/signatures may be emitted;
all user-string operands must be the literal redaction `user_string`. There is
no node-path or other string-value exception in this scope.

Reuse the accepted fixed-selection inspector helpers and corrected bounded capture
wrapper. Disable prior selection/declaration/field/node-path logic completely.
Use offline SDK9.0.303 with cleared package sources, no shared compiler and fresh
build/artifact directories. The runtime bundle contains exactly the inspector DLL,
.deps.json and .runtimeconfig.json, each pinned by size/hash before use.

The capture wrapper enforces at most1MiB stdout,4,096 stderr bytes and30 seconds;
kill/reap on overflow or timeout. Output is a new0700 directory and create-only
0600 stdout/stderr/result files. Fixed errors contain no target content or exception
text. Fixture/target modes remain explicit. Fixture mode accepts only raw canonical
absolute nonsymlink regular files under /private/tmp; reject invalid fixture paths
before accessing image metadata or creating output. Target mode permits no input
path, hash or selection override. Final capture output is canonical bounded JSON.

Before root's target invocation, freeze complete source, three-file bundle and
synthetic-result manifests. Independently review those exact hashes. Required
inert checks cover all seven exact bodies/one field; missing,
ambiguous, wrong-signature/return, bodyless and distinct ordinary-body/getter instruction-limit failures; hash,
symlink, malformed-image and canonical fixture-path guards; no traversal or string
leakage; exact declaration/field output restrictions; canonical schema; create-only
output; stdout/stderr caps and bounded timeout. Synthetic assemblies are inspected
as metadata only and must never execute game code.
