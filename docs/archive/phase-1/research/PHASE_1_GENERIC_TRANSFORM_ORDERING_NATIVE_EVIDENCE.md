# Generic transformation — ordering and native binding evidence

2026-09-08. This follow-up closes the previously identified deck-ordering,
public-result-field, request-filter and preview-container gaps. Together with the
[first transformation capture](PHASE_1_GENERIC_TRANSFORM_NATIVE_EVIDENCE.md), it
supports a separate transformation effect contract based on observed removals
and final appended replacements. It does not establish a live implementation.

## Exact retained evidence

The one root-owned invocation under
[the ordering scope](PHASE_1_GENERIC_TRANSFORM_ORDERING_SCOPE.md), scope SHA256
`543e6287808f54aca7ab2787ee24f12dee566f09ea84bb434daa6358530b5346`,
returned exit0 and empty stderr. The rehashed output is
`/private/tmp/generic-transform-ordering-target-a/stdout.bin`, 18,925 bytes,
SHA256 `380a2ba0f7307fa8a615f112bd705ed37ef4428d8a23c5c7102d282aeecd3118`.
It contains five bodies /116 instructions, five field projections, one method
declaration and two constrained node paths. The pinned target hash remains
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.

The previous capture was also rehashed: 204,926 bytes, SHA256
`fe6402573e251c2229fe615c38f3d11fbf760ef3fccb5443cee83d6c6adc485e`.
This analysis reads retained outputs only. It performs no new target read,
build, target execution, live/profile/network operation or frozen-successor edit.

## Deck insertion and ordering

`PileType.Deck` is a public static literal with Int32 value6; the enum's public
`value__` field is Int32. The earlier collection-transform branch for raw pile
value6 is therefore the deck branch.

`CardPile.AddInternal(CardModel,Int32,Boolean)` asserts that the card is mutable,
then throws if its Cards already contain the card (IL0–74). A nonnegative index
uses the backing List.Insert(index,card) (IL75–92). A negative index uses
List.Add(card) (IL94–101): the transform command's -1 argument appends the exact
card reference. The final Boolean is tested at IL142–143; false allows the
CardAdded callback and InvokeContentsChanged before return (IL145–164). Therefore
an observational postfix must validate the deck after those native callbacks;
the presence of the earlier List.Add instruction alone is not a successful
postcondition. A throwing callback can leave a mutation without a normal return.

`PileIndexSort` first compares the tuple piles' Type values when different
(IL0–65). When equal it compares Item3 in ascending order (IL66–84). The earlier
capture proves Item3 is the index captured immediately before each original's
removal, while preceding originals may already have been removed. These are not
necessarily original baseline indices. Equal captured indices do not establish
stable order. The adapter must follow actual observed final insertions and must
not predict their order from action order, HashSet iteration or baseline slots.

The command removes every batch original before entering its sorted insertion
loop. It appends each deck replacement and then awaits AfterCardChangedPiles
before advancing. For baseline [A,B,C,D] and selected {B,D}, the first inserted
replacement can therefore be observed with deck length3. After completion,
unselected originals retain their relative order and replacements form an
appended suffix in actual insertion order. This remains incompatible with the
frozen transform rule requiring constant length and replacements at original
positions; even a single non-tail original moves its replacement to the end.

## Exact request predicate and preview path

The generated `b__19_0(CardModel)` short-circuits to false when the raw numerical
CardModel.Type value equals6 (IL0–7,16–17). Otherwise it returns
CardModel.IsTransformable (IL9–15). Thus the owned candidate-domain admission
must mirror `(int)card.Type != 6 && card.IsTransformable`, preserving deck order
and exact original references. This scope did not inspect the card-type enum;
no name is assigned to its numerical value6. `b__19_1(CardModel)` constructs
`new CardTransformation(original)` directly (IL0–6).

The earlier request capture also proves the empty and nonmanual count<=MinSelect
automatic shortcuts. An owned-screen implementation must reject an observed
request completing without its owned screen, rather than treating that shortcut
as an ordinary parent transition. The same Player, run, complete pre-action deck,
exact candidate domain, effective transformation delegate and rule-bearing prefs
must bind the request and creation. Both manual preference values can be admitted
when the concrete owned local screen is actually observed.

`NTransformPreview._Ready` assigns public-path GetNode<Control>("%Before") to its
before field (IL0–17) and GetNode<Control>("%After") to its after field (IL22–39).
The scanner proved the exact generic argument/return shape, both receivers,
unique field assignments and absence of branch/switch/EH entry into either
assignment's interior byte interval. All IL strings remain redacted; these two
path values are separate narrowly permitted projections. No third path value
was exposed.

The prior Initialize body proves that before holders display exact transformation
Original references. The adapter can inspect that public before container and
bind exact holders/cards/originals; it need not re-enumerate the lazy transformation
input or read private fields. After holders may display animated possibilities
or a supplied replacement and are not authoritative final-deck-result witnesses.
Exact before membership must match the action-correlated selected set, and holder,
card, original and container references must remain bound through Confirm.

## Final replacement identity and hook feasibility

The new projection proves these instance fields are public:
`CardPileAddResult.success : Boolean`, `cardAdded : CardModel`, and
`modifyingModels : List<AbstractModel>`. It also proves the exact public static
method declaration returning CardModel:

`Hook.ModifyCardBeingAddedToDeck(IRunState,CardModel,ref List<AbstractModel>)`.

Its body was not selected. The previous collection-command body already proves
that the returned card replaces GetReplacement's initial result before deck
insertion and is copied into cardAdded. The new field projection enables bounded
public inspection of completed result entries, including success. A default
result wrapped in Nullable remains insufficient: HasValue alone does not prove
success or a non-null final card.

The proposed fifteen-method ownership closure is feasible from these retained
boundaries: preserve the nine generic-v4 hooks, then observe the exact transform
request, transform ShowScreen, collection CardCmd.Transform, value-type
CardTransformation.GetReplacement, the public modification hook, and AddInternal.
This is a design conclusion, not an implemented or live-tested result.

The necessary ownership sequence is:

1. Reserve the exact selected-original set before dispatching native Confirm.
   Before-preview holder membership and the core action history must agree;
   an observation of a user callback does not itself authorize it.
2. Admit a collection command only in that owned continuation. Preserve its exact
   returned Task, and carry a restored observational scope across its native
   awaits. Do not independently enumerate the command input.
3. Each GetReplacement return records the exact transformation Original to initial
   card reference. Before the first deck modification, compare all observed batch
   originals with exact baseline subtraction; all must be selected, disjoint from
   prior completed batches and removed, with every other original unchanged.
4. Bind each modification's exact initial argument to its original, then record
   its exact returned final reference. Require exact run/deck ownership and reject
   duplicates, concurrent/nested commands, reuse and foreign invocations. Initial
   and final identities must satisfy the accepted contract's disjointness rules.
5. On the corresponding successful AddInternal return, verify the exact deck and
   appended final reference after native callbacks. Only then publish its insertion
   witness. No normal-return witness is published on exception; subsequent effect
   checks still reject any unaccounted mutation.
6. Require bounded successful command results to agree with observed final cards,
   plus successful request and parent Chosen tasks, before resolution. Sequential
   disjoint command batches can support callers that use the single-card wrapper;
   per-batch scope identity must not be reused for later commands.

No transform OnCardClicked interception is required by this mapping if the core
already correlates action history with the exact complete before-preview original
set. This does not relax controller ownership or permit re-enumeration of lazy
transformation inputs.

## Implementation acceptance still required

No additional static read is presently required for this proposed bounded path.
The new effect contract and native implementation still need independent review
and inert tests proving append order, partial removals/insertions, modifier-changed
final identities, deferred callbacks, same-original foreign invocations, mutated
preview bindings, callback exceptions, task faults/cancellation, sequential batches,
and successful cleanup. Public path existence and retained IL do not prove live
layout readiness, concrete visual-node types, or supported real-event coverage.
