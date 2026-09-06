# Event card operations v1 native caller selection

2026-09-06; proposed for independent review. This is the second-stage native
selection record under the frozen event-card structural contract
`be480799460c5a5799bd9785d21f1c41d6467c912876cd456b271999408dac6e`.
It preserves all thirteen accepted successors and the frozen API/schema.

## Evidence and exact rows

The complete metadata-only callback result is 246,733 bytes, SHA-256
`e8c6f9aad5035daa21e7329b89669c652c9845ae07049d9f1274b1cd26c762ca`.
Its exact pinned game image remains
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
No target assembly was executed. Callback candidate labels alone are not proof;
the complete initial-option stack and selected attributed body establish these
two rows:

| Exact event type under MegaCrit.Sts2.Core.Models.Events | Exact option key | Policy ID | Callback |
| --- | --- | --- | --- |
| AromaOfChaos | AROMA_OF_CHAOS.pages.INITIAL.options.MAINTAIN_CONTROL | aroma_maintain_control_upgrade_one | MaintainControl() |
| SapphireSeed | SAPPHIRE_SEED.pages.INITIAL.options.EAT | sapphire_eat_upgrade_one | Eat() |

Aroma initial-options IL56 binds the exact instance callback, IL67 supplies the
key, and IL77 constructs that EventOption. Its attributed callback body calls
FromDeckForUpgrade with Owner and UpgradeSelectionPrompt/count1 at IL18–34,
awaits the selector, upgrades the returned first original at IL131–142, then
calls SetEventFinished at IL213. Sapphire uses callback/key/constructor offsets
10/21/31. Its body first awaits healing, then calls the same selector with
Owner/prompt/count1 at IL148–164, upgrades the returned first original at
IL258–269, and calls SetEventFinished at IL286. The existing public IsFinished
of that same exact event instance is the post-effect witness; a different page
projection or task completion alone is insufficient.

Both rows select Upgrade, min1/max1, PreviewThenConfirm,
ExistingDeckOriginals, complete candidate domain2..64. Before parent dispatch,
retain the complete deck (at most512), exact eligible original references and
each baseline card state. Eligibility is exactly CardModel.IsUpgradable.
Recompute/compare those bindings before dispatch and at admission. Bind the
exact first NDeckUpgradeSelectScreen, one initially incomplete completion task,
complete card grid, single-upgrade preview and enabled confirm control. Reuse
the frozen card session and its exact one-original upgrade delta reconciliation.

Retained selector evidence is hash-verified against selection authority
`ec8b8d53858182e8e75d4efebe2a843de7a6d9b74b9de2f5b9c1c2252ad349b9`:

- CardSelectorPrefs constructor set:
  `fc4856a0b74c4bb5e00759c84799cd2fcec1ee7abe7a928d03f353902ed4082b`
  binds equal min/max and defaults RequireManualConfirmation false.
- FromDeckForUpgrade attributed body:
  `301e54317670e9c9687bda1e283e0c801c2be23b02c0fb5ca77afce852938201`
  filters the deck, skips the screen for an empty domain or count<=min with no
  manual requirement, otherwise opens NDeckUpgradeSelectScreen for the local
  player. Thus a domain of zero or one is unsupported before any dispatch.
- The exact eligibility predicate:
  `1b4c549ef4ee53d6143a91a06d0e5769ce81031202a9ab67b9b156dda38457f7`
  returns CardModel.IsUpgradable directly.
- Upgrade preview/click body:
  `01bf27c78e87361d13a7eb87550cafa44a4157ef035d01e522642b7ef3bbf3cb`.
  The single-preview original is public NUpgradePreview.Card, as already used
  by the accepted Smith adapter. This packet adds no multi-upgrade native row.

Require public CardSelectCmd.get_Selector() to be null immediately before
dispatch; if no exact expected local foreground selector appears afterward,
terminalize unsupported. The private ShouldSelectLocalCard is not invoked or
claimed as a pre-dispatch predicate. A missing native foreground screen
never becomes an ordinary option-transition success for a supported-card row.

## Closed classification

The complete initial-option maps for these exact event types are:

- Aroma: MAINTAIN_CONTROL supported under the bound row; LET_GO known
  unsupported card transformation.
- Sapphire: EAT supported under the bound row; PLANT known unsupported card
  enchantment.

Unknown non-Proceed keys in either selected type make the capture unsupported.
An exact supported key with no valid full domain remains visibly enabled as an
observation fact but is classified unsupported_card, with no policy/factory.
Duplicate matching options and subclasses are unsupported. Accepted Cheese
behavior is preserved. All other positive card-selector event types in the
accepted caller census remain whole-event unsupported before dispatch until a
complete reviewed option map exists. Ordinary nonclassified event behavior and
its existing stop boundaries remain unchanged. Proceed is handled by the
shared parent after the resolved card child has been delivered and disposed.

BrainLeech, ZenWeaver, Wellspring and transformation rows are not selected here.
BrainLeech still needs a proven generation-count rule, ZenWeaver needs its
outer awaited callbacks and concrete count/witness, and Wellspring has an
additional post-removal AddGuilty effect. Later exact rows require a separate
accepted selection record; none is inferred from generic operation tests.

## Required native validation

Tests must execute the production native capture/factory/adapter code against
inert target stubs and the real frozen card session. Cover both exact rows,
pre-dispatch deck/eligibility changes, domain0/1 and over64 rejection, delayed
Sapphire pre-selector healing, initially complete/wrong/replaced tasks and
screens, cleared grid highlights with exact preview original, enabled-control
binding, delayed or wrong upgrade effects, unrelated deck changes, absence of
IsFinished, parent replacement, unsupported paired choices and census types,
Cheese/item/ordinary regressions, and resolved-child disposal/Proceed.

After independent review and coordinator disposition, native implementation
may begin in the new successor only. This record alone creates no listener,
package, installation or live campaign.
