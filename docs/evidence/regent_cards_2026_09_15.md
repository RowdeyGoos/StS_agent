# Regent card family — 2026-09-15

## Scope and native evidence

`REGENT_CARDS` extends the explicit Silent catalog with **80 ordinary solo Regent
cards**, both levels, four starters and four generated dependencies: Sovereign
Blade, Minion Strike, Minion Dive Bomb and Minion Sacrifice. Cards execute under an
Ironclad combat owner; no Regent character, multiplayer-only cards, default foreign
acquisition, bridge projection or legacy encoder expansion is added.

Target: **0.107.1 / Steam build 23811903**. Pinned assembly SHA-256:
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
The existing [native oracle](../../tools/native_combat_oracle/README.md), mode
`regent`, reproduces the [90-row metadata fixture](../../tests/fixtures/headless_native_regent_values.json)
byte-for-byte. It invokes actual native metadata and upgrade methods. Two Ancient
entries, Meteor Shower and The Sealed Throne, remain inventoried exclusions.
No live game launch, player profile, save, history or Cloud access occurred.

Pinned IL, rather than older decompiled values, establishes behavioral recipes.
Material changes include Begone→Minion Strike, Charge→Minion Dive Bomb, Astral
Pulse's two hits, Spoils of Battle's Forge then draw, Glow's immediate/next-turn
draw, Guiding Star's immediate draw, and Summon Forth moving blades before Forge.
Arsenal uses generation hooks; Sword Sage adds whole-card replays without a cost
increase. Void Form's base Ethereal is removed by upgrade; both levels grant two
free manual series starting on later turns.

Representative source anchors (method metadata tokens in the pinned assembly):

| Rule | Native method evidence |
| --- | --- |
| Forge creates only if no non-exhausted blade, then improves every blade | Forge `100712407`; damage increment `100697406` |
| Manual Stars payment, autoplay Star-X capture, Chemical X | SpendResources `100706393`, SpendStars `100706395`, AutoPlay `100712167`, ResolveStarXValue `100682114`, Chemical X `100683309` |
| Arsenal generation and Sword Sage replays | Arsenal `100707206`; Sword Sage `100686300`–`100686303` |
| Black Hole paid-series/gain-event triggers, Child of the Stars payment block | `100707225`, `100707227`, `100707261` |
| Sovereign Blade powered Parry block per play | `100710775` |
| Bombardment after setup/side-start, before ordinary auto-preplay | `100709633`; StartTurn `100712573`, RunAutoPrePlayPhase `100712567` |
| I Am Invincible per-instance auto-postplay, before turn-end/flush | `100710205`; EndPlayerTurnPhaseOneInternal `100712557` |
| Generation history, pile entry, then generation hooks | AddGeneratedCardsToCombat `100712223` |

## Implementation and continuation

Stars are owned combat resources, retained across turns. Manual legality checks
energy and Stars together. Fixed-cost cards respect Void Form; Star-X captures and
spends current Stars, and Chemical X increases its effect without extra payment.
Autoplay captures X while spending zero. Child of the Stars runs during payment;
Black Hole fires once per positive gain event or paid card series.

Forge preserves blade identity and damage, including exhausted blades. Sword Sage
changes replay counts on existing and new blades, with native clone exemptions.
Seeking Edge and Parry compose with repeats and target changes. Transformation
replaces an exact card in its existing pile, without a generated-card event.
Arsenal/Pillar and Supermassive count actual generation, including clones and
selected offers, without counting unselected offers or ordinary pile movement.

Shared before-draw and side-start dispatch preserve application order across card
families. Bombardment waits for setup choices. I Am Invincible runs per instance
before Orichalcum readiness is captured. Monarch's Gaze/Envenom and
Reflect/Flame Barrier preserve power order against Artifact and Slippery.
Independent Orbit/Monologue instances, next-turn tutors, draw hooks, optional
choices and delayed effects use owned plain state. Royalties produces a separate
claimable/skippable gold reward bound to its earned amount.

Private snapshots are combat **v21**, run **v33**. New resources, histories,
captured play values, counters and pending work validate on restore. Queued Forge
requires an owning Beat Into Shape play and its captured amount. The default
catalog and fixed legacy encoder vocabulary remain unchanged.

## Validation

[Regent tests](../../tests/headless/test_regent_cards.py) cover native values,
all ordinary base/upgraded cards through choices and three turns, resource and
power interactions, native generation RNG continuation, earned rewards and
malformed snapshot rejection. Independent semantic review found and verified the
Arsenal/Sword Sage, phase/order, Forge ownership and retaliation corrections;
its final bounded pass reported no remaining blockers.

- Broad headless suite: **3,074 passed in 352.74s**. This run began before the
  final ordering corrections and ten additional regressions.
- Final affected checks after those corrections: **1,326 passed in 91.78s**,
  including Regent, Silent, Ironclad, relic combat/run, choices, rewards, draw,
  native combat generation and interactions.
- Independent final Regent check: **303 passed in 23.97s**.
- Simulation/engine/conformance/data compatibility: **355 passed in 77.85s**.
- Installed-wheel Regent plus runtime eligibility: **344 passed in 23.68s**.
- Native oracle build: zero warnings/errors; generated fixture matches exactly.
- `compileall game tests`, diff whitespace and changed-document links checked.
- All **168** packaged headless Python modules match their working source bytes.
- Installed first-slice seed 2/smith: completed, 38 commands, 66 HP, every command restored.
- Installed generated Act 1 seed 2/right/rest/Neow: 198 commands, 16 rooms and
  nine completed combats; defeat at the boss, every command restored. This is
  executable continuation evidence, not a victory or native parity claim.

Wheel SHA-256:
`508a7f9cfafeca35077753c4361a49efa1cac1306e2d68844e36d88a2d93a230`.
Artifact: `/private/tmp/sts-headless-regent-native/package/sts_agent-0.1.0-py3-none-any.whl`.

Work began at 19:53:52 UTC. Implementation, source inspection and independent
review overlapped with validation; final test wall times are reported above.
Packaging and installed checks completed at approximately 20:25 UTC. There was
no user-readiness wait. The batch uses the dedicated headless worktree and is
merged locally into `codex/headless-integration`; main and remotes are unchanged.

## Remaining work

Next: Necrobinder's 80 ordinary cards and Doom/Souls/Osty dependencies, then
Defect's 80 cards and orb/Focus rules. Complete native Kaleidoscope/Splash
acquisition follows all four foreign catalogs. Actual native card/selector and
enemy-turn composition, plus the Act 1 boundary comparison gate, remain open.
Metadata execution and Python continuation are not full native gameplay parity.
See the [implementation backlog](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment).
