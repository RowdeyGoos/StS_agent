# Native combat construction and shuffle fidelity — 2026-09-14

Feature branch `codex/headless-combat-rng`, based on integration `de02974`, for
local merge into `codex/headless-integration`. Scope: solo Ironclad A0, Overgrowth
Act 1, pinned game 0.107.1 / Steam 23811903. Main and bridge sources are unchanged.

## Native reference

`sts2.dll` SHA-256:
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
The retained [oracle](../../tools/native_combat_oracle/README.md) calls actual
native methods using explicit in-memory contexts. No game launch, RunManager,
profile, save, history or Cloud access occurs. Its rebuilt output exactly reproduces
the retained [fixture](../../tests/fixtures/headless_native_combat_vectors.json).

- **184 construction cases:** four seed strings × two explicit total floors ×
  22 Overgrowth encounters plus Dense Vegetation. Checks compare roster order,
  max HP, opening move, and composition/HP/AI counters and next-double suffixes.
  Method execution constructs all native creatures before setting up and rolling
  their moves. Recorded native local monster seeds are context, not a claim of
  complete Python monster-local RNG consumption.
- **48 card permutations:** three uint32 RNG seeds × sizes 0/1/3/10/16/17/31/64 ×
  initial unstable/refill stable shuffle. Strike, Defend, Bash, Anger and Shrug It
  Off include upgrades and duplicate sort keys. Output indices identify physical
  card copies. Tests compare both stored pile and actual draw order.

Pinned anchors: `EncounterModel.GenerateMonstersWithSlots` 100682422;
`CombatState.CreateCreature` 100697658; `Creature.SetUniqueMonsterHpValue`
100696399; `MonsterModel.SetUpForCombat` 100682703;
`CardPile.RandomizeOrderInternal` 100696519;
`ListExtensions.StableShuffle` 100695729; `CardModel.CompareTo` 100682249;
`CardPileCmd.Shuffle` continuation 100712243; Fogmog branch weights
100708291/100708292. `RunState.TotalFloor` 100666464 counts history entries;
`EnterMapPointInternal` 100700670 appends the current room before combat startup
100701058 generates its roster. The first map combat therefore includes both the
Ancient root and current room. The oracle's explicit floors do not independently
prove that run-to-floor mapping.

## Behavior

Encounter composition now has a local seed derived from root seed + total floor +
native encounter ID hash. Creature HP uses the shared run Niche stream, including
fixed-HP monsters and Phrog/Fogmog summons. Available HP values exclude existing
living enemies' max HP when possible. Monster AI retains its separate shared
stream. Native SlimesNormal composition ordering is corrected; fixture trajectories
retain their previous generator behavior.

Native AI branches preserve binary32 cumulative inclusive boundaries. In particular,
Mawler no longer indexes past its candidates when a native float rounds to 1.0;
slime and Fogmog equality cases also choose the native branch.

Initial deck shuffle uses incoming order; empty-pile refill sorts by card model ID
and upgrade level first. The small native sort helper preserves .NET's equal-key
permutation before Fisher–Yates. Python keeps its stack representation and translates
native index-zero draw order at the boundary. Catastrophe uses the same stable
candidate shuffle for each autoplay. The sort fallback was inspected, not forced by
the native vectors; these cases do not exhaust all possible decks.

Combat snapshots advance to **v14**, run snapshots to **v26**. Niche ownership is
serialized with the other seven combat domains, rebound to the owning run and
validated atomically. Supported native enemies cannot redirect their AI RNG to HP
or another source. The exact synthetic SimpleEnemy remains exempt from native AI
ownership, preserving its fixture constructor. Older private schemas reject.

## Validation and packaging

- Final focused regression: **245 passed in 1.26 seconds**. This includes native
  vectors, generated first-floor binding, fixed-HP draws, Phrog/Fogmog summon
  continuation, random multihit death/reselection, Catastrophe autoplay, float
  endpoints and malformed ownership rejection. Continuation tests are Python
  regression evidence, not executed native full-action sequences.
- Independent semantic review verified all reported fixes; **244 cases passed in
  1.19 seconds** before the final additional Catastrophe regression. No unresolved
  concrete blocker. Review found the initial foreign-AI alias hole, endpoint crash
  and skipped-Neow floor offset; these were corrected before acceptance.
- Compatibility: **262 passed in 5.74 seconds**, covering engine snapshots,
  simulation, headless backends and package layout.
- Broad headless: **2,080 passed in 268.22 seconds** (4 minutes 28 seconds),
  before the additional Catastrophe regression covered by the final focused run.
- `compileall` and `git diff --check` passed. The retained .NET oracle builds with
  zero warnings/errors and reproduces the fixture exactly.

Built wheel SHA-256:
`5ea90953aab77ed6d75457ce058ca7c90bda6c59057cddeb6ce0b471348aefb5`.
Installed into the existing disposable environment and ran outside the checkout
with PYTHONPATH unset; imports resolve from site-packages. Installed checks passed
184 composition/HP/AI suffix cases and all 48 shuffle cases. The authored seed-2
slice completed in 38 commands with 66 HP. Generated seed 2/right/rest with Neow
visited 16 rooms, completed nine combats and lost at the boss after 198 commands.
Both CLI runs verified JSON restoration throughout. This establishes execution and
continuation, not native whole-run parity or a winning policy.

Work started around 19:17 UTC. Inspection, implementation and review overlapped;
separate phase durations were not recorded. Validation times are above. Package and
installed checks completed around 19:40 UTC. Final documentation and local integration followed around 19:43 UTC
(about 26 minutes total). No user wait or live release step was required. Scratch
outputs are in `/private/tmp/sts-headless-combat-rng`.

## Remaining work

HF-05C continues with native card/potion generation consumers, Bottled Potential's
nonempty-pile shuffle, initial/refill relic and power hooks, and dependent native
multihit/autoplay/spawn interaction sequences. Existing Stampede and Sword Boomerang
RNG domain choices were retained; Python replay alone does not certify every native
call. Cross-character Kaleidoscope support and an actual native Act 1 boundary
comparison matrix remain separate tasks. See the
[next assignments](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment).
