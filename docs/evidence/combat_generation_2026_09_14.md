# Native combat generation — 2026-09-14

Feature branch `codex/headless-combat-generation`, based on integration `db55c62`,
for local merge into `codex/headless-integration`. Scope remains solo Ironclad A0,
Overgrowth Act 1, ordinary all-unlocked pools, game 0.107.1 / Steam 23811903.
Main and the production bridge are unchanged.

## Native evidence

Pinned `sts2.dll` SHA-256:
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
The existing [combat oracle](../../tools/native_combat_oracle/README.md) now has
an optional `generation` mode. It executes actual native CardFactory and
PotionFactory methods with a synthetic solo player, an empty deck, all-unlocked
state and the existing explicit combat context. No game launch, RunManager,
profile, save, history or Cloud access occurs. Its default mode still reproduces
the previous construction/shuffle fixture exactly.

The new [fixture](../../tests/fixtures/headless_native_combat_generation_vectors.json)
retains direct assembly output:

- Native metadata and eligible order for **78 Ironclad and 50 colorless** ordinary
  combat-generated cards. Skill includes the engine's legacy `block` category;
  native X costs retain their separate flag (native canonical 0, local sentinel -1).
- **66 card-generation sequences:** 11 caller recipes × six seeds, including the
  actual combat-card stream seed for run seed 2. Each call records its complete
  filtered pool, selected cards, upgrade levels, counter and final RNG suffix.
  Recipes cover Infernal Blade, Discovery, Attack/Skill/Power/Colorless Potions,
  Jack of All Trades, Jackpot, Stoke, Calamity and Orobic Acid's three type calls.
- **16 boundary cases:** empty/singleton/duplicate input pools, zero requests and
  requests larger than a distinct pool. Duplicates are filtered before sampling.
- **12 repeated potion sequences:** actual in-combat and out-of-combat factories
  called three times, at six seeds including run seed 2's combat-potion stream.
  Independent calls allow duplicates; a single distinct multi-potion batch has
  different semantics and remains covered by the earlier acquisition fixture.

Anchors: `CardFactory.GetDistinctForCombat` 100695702, `GetForCombat` 100695703,
`FilterForCombat` 100695704 / predicate 100711619; `IEnumerableExtensions.TakeRandom`
100695728; `CombatState.CreateCard` 100697652. Pinned caller continuations confirm
Infernal Blade and Orobic Acid call the distinct factory even for one card;
Calamity and current-build Stoke call the replacement factory. The older Stoke
reference instead draws cards and is not the target behavior. Alchemize calls
`CreateRandomPotionInCombat` before procurement; Entropic Brew continuation
100707895 calls the out-of-combat factory once per available slot.

These methods execute selection and native card construction. They do not execute
whole OnPlay/OnUse flows, optional screens or card-insertion hooks. Caller recipes
come from pinned IL; upgrades, discounts and continuation behavior are additionally
checked through Python actions. No whole-native-combat or whole-run parity claim
is made.

## Changes

`generation/combat.py` owns shared pool filtering and distinct/replacement selection.
Existing NativeRng.sample already used full-pool Fisher–Yates; Discovery, card
potions and Jack of All Trades retain that algorithm. Infernal Blade previously
made one indexed draw and now shuffles its entire eligible attack pool. Orobic Acid
now separately shuffles attack, skill and power pools in native order. Its skill
pool, and Skill Potion's, now includes Shrug It Off. This corrects the legacy
`block` representation without changing card/observation types.

Stoke, Jackpot and Calamity keep sampling with replacement. The factory does not
roll card rarity or upgrades. Callers create fresh owned instances and apply their
explicit upgrade/free-cost rules. Queued generation now carries a fifth, explicit
`distinct` boolean, so restored work preserves the intended sampling method.
Combat snapshots advance to **v15**, run snapshots to **v27**; older private schemas
reject rather than reinterpret continuation data.

Alchemize and Entropic Brew's existing potion generation behavior is validated
against actual repeated factory calls, including Alchemize at full inventory.
No potion factory production change was necessary. The explicit Fire/Block fixture
pool retains its existing restricted behavior; ordinary generated runs use the
complete potion pool. Fixture card generation remains Python Random; typed skill
generation now correctly includes Shrug It Off there as well.

## Validation and package

- Existing Ironclad/colorless/potion tests: **493 passed in 26.56 seconds**.
- Final new focused suite: **125 passed in 4.78 seconds**, including all native
  vectors, base/upgraded callers, skipped/accepted choices, full hands, owned IDs,
  RNG isolation, full potion inventory and JSON restoration. Synthetic queued-work
  tests additionally reject the old arity and a nonboolean distinct flag atomically.
- Independent semantic review: no concrete blockers; **108 new cases passed in
  3.96 seconds** and **21 affected regressions in 2.02 seconds**, before the final
  additional boundary/potion tests. Production code did not change afterward.
- Compatibility: **262 passed in 6.11 seconds** (engine snapshots, simulation,
  headless backends and package layout).
- Broad headless: **2,206 passed in 300.65 seconds** (5 minutes).
- `compileall` and `git diff --check` passed. The extended native oracle builds
  with zero warnings/errors. An initial potion action fixture used the restricted
  default pool; it was corrected to declare the full pool before final broad testing.

Built and installed wheel SHA-256:
`26ad73144bebebf5ee6c78b73b3144c0d74cf16e7f6d7feeb74cc5e02769853c`.
With PYTHONPATH unset, outside the checkout, imports resolve from site-packages.
Installed checks passed all 66 card sequences, 16 boundary cases, 12 potion
sequences and four actual card/potion continuation scenarios.
The authored seed-2 slice completed in 38 commands with 66 HP. The generated
seed-2/right/rest Neow route visited 16 rooms, completed nine combats and lost at
the boss after 198 commands. Both verified JSON restoration throughout; this is
execution/continuation evidence, not native whole-run parity or policy strength.

Work began around 19:44 UTC. Inspection, implementation and review overlapped;
separate phase timings were not recorded. Test durations are above; package and
installed reference checks completed around 19:59 UTC. Final validation and local integration completed around 20:02 UTC
(about 18 minutes total). No user wait or live release step was needed. Scratch outputs
are in `/private/tmp/sts-headless-combat-generation`.

## Next implementation

Bottled Potential's nonempty-pile shuffle, initial/refill Innate/Stratagem/Abacus
ordering and generated-card insertion hooks are the next bounded assignment.
Check Stomp's modifier timing for unselected offers separately from factory RNG.
Entropy's transformation categories/selection RNG, foreign-character Splash and
Kaleidoscope, dependent native combat interactions and a native Act 1 boundary
matrix remain explicit work in the [implementation backlog](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment).
