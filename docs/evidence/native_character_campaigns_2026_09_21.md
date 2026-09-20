# Native campaigns for the four additional solo characters

Eight complete boosted campaigns now compare native execution with the Python
headless engine through victory: Silent, Regent, Necrobinder and Defect at A0 and
A10. This extends the [character startup evidence](playable_characters_2026_09_20.md).

## Captures and scope

All A0 cases use Overgrowth seed 1; all A10 cases use Underdocks seed 4. Both
continue through Hive and Glory. A0 fights Ceremonial Beast, The Insatiable and
Queen; A10 fights Waterfall Giant, Knowledge Demon, Aeonglass and Queen, including
the final double boss.

| Character | Ascension | Rooms | Combats | Combat actions | Selection calls | Capture |
| --- | --- | --- | --- | --- | --- | --- |
| Silent | 0 | 48 | 26 | 793 | 181 | [JSON](native_campaign_silent_a0_2026_09_21.json.gz) |
| Silent | 10 | 49 | 27 | 805 | 173 | [JSON](native_campaign_silent_a10_2026_09_21.json.gz) |
| Regent | 0 | 48 | 26 | 895 | 48 | [JSON](native_campaign_regent_a0_2026_09_21.json.gz) |
| Regent | 10 | 49 | 27 | 944 | 56 | [JSON](native_campaign_regent_a10_2026_09_21.json.gz) |
| Necrobinder | 0 | 48 | 26 | 541 | 0 | [JSON](native_campaign_necrobinder_a0_2026_09_21.json.gz) |
| Necrobinder | 10 | 49 | 27 | 777 | 3 | [JSON](native_campaign_necrobinder_a10_2026_09_21.json.gz) |
| Defect | 0 | 48 | 26 | 687 | 0 | [JSON](native_campaign_defect_a0_2026_09_21.json.gz) |
| Defect | 10 | 49 | 27 | 790 | 3 | [JSON](native_campaign_defect_a10_2026_09_21.json.gz) |

Total: **388 rooms, 212 combats, 6,232 combat actions and 464 selection calls**.
Selections are additional decisions within recorded play/end-turn actions.

The native fixture uses the pinned game DLL with SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
Each compressed capture retains its fixture source hashes, compiled fixture
identity, dependency pins, measured build/execution times and cleanup outcome.
[Runner usage](../../tools/native_combat_oracle/README.md#other-character-native-campaigns)
describes the existing queue-runtime command and character argument.

Native starting decks, relics, generated encounters, reward pools and gameplay
callbacks run normally. The sole authored gameplay override is setting HP and
maximum HP to 1,000,000 before Neow; A10's native Neow heal then sets HP to 800,000.
The bounded policy picks legal cards, targets, rewards, purchases and event choices;
it can skip unwanted rewards without removing them from the offered pool.
Combat selections record the actual native options and returned indices. The
selector answers at least one card when allowed because the native test API can
pass a minimum of zero even when the corresponding real UI forbids skipping.

These are native TestMode executions in the existing isolated fixture, with
in-memory persistence, uploads disabled, explicit combat phase dispatch and
presentation-only localization/texture substitutes. They are not live desktop
playthroughs. Each owned empty user directory was removed; presentation listeners
were disposed. Native victory serialization is exercised, while the repeated
JSON restore comparisons below exercise Python persistence, not native disk saves.

## Compared boundaries

The replay applies the recorded native decisions through ordinary headless actions
and checks room entry, room completion, combat starts and every captured nonterminal
combat action. Lethal actions are followed by the recorded reward/run boundary.
Checks include HP/max HP, block, energy, enemy identity/HP/block, ordered card piles
and upgrades/enchantments, gold, deck, relics, potions, reward offers and selected
purchase prices. All 15 available named run/player RNG counters are compared at
A0 and A10. Stars, Osty's HP/max HP/block, orb capacity and ordered passive/evoke
values, and active player power amounts are also compared. Osty's native combat
ID serves only to align enemy identities with stable headless slots.

Every replay command is also executed from a JSON-restored copy. Legal actions
and the entire resulting serialized state must match the original continuation,
including pending choices. Restoring once before each command replaces a redundant
second clone of the same result; continuation coverage is retained.

These checks do not compare every internal native field, complete RNG state or
every enemy power amount directly. They establish agreement for these full routes
and selected decks, not every seed, card permutation or normal-HP policy victory.
Multiplayer and alternate modes remain outside scope. Public observation/RL
adapters for the added characters remain separate work.

## Fidelity corrections

- Random orb and Necrobinder power targets follow native enemy execution order
  while retaining stable targeting slots. Orb damage identifies the player as its
  dealer, allowing Hand Drill to trigger when an orb breaks enemy block.
- Drain Power still upgrades eligible discarded cards and consumes its selection
  RNG after its damage wins combat.
- Ordinary monster move rolls occur after enemy-side Doom and turn-end effects.
  Monsters killed by Doom do not consume another move roll. Completed moves keep
  an owned pending-roll record through later reactive draw choices.
- Forced stuns retain their required execution if triggered after the monster has
  already acted. Queen's Enrage can transition immediately at that pending roll,
  matching its native state semantics when Doom kills Torch Head Amalgam.
  Lagavulin Matriarch's sleep threshold follows the corrected roll timing.

Private combat/run snapshots advance to **v46/v67**. Restore rejects detached or
inconsistent pending-roll ownership and older versions. Focused tests cover a
paused multi-enemy turn, malformed ownership, a reactive forced stun and the
Queen/Doom transition. Independent semantic review found no remaining blocker
after these corrections.

## Validation

The eight campaign regressions are in
[`test_native_character_campaigns.py`](../../tests/headless/test_native_character_campaigns.py).
All eight passed against the final code: Necrobinder A0/A10 and Defect A10 passed in 78.00 seconds, followed by the other five in 169.48 seconds
(**247.48 seconds total**). These are focused reruns after correcting the Queen
transition; earlier failed exploratory runs are not counted as acceptance.

Additional focused validation passed: 621 monster/continuation/native behavior
checks in 32.36 seconds and 624 character/source-binding/simulation checks in
6.18 seconds. After the final Queen correction, all 246 Glory/continuation checks
passed in 7.99 seconds; independent review also ran the three focused continuation
cases in 0.08 seconds. All nine retained Ironclad campaign routes replayed against
their native boundaries in 6.39 seconds, without repeating per-command JSON clones.

The [15-mode native regression report](native_character_campaign_regressions_2026_09_21.json)
records fresh executions of the current harness whose parsed results exactly
match their retained baselines, including previous campaigns and item/status
probes. Historical evidence keeps its original hashes; current-source assertions
bind the fresh report to the original result and capture identities.

Accepted eight-campaign native builds took **13.52 seconds** total and native
execution **22.29 seconds**. The 15 baseline reruns took **25.73 seconds** building
and **34.86 seconds** executing. These are measured fixture times, excluding
Python replay, debugging and review. Compileall, diff checks, source bindings and
local documentation links also passed. Overall implementation time was not recorded.
