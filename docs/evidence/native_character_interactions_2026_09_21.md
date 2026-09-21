# Focused character interaction audit — 2026-09-21

The bounded audit adds **four native scenarios at 35 recorded boundaries** and
fixes two Defect fidelity gaps. It uses the existing isolated native oracle and
shared headless rules. It does not add a character-specific engine or a large
seed/difficulty/inventory cross-product.

## Audit and selected comparisons

The starting evidence comprised native card metadata, local gameplay/continuation
tests, eight starter/refined-starter and exclusive-potion probes, and eight full
A0/A10 campaigns for the four added characters. Those campaigns cover the decks
actually selected by their policy. They do not exercise every exclusive relic or
all 320 ordinary foreign cards in combination.

The audit inspected the shared character relic hooks, orb callers, cost modifiers
and their existing tests against pinned native source. It selected mechanisms
with local tests but no equivalent focused native comparison:

| Character | Native scenario | Result |
| --- | --- | --- |
| Silent | Helical Dart after a Shiv, Speed Potion, Artifact, a second Shiv, then ordered temporary-power expiry | Two distinct temporary Dexterity wrappers expire. Artifact blocks Helical Dart's first loss; Speed Potion removes five, leaving two Dexterity. Matches. |
| Regent | Galactic Dust and Mini Regent across spends of 7, 5, 20 and 1 Stars, a turn-reset callback, then Child of the Stars/Juggernaut killing the last enemy during spending | Block thresholds and remainder, once-per-turn Strength, power-before-relic ordering and ending suppression match. |
| Necrobinder | Bookmark discount, absolute this-turn cost 2, another discount, setter expiry, then actual Capture Spirit play | Until-played reductions respect modifier chronology, survive the setter's expiry and clear after the play. Selection counters/suffixes match. Ivory Tile is installed but its three-energy threshold is not exercised by this case. |
| Defect | Glass/Lightning with Gold-Plated Cables and Infused Core, natural orb phase, Loop, Focus −4, eviction and four random channels | Exposed the direct-passive count and RNG seed discrepancies; both are fixed and all recorded values/choices/suffixes match. |

The [compressed capture](native_character_interactions_2026_09_21.json.gz) retains
fixture sources, compiled/runtime identities, timings and successful owned-directory
cleanup. Native `sts2.dll` SHA-256 is
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
All scenarios use seed 2 and A0; they isolate mechanisms rather than difficulty
variation. Native actions and callbacks run on authored active combat state under
TestMode. No live UI, user profile, disk save or Cloud data is involved.

## Corrections

**Gold-Plated Cables applies only to natural orb turn phases.** Native OrbQueue
consults the passive-count modifier during its natural start/end phases. Direct
`OrbCmd.Passive` calls do not consult it. Headless previously doubled all front-orb
passives, including Loop, Emotion Chip, Darkness and Tesla Coil. Natural phases
now emit `orb_phase_trigger`; direct calls retain one trigger. Glass recalculates
its passive after each decay; nonpositive values do not decay further. Infused
Core adds its Lightning bonus after the negative-Focus clamp.

**The random-orb stream uses the native enum's seed name.** The native property
`RunRngSet.CombatOrbGeneration` resolves `RunRngType.CombatOrbs`, seeded with
`combat_orbs`. Headless had used its logical key `combat_orb_generation` as the
salt. The logical key and owned stream remain stable; only the seed salt changes.
The probe compares actual generated orb types and all three tracked streams'
next values, not just request counters.

Private combat/run snapshots advance to **v47/v68**. Natural orb tasks retain
emission receipts and validate their phase and orb identity. Older snapshots
reject rather than silently resume different passive or random-orb semantics.
The random-service restore also rejects a stream seeded for the wrong owner.

## Comparison strength and limits

Each step compares HP, block, energy, Stars, target HP, active player power amounts,
tracked physical cards' resolved costs and piles, ordered orb passive/evoke values,
Galactic Dust's remainder and three RNG counters. Final RNG suffixes are compared.
Each step executes both normally and from a JSON-restored copy; complete Python
snapshots and legal actions must agree. A separate focused test exercises the
four direct-passive callers. Another resumes a natural orb phase's detached
Gremlin Horn/Stratagem choice and rejects forged phase work and obsolete schemas.

The fixtures invoke named phase callbacks explicitly; they do not claim native
whole-turn dispatch, all generated-card piles, all enemy powers or every internal
relic flag. In particular, Mini Regent's inert used flag at combat ending is not
compared; native sets it before a suppressed Strength application, and both
engines reset it before another relevant turn/combat. This is not an unresolved
observed gameplay divergence. Full campaigns retain their separate evidence.

More character-specific card/item compositions remain possible verification work,
including relic thresholds not hit here, other callback orders and low-HP/death
branches not selected by these probes. No untested combination is marked complete
by its family name. Use a concrete missing mechanism or reproduced mismatch to
choose further focused work. Normal-HP policy victories, multiplayer and alternate
modes remain outside this acceptance gate.

## Validation

The seven focused comparison/identity/caller/continuation tests pass, including
JSON restoration and adversarial pending-work checks. Independent semantic review
confirmed both production corrections and independently ran the four native
comparisons in 0.11 seconds. Final validation also passed:

- All eight A0/A10 character campaign replays, with per-command JSON continuation:
  **242.06 seconds**.
- **459** RNG, combat generation, draw and native interaction checks: **3.51 seconds**.
- **13** source-binding, starter/potion and enemy-continuation checks: **1.20 seconds**.
- All **320 existing** Defect/character tests passed in the affected invocation
  (54.16 seconds including two new test-fixture failures). Those two fixture
  expectations/setup checks were corrected; the final seven focused tests then
  passed in **0.13 seconds**. This is not recorded as an initially clean broad run.
- Nine retained Ironclad routes matched native boundaries in **6.22 seconds**,
  without repeating the per-command JSON clones.

Compileall and diff checks passed. The entire repository suite was not rerun.

The changed shared harness was freshly run against **23 retained baselines**:
its previous 15 campaign/interaction modes plus all eight added-character native
campaigns. Every parsed result matches its original retained capture exactly.
The [regression report](native_character_interaction_regressions_2026_09_21.json)
binds those results and original file hashes to the current source and compiled
identities. Existing captures were not rewritten or assigned new source hashes.

The accepted four-scenario build took **1.65 seconds** and native execution
**1.51 seconds**. The 23 baseline builds took **36.58 seconds** total and executions
**55.28 seconds**. These measured times exclude Python replay, implementation and
review; an overall implementation timer was not recorded.
