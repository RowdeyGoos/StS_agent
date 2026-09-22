# First headless treasure room — 2026-09-13

This batch implements HF-36's first ordinary A0 chest: leave closed, open for
gold, take or skip the relic, then continue the authored Act 1 route. It also
implements Circlet as the repeatable exhausted-pool fallback. Evidence is static
native inspection and headless execution; no native UI, profile or save access.

## Source anchors

Source: game v0.107.1, Steam build 23811903, existing pinned `sts2.dll` reference.
SHA-256: `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
The existing bounded metadata scanner checked the assembly identity and read
selected room, reward, relic and RNG methods without executing game code. Scratch
outputs were under `/private/tmp/sts-headless-treasure-native/`. The tokens below
identify the inspected methods independently of those temporary files.

| Method / metadata token | Verified behavior |
| --- | --- |
| `TreasureRoom.EnterInternal` async body, 100701083 | Starts relic picking on room entry. |
| `TreasureRoomRelicSynchronizer.BeginRelicPicking`, 100681282 | For each eligible player, roll rarity, apply tutorial override or pull a relic from the shared grab bag; use the fallback if the pull returns null. One player ordinarily receives one offer. |
| `RelicGrabBag.PullFromFront`, 100666206 | Removes the selected entry from its deque when offered, before acquisition. |
| `RelicFactory.get_FallbackRelic`, 100695719 | Returns Circlet. |
| `NTreasureRoom.OpenChest` async body, 100704634; `TreasureRoom.DoNormalRewards`, 100666921 | Opening executes normal rewards before presenting the relic collection, then extra reward hooks. |
| `OneOffSynchronizer.DoTreasureRoomRewards` async body, 100706217 | Ordinary A0 gold comes from `NextInt(42, 53)` and is automatically granted on opening. Treasure-suppression, Poverty and Spoils Map have separate branches. |
| `Rng.NextInt(int,int)`, 100667298; `MegaRandom.Next(int,int)`, 100667269 | Integer interval uses the upper-exclusive range, giving 42–52 gold. |
| `NTreasureRoom._Ready`, 100676156; `OnProceedButtonPressed`, 100676159 | Initial button uses Proceed; the ordinary non-skip path directly departs. Once opened, single-player relic skip also departs. UI animation/skip delay is not simulated. |
| `Circlet.get_IsStackable`, 100683321; `Player.AddRelicInternal`, 100696092 | Circlet allows repeats. Acquisition appends separate relic instances to the player's collection. Circlet has no custom pickup effect. |

Native exhausted pools are not ordinary empty chests: the former use Circlet;
empty treasure can result from generation-suppression hooks. This batch does not
implement those modifiers or pretend that they are pool exhaustion.

## Rules and ownership

Immutable `treasure/catalog.py` declares the restricted fruit pool, Circlet fallback
and gold range. `run/treasure.py` handles room decisions through shared relic
acquisition. `run/treasure_validation.py` validates private continuation data.

The relic is sampled on entry, excluding owned fruit relics and earlier treasure
offers. The offer is consumed even if the chest is left closed or the relic is
skipped. Gold uses a separate stream and is drawn/granted only on opening. Opening
and claiming cannot be replayed. A claim names the exact treasure ID, and the
pending state records the exact acquired item ID. Restoring does not regenerate
stock, grant gold or reapply the relic's max-HP/healing effect.

The depleted pool belongs to this restricted treasure source. It does not model
native shared/player grab bags across shops, elites and events. Uniform fruit
sampling and named Python RNG streams are authored. Native rarity weights,
tutorial overrides, multiplayer allocation, suppression modifiers and extra
reward hooks remain open. The fallback can be acquired repeatedly with unique
owned IDs; other relics retain duplicate-definition rejection.

The Act 1 route now passes through treasure after its third combat, before its
first camp. Smaller routes are unchanged. Private run snapshots advance to
`headless_run_state_v6`, including the chest catalog, counter and depletion data;
old private run versions reject. Combat v4 and public reduced fixture schemas
remain unchanged. Circlet is a fallback, not an ordinary elite reward-pool entry.

## Validation and installed result

- Focused treasure tests: **36 passed in 1.25 s**. Covers gold timing/bounds,
  leaving closed or open, all fruit pickups, declined-offer depletion, repeated
  Circlets and exact removal of one duplicate, stale/repeated claims, entry failure
  rollback, malformed snapshots, RNG isolation, next-combat persistence and both
  authored Act 1 demo branches.
- Compilation passed: `python -m compileall -q game tests`.
- Final integration: **806 passed in 17.01 s**, covering headless rules, simulation,
  analysis, engine, headless backends, content, lazy imports, package layout and
  headless CLI. Existing shop and combat consumers still pass.
- Independent review found no blocking issues. Additional reviewer probes covered
  438 restored decisions across 240 chest visits, separate Circlet instances,
  unopened/open skipping and malformed/illegal command rejection.
- Built and installed the wheel outside the repository. Wheel SHA-256:
  `c0c2296ddece9edfb64523fbd7600a48ab691fdbdc0612771bc3b30c31455fc8`.
  Installed `sts-headless-play` ran with `PYTHONPATH` unset and exact restore
  verification at every command:

| Demo | Result |
| --- | --- |
| `--route overgrowth-act1 --seed 2 --path left --rest-choice rest --verify-restore` | **Act 1 complete**, 11/94 HP, 180 gold, five combats, Mango from treasure, one shop purchase/removal, 121 commands. Vantom reward departure records the explicit act-completion record. |
| Same route/seed/rest, `--path right` | Defeat at Vantom, 0/104 HP, 232 gold, five combats, Mango plus elite Pear, 111 commands. |
| Default first-slice, seed 2 | Slice complete, 66 HP, 127 gold, two combats, 38 commands. |

The successful left path is a normal seeded headless playthrough without injected
HP, gold, rewards or forced combat victory. It demonstrates a win on the authored
restricted five-fight route, not full native Act 1 map/content/RNG fidelity or a
full-game victory.

The turn began at 14:45:40 UTC; implementation, review, tests, package installation
and smoke runs were complete by 14:54:19 UTC (about 8 minutes 39 seconds). Review
ran concurrently; no separate review-only duration was recorded. Final integration
tests took 17.01 seconds. Documentation and local integration followed; no user
wait was needed.

Next: a source-verified ordinary Overgrowth event (HF-39), as specified in the
[current assignment](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment).
