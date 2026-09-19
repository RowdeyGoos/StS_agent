# Event interaction research map

This is the entry point to the **dated native-source census**, not a current
support matrix. Use [status](STATUS.md) for implemented behavior, failures and
remaining tests, [caller evidence](EVENT_COVERAGE.md) for demonstrated paths,
and [contracts](GENERIC_EVENTS.md) for current semantics.

## Scope and interpretation

The September 9–10 research inspected Slay the Spire 2 **v0.107.1 / Steam
23811903**: 68 concrete event types and 105 grouped branches, including immediate
interactions in 135 explicitly referenced relic types. Pool references include
57 ordinary events and seven ancients; Darv, The Architect and two deprecated
placeholders account for the other four types. This is not a whole-game transitive
proof of every random relic, modifier, global hook or generated outcome.

Pool membership is not current-run eligibility. A branch group is not every
possible option/state. The research read no player progress and makes no encounter
frequency or supported-event percentage claim. Automatic effects may need no new
input surface while still remaining unverified by the bridge's parent summary.

- [Research record and scanner](evidence/event_interactions_2026_09_09/README.md)
  retain source identity, scope and reproducibility details.
- [Original structured inventory](evidence/event_interactions_2026_09_09/inventory.json)
  retains method tokens, positive IL offsets, pool references and original annotations.
- [Archived narrative/matrices](archive/EVENT_INTERACTION_MAP_2026_09_10.md)
  preserve the original comparison against `4d3516f` and subsequent dated commentary.
  Its “gap” labels are **historical**, not today's missing features.

The inventory and recorded hashes have not been rewritten. Apply the corrections
below when interpreting it.

## Sea Glass research correction

The original `sequential_children` finding for Orobas is superseded. In the same
pinned IL, `SeaGlass.get_CanonicalVars` constructs `CardsVar(15)`;
`AfterObtained.MoveNext` concatenates rarity lists at offsets 335/342, materializes
one list at 347, constructs preferences `(0, list.Count)` at 390 and calls
`FromSimpleGridForRewards` once at 410. Selected additions follow at 551.
**Sea Glass uses one optional 0..15 grid**, not sequential selector children.
That finding establishes no separate sequential-selector caller.

## Choose-card research clarification

`CardSelectCmd.FromChooseACardScreen` accepts at most three direct choices
(state machine d13, IL39–45); native click admission requires more than 350 ms
since opening. Bundle preview moves the existing card nodes, and each screen's
task wrapper removes its own overlay before request completion.

The original Hefty Tablet description of “multiple copies” is incorrect.
`AfterObtained.MoveNext` passes `canSkip=true` at IL185, chooses at 186, creates
Injury at 313, conditionally inserts the chosen original before it at 324–340,
and adds the sequence at 350. **Choose adds the chosen original plus Injury;
Skip still adds Injury.** Lead Paperweight and Massive Scroll also allow Skip,
without that appended grant. These use `card_offer_v2`; no required-choice v1
caller was identified in the bounded inspection.

## Interaction families and concrete blockers

The [historical family matrix](archive/EVENT_INTERACTION_MAP_2026_09_10.md#interaction-families-and-concrete-blockers)
explains native dependencies and source-backed acceptance questions. Counts overlap
and do not measure remaining effort. Many of its original gaps are implemented now;
consult [current implementation gaps](STATUS.md#implementation-gaps-versus-remaining-live-tests)
before choosing work.

## All-event map

The [68-type table](archive/EVENT_INTERACTION_MAP_2026_09_10.md#all-event-map)
and [structured inventory](evidence/event_interactions_2026_09_09/inventory.json)
identify branches and native surfaces. “Candidate” means the research found no
specific missing interaction at that checkpoint; it does not promise runtime
support or all-branch acceptance.

## Ancient relic pickup paths

The [27-path appendix](archive/EVENT_INTERACTION_MAP_2026_09_10.md#ancient-relic-pickup-paths)
traces `RelicOption` → `RelicCmd.Obtain` → `AfterObtained`. Apply the Sea Glass
and Hefty Tablet corrections above. The research does not establish normal Darv
pool eligibility or exhaustive support for random pickup effects.

Later pinned inspection found ordinary random relic rolls use rarities 2/3/4,
while the identified pickup-selector relics use shop/ancient rarities 5/7. Small
Capsule/Toy Box therefore do not establish the proposed ordinary random reward →
nested-selector case. See the [contract reference](GENERIC_EVENTS.md#nested-pickup-boundary).

<a id="what-the-research-changes"></a>
<a id="planning-implications"></a>

## Using the research for new work

Name the branch, native request/screen chain, observable effect and completion
destination. Check current support before proposing a new adapter. Existing
mechanisms may need a held-out caller test rather than another implementation.
[Roadmap](../ROADMAP.md) owns priorities.

## Earlier assumptions to retire or narrow

- `Symbiote.KillWithFire` reads a dynamic value but passes equal min/max bounds;
  it does not establish variable-count selection. Claws/Sea Glass supply concrete
  optional cases; zero confirmation is not native cancellation.
- No inspected event/immediate named pickup establishes variable upgrades or true
  cancelable deck selection. This statement is scoped to those event/pickup callers:
  **rest-site Smith and Cook do allow cancellation**, as checked below.
- The 17 inspected referenced enchantments inherit non-stackable behavior; those
  callers do not establish a need for stacking/replacement.
- Event prose is not the input family: Round Tea Party's “fight” is option-driven
  damage, Sunken Treasury has automatic gold/curse effects, and Welcome to Wongo's
  uses ordinary choices rather than a merchant surface.
- The scan establishes no unallocated-holder caller. Automatic selectorless
  completion is a separate static case: native removal may return all eligible
  cards without a screen when count is at most `MinSelect`. That is not an empty
  or canceled selector and has no live acceptance from this research.

## Native capability audit: September 19

This follow-up checked which reported bridge gaps correspond to actual native
interactions, including rest sites outside the original event census. It used the
same pinned `sts2.dll`, SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
Metadata/IL were read with the existing `PEReader`/`IlDecoder` scanner machinery;
no game assembly was executed, game launched or player data accessed.

The scan traversed **9,409 types and 48,901 method bodies** for references to
`SmithCount` and rest-option constructors, then inspected the concrete option,
relic/card and selector bodies. It found no call to `set_SmithCount`. Backing-field
writes occur only in the property setter and the constructor, which stores one.
This establishes no ordinary multi-card Smith caller in this pinned assembly;
it is not a claim about mods or future builds. The source fact, rather than the
bridge's defensive guard, determines the current capability list.

Representative metadata anchors (offsets are decimal IL offsets):

| Native method | Token / offset | Finding |
| --- | --- | --- |
| `SmithRestSiteOption..ctor` | `0x06007fb7`, IL2 | Store default count one |
| `SmithRestSiteOption.<OnSelect>d__14.MoveNext` | `0x0600bd11`, IL45/68 | Native Cancelable=true; call upgrade selector using SmithCount |
| `CookRestSiteOption.<OnSelect>d__9.MoveNext` | `0x0600bcfc`, IL48/72 | Native Cancelable=true; removal selector (count two) |
| `Shovel.TryModifyRestSiteOptions` | `0x06005302`, IL13 | Create Dig option |
| `Girya.TryModifyRestSiteOptions` | `0x06004f77`, IL24 | Create Lift option, gated by lift counter |
| `MeatCleaver.TryModifyRestSiteOptions` | `0x060050b1`, IL13 | Create Cook option |
| `PaelsGrowth.TryModifyRestSiteOptions` | `0x06005180`, IL13 | Create Clone option |
| `PumpkinCandle.TryModifyRestSiteOptions` | `0x06005265`, IL13 | Create Kindle option |
| `ByrdonisEgg.TryModifyRestSiteOptions` | `0x06006cb2`, IL13 | Create Hatch option |
| `Trial.<MerchantInnocent>d__17.MoveNext` | `0x0600b3fb`, IL144 | Upgrade selector with fixed count two after Shame |
| `YummyCookie.get_CanonicalVars` / `<AfterObtained>d__10.MoveNext` | `0x0600549f`, IL1 / `0x0600ab40`, IL52 | Canonical count four feeds upgrade selection |

`RestSiteOption.Generate` creates Heal/Smith and adds Mend only with multiple
players. `HealRestSiteOption.ExecuteRestSiteHeal` invokes reward-modifying hooks;
Dream Catcher supplies a card reward and Tiny Mailbox two potion rewards. Those are
real follow-up surfaces, not evidence that basic Heal already drives them.
`BattlewornDummy.Resume` offers a single potion for Setting1, automatically
upgrades two cards for Setting2, and directly obtains a relic for Setting3. It
does not establish resume-time card menus, multiple item offers or a relic chooser.

[Current status](STATUS.md#implementation-gaps-versus-remaining-live-tests) separates
these concrete interactions from unsupported shapes with no identified caller.
The audit is static evidence of native behavior, not a live acceptance result.
Original census artifacts and historical hashes remain unchanged.
