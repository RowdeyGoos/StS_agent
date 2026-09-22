# Playable solo characters — 2026-09-20

The shared headless engine now supports Silent, Regent, Necrobinder and Defect
campaigns alongside Ironclad on pinned build 0.107.1. Character selection changes
starting inventory/resources, ordinary pools and owner-dependent generation;
it does not select a second engine. Multiplayer-only cards remain excluded.

## Implemented scope

| Character | Starting HP | Starting deck size | Starter |
| --- | ---: | ---: | --- |
| Ironclad | 80 | 10 | Burning Blood |
| Silent | 70 | 12 | Ring of the Snake |
| Regent | 75 | 10 | Divine Right |
| Necrobinder | 66 | 10 | Bound Phylactery |
| Defect | 75 | 10 | Cracked Core; three base orb slots |

All start with 99 gold before Ancient effects. The added content comprises 32
exclusive relics, four refined starters, twelve exclusive potions and Wraith Form,
The Sealed Throne, Forbidden Grimoire and Biased Cognition. Existing character card
families reuse the same owned choices, Stars/Forge, Osty, orb and power rules.
Rewards, merchant stock, potion generation, player relic bags, events, Neow,
Kaleidoscope/Splash and character-dependent Ancient gifts select the correct owner
pool. Shared chest bags remain shared. Osty does not count as an event pet.

Combat/run private snapshots advance to v45/v66. New retained-cost discounts,
character identity, emitted item/Doom callbacks and removal rewards contain plain
values and owned IDs. Old private versions are rejected. The CLI uses
`--character` on generated routes and avoids toggling already-selected cards when
completing a multiple-card choice.

## Independent reference evidence

[Native capture](native_characters_2026_09_20.json.gz) uses the same pinned assembly
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
Eight named cases invoke real starter/refined-starter callbacks on authored active
combats. The four base-starter cases also execute all twelve exclusive potions
through native `UsePotionAction`. The comparisons include HP, draw modifiers,
Stars, Osty, orb capacity/order, powers, generated cards and upgrades, with Python
JSON continuation before each action. These are callback/potion probes, not native
run-start shuffles or native whole-campaign comparisons.

The accepted native invocation took 1.870 seconds including a 1.641-second build.
Its disposable empty user directory was removed. No game profiles, saves or Cloud
state were read. The capture retains exact compiled/source/dependency identities.
It also reruns every older item-status case unchanged and records a fresh shared
36-case enemy-turn regression against the retained result. Historical captures
are unchanged. The staging script change only adds the new character probe file;
unchanged campaign implementations keep their historical source bindings.

An independent source review checked character-exclusive items and shared hook,
pool, persistence and terminal ordering. It found and verified fixes for Bookmark
absolute-cost layers, separate Helical Dart/Speed Potion expiration, Emotion Chip
previous-turn HP costs, Infused Core with negative Focus, power-before-relic
ordering, and Book Repair Knife after the complete Doom/death callback batch.
Final bounded review found no remaining production blocker.

## Integration and regression checks

Each added character completed a seeded, boosted-HP three-act Python run on A0
from Overgrowth and A10 from Underdocks: eight victories through the Architect.
Runs use legal actions and real combat resolution; HP 1,000,000 is the only
assistance. JSON checkpoints cover room boundaries and every hundred commands.
The earlier smoke trajectories completed 26 or 27 combats. This proves
integration under those paths, not native full-run agreement or policy strength.

The dedicated character/native suite passed 35 tests in 51.87 seconds, including
those eight campaigns; the subsequently added emitted-Doom-receipt regression
also passed. Affected card/item/event/native regressions passed 1,892 tests in
44.99 seconds. The additional pool/Ancient pass had 703 passing tests; its 15
failures came from legacy fixture owners without a config field and were corrected
with the existing Ironclad default; the affected pool and character rerun passed
76 tests in 2.08 seconds. Compileall and diff checks also passed.

A broad legacy headless run was stopped at six minutes (2,985 passing tests). Its
five failures were historical fixture-source assertions, corrected by binding
unchanged campaign modules to their retained hashes and the separately rerun
character harness to its new evidence. That incomplete broad run is not recorded
as a full-suite pass. Final validation uses affected checks, not another campaign
matrix solely for a documentation/hash change. The Defect CLI smoke completed
128 commands with JSON verification and reached ordinary defeat after seven
combats; it does not claim a normal-HP victory.

## Remaining limits

Full native campaigns for the four new characters, broader seed/path comparisons
and their external public-observation/RL adapters remain separate acceptance work.
Progression-specific unlock histories, multiplayer and alternate modes remain
outside the declared profile. Existing native full-campaign captures are Ironclad
evidence and are not relabeled as evidence for the other characters.
