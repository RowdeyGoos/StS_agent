# Overgrowth encounters and branching route, 2026-09-13

The direct engine now offers solo Fuzzy Wurm, solo Mawler and paired Nibbits in
addition to the existing solo Nibbit and weak-slime encounters. A restricted
four-combat route connects them with two independent branch decisions and a rest
site. This is progress toward Act 1, not a complete act or native map generator.

## Source identity and scope

Target v0.107.1, Steam build 23811903; assembly SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
[Build manifest](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json).
Implementation base: `b7a0412` on `codex/headless-integration`.

Reused the bounded metadata scanner from the
[starter-card source check](strike_upgrade_2026_09_13.md), with its hash, symlink,
file-size and instruction-count guards, running under .NET 9.0.303. No native
model was instantiated or executed. Selected roots under `MegaCrit.Sts2.Core`:
`Models.Monsters.FuzzyWurmCrawler`, `Mawler`, `Nibbit`, and
`Models.Encounters.FuzzyWurmCrawlerWeak`, `MawlerNormal`, `NibbitsNormal`, including
nested move bodies. Scratch source: `/private/tmp/sts-headless-overgrowth-native/il.json`
while retained. RandomBranchState evidence is reused from the
[earlier encounter check](slice_combat_content_2026_09_13.md).

Tokens and IL offsets below are decimal. AscensionHelper's non-modifier branch
supplies the A0 values. Higher difficulty remains unsupported.

| Native member | Token | Verified behavior / anchors |
| --- | --- | --- |
| FuzzyWurmCrawler HP / damage | 100687734–100687736 | HP 55–57 (A0 constants at 3); Acid Goop 4 (at 3). |
| Fuzzy move state machine | 100687739 | First attack → Inhale at 129–131; Inhale → second attack at 136–138; second attack → first attack at 143–145. Starts first attack at 171–173. |
| Fuzzy AcidGoop / Inhale bodies | 100708317 / 100708319 | Attack reads damage at 137 and executes at 200. Inhale applies self Strength 7 at 159–178. Existing Python cycle already matched; full-cycle cases now verify accumulating damage 4,11,11,18… and no move-selection rolls. |
| FuzzyWurmCrawlerWeak composition | 100690038 | One mutable FuzzyWurmCrawler at 0–16. |
| Mawler HP / Rip / Claw | 100688064–100688067 | HP 72; Rip and Tear 14; Claw 4. Max HP equals minimum. |
| Mawler state machine | 100688068 | Starts Claw (local 3) at 238–240. Each move follows RAND at 143–162. Branches are Rip, Roar, Claw at 167–204, all weight 1; repeat types 2,3,2 respectively. |
| Mawler move bodies | 100708463 / 100708465 / 100708467 | Claw uses hit count 2 at 33–34; Rip executes one attack at 81; Roar applies Vulnerable 3 to targets at 136–155. |
| RandomBranchState.GetStateWeight | 100681568 | Repeat type 2 rejects an immediate repeat; type 3 excludes a previously performed move. Roar is therefore once per combat. |
| RandomBranchState.GetNextState | 100681567 | Calls NextFloat at 39 even if only one move has nonzero weight, then walks authored branch order. |
| MawlerNormal composition | 100690125 | One mutable Mawler at 0–16. |
| NibbitsNormal composition | 100690149 | Creates front model with IsFront=true at 17–18, puts it in front at 30–42, then creates the back model at 48–69. Neither receives the solo flag. |
| Nibbit initial branch / predicates | 100688144 / 100688151–100688153 | Solo chooses Butt at 149–177. Non-solo adds Hiss with !IsFront at 179–194, Slice with IsFront at 199–214. Predicates read these flags at 16. |
| Nibbit follow-ups | 100688144 | Slice→Hiss at 219–221, Butt→Slice at 226–228, Hiss→Butt at 233–235. Flags only determine opening; losing an ally does not restart the cycle. |

Nibbit A0 HP 42–46, Butt 12, Slice 6/block 5 and self Hiss Strength 2 use the
previously verified scalar/source anchors. Each Nibbit buffs itself. Front and
back stay in slots 0/1, including after death; no retargeting or slot compaction
was added. Existing monster fields already represent every future transition,
so opening roles require no additional saved flag.

Mawler now uses one Python `random()` draw per transition and native authored
branch order. Eligible successors are equally weighted. This corrects the
previous `choice()` consumption and successor ordering, changing seeded Mawler
trajectories. It does not implement native RNG algorithms, run-wide stream
ownership or bitwise seed parity. The legacy Mawler regression now injects
boundary rolls rather than overriding the obsolete `choice()` operation.

## Authored route and compatibility

`RunEngine.ironclad_slice(route="overgrowth")` traverses:

- Solo Nibbit → choose slimes then Fuzzy, or Fuzzy then slimes.
- Rest/Smith → choose Mawler or paired Nibbits.
- Final hallway rewards → `slice_complete`.

That gives four combats, four path combinations and four hallway reward bundles.
Starting inventory, Burning Blood, potions, card rewards and rest rules reuse the
existing engine. No elite rewards or act completion are fabricated. This route
selects from explicit supported content; it is not a native easy/hard pool sampler.
Shrinker, remaining normal encounters, elites, bosses and other room families
remain implementation work.

The graph and visited history are already serialized in run v2; combat v3 keeps
its existing state shape. Restore requires matching game-rule implementation,
as before. Mawler additionally rejects unknown current moves and the impossible
combination of a pending Roar with an already-used Roar flag. Historical public
fixtures and release evidence were not repinned. The default `first-slice` route
retains its two-combat behavior; new CLI `--route` and `--path` options expose the
longer example without another runner or entry point.

## Acceptance

Tests verify complete Fuzzy cycles, paired Nibbit opening/self-buff/survivor
behavior, Mawler branch boundaries, once-only Roar, forced rolls, player Vulnerable
lifetime, twelve-turn continuations for each added encounter, invalid snapshot
atomicity, and rejected sibling/replayed map choices. Every combination of the
two branches and Rest/Smith completes four combats with exact continuation after
each command. A loss produces neither rewards nor slice completion. CLI output
reports the restricted route scope and completed combat count.

Independent review found no blockers. It passed 173 existing headless/CLI tests
and verified 1,669 JSON-restored transitions across 24 seed/path/rest combinations;
all completed four combats.

Final affected suite: **636 passed in 29.95 seconds**, covering headless,
simulation, analysis, engine, headless backends, content, package/lazy-import and
headless CLI tests. The focused encounter/route suite passed 35 tests in 1.95 seconds.
Compileall, diff whitespace and relevant local links passed.

Built wheel SHA-256:
`2b9c18cdafc10417c751c6948b07ffab358f3bd372873e96a3c1932420e977a9`.
Installed in the disposable no-RL environment, then ran outside the source tree
with `PYTHONPATH` unset. Seed 2 Overgrowth left/Rest completed in 69 commands with
74 HP; right/Smith completed in 78 with 29 HP. Both finished four combats with
161 gold, 14 cards and two potions used, verifying restoration at every command.
The default first-slice check still completed in 38 commands with 66 HP, 127 gold
and 12 cards.

Elapsed work was approximately ten minutes: source inspection and implementation
occupied the first four minutes; test expansion, independent review and focused
validation overlapped the next three; documentation, the final suite and package
checks followed. No user wait or live launch was required.
