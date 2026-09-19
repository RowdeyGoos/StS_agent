# Necrobinder cards — 2026-09-19

## Scope and implementation

The cumulative `NECROBINDER_CARDS` catalog extends `REGENT_CARDS` with all 80
ordinary solo Necrobinder cards at both upgrade levels, four starters, Soul and
Sweeping Gaze (86 definitions). Acquired cards run under the existing Ironclad
owner. Forbidden Grimoire and Protector are inventoried Ancient exclusions.
Defect, complete Kaleidoscope/Splash acquisition, playable foreign characters,
higher ascensions and native full-run parity remain separate work.

Definitions and immutable card operations live in `cards/necrobinder.py`,
`cards/necrobinder_effects.py` and `cards/osty_effects.py`. Shared mechanics live in
`core/osty.py`, `powers/necrobinder.py` and `powers/necrobinder_damage.py`; they
extend existing command, hook, choice and catalog mechanisms. No combat projection
or RL encoding was added.

Osty owns serializable HP/max-HP state, including his dead state. Summons grow a
living pet or revive him; attacks consume owner block, pet HP, then owner HP.
Pet attacks separate dealer modifiers from the owner. Doom, Souls, debuff copying,
Ethereal manipulation, delayed summons, first-attack bonuses and per-card play
history use explicit state. The Scythe grows its physical card, including on a
lethal attack, and synchronizes growth to its matching run-deck ID after an action.
Private formats advance to combat v22 and run v34; earlier formats reject.

## Native reference and evidence boundary

Target: **0.107.1 / Steam build 23811903**. Pinned `sts2.dll` SHA-256:
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.

The existing native combat oracle now accepts `necrobinder` and reproduces
[`headless_native_necrobinder_vectors.json`](../../tests/fixtures/headless_native_necrobinder_vectors.json).
Its 88 rows include the two Ancient exclusions. Actual mutable native card
construction and upgrade methods provide costs, targeting, keywords, generation
eligibility and dynamic variables. A fresh oracle invocation reproduced the
retained JSON exactly. The oracle build completed without warnings or errors.

Behavior recipes were checked against decompiled code from that pinned assembly:
Necrobinder card `OnPlay` methods; Osty creation, summon and damage commands;
Doom, Necro Mastery, Haunt, Reaper Form, Sic Em, Danse Macabre, Lethality,
Summon Next Turn and related power hooks; card generation/history and cloning.
Python regressions exercise those recipes. This is direct native metadata evidence
plus source-backed simulated behavior, **not native card/turn execution or full-run
parity evidence**. No live game, profile, save, history or Cloud access was used.

## Review corrections

An independent semantic review found and rechecked these concrete issues:

- Queued summon/damage tasks need an actual pending event, not merely a compatible
  source card or power. Owned context/task receipts now match queued work, are
  consumed once and are cleared on cancellation. Forged Snap/Sic Em and untriggered
  Haunt tasks reject. A legitimate Necro Mastery callback paused by Centennial
  Puzzle/Stratagem restores and resumes identically.
- After-damage callbacks preserve player-power order across Reaper Form, Envenom
  and Monarch's Gaze. Rend includes the added enemy debuffs and effective negative
  Strength; Misery copies temporary Strength once.
- Transformations enter generated-card history while bypassing Arsenal and Pillar
  of Creation generation hooks. Regent history regression expectations were
  corrected; the earlier historical evidence remains unchanged.
- Pending Scythe gains are bounded by their physical card; owning run snapshots
  reject unsynchronized gains. Malformed values raise the public ValueError.
- Confirmed owner death kills Osty after death prevention has had its opportunity.

Compatibility tests also exposed untargeted legacy plays with no enemy roster;
the new before-play hook now accepts that existing simple combat path.

## Validation

- Native inventory: 88 rows reproduced as identical JSON; 86 implemented definitions
  checked against base/upgrade metadata. Every ordinary card exercises choices,
  JSON continuation and three turns at both levels.
- Compatibility: **355 passed in 81.03 seconds** across simulation, engine,
  conformance and data tests.
- Installed package: **343 passed in 30.30 seconds** across the Necrobinder and
  runtime-eligibility tests, plus the subsequently retained pending-Mastery
  regression (**1 passed in 0.23 seconds**). The same added test passed against
  source in 0.25 seconds; no production source changed after packaging.
- `compileall game tests`, whitespace review, current documentation file links,
  and the new guide example passed.
- Full headless suite: **3,386 passed in 391.40 seconds (6m31s)**. The one
  subsequently retained pending-Mastery regression also passed, for 3,387 headless
  cases checked on the final production source. No unresolved review findings remain.

## Package and operational checks

Wheel: `sts_agent-0.1.0-py3-none-any.whl`, SHA-256
`ccf4b2ccfd86bea0d7c9c39804318a15c147c9766fdc977d51f7cb3971dd180e`.
The disposable package is in `/private/tmp/sts-necrobinder-package/`; installed
verification uses `/private/tmp/sts-necrobinder-installed/`. All **175** wheel
headless Python modules match the source bytes. Tests imported the installed
package from outside the source checkout with `PYTHONPATH` removed.

Installed `sts-headless-play` outcomes, with restoration verified after every command:

| Route | Outcome |
| --- | --- |
| `first-slice --seed 2 --rest-choice smith --verify-restore` | Slice complete; 38 commands, four rooms, two combats, 66 HP. |
| `overgrowth-generated --ancient neow --seed 2 --path right --rest-choice rest --verify-restore` | Defeat; 198 commands, 16 rooms, nine combats, 0 HP. |

These are deterministic compatibility smoke routes. Their default catalog remains
restricted; neither route establishes complete foreign acquisition or native parity.

## Timing

Work began at 10:13:03 UTC. Implementation, source inspection and independent
review overlapped; their separate elapsed times were not measured. The first broad
headless run took 389.98 seconds and exposed two instances of the legacy-roster
issue; final validation below supersedes that failed candidate.

Implementation, review, validation and package preparation finished at 10:59:02 UTC
(45m 59s elapsed). No user wait was required.
The final broad validation took 391.40 seconds; compatibility ran concurrently in
81.03 seconds. Installed checks took 30.30 seconds plus the 0.23-second added case.
