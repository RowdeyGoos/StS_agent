# Starter-card upgrade source checks, 2026-09-13

The first HF-13 slice implements ordinary Ironclad Strike at 6 damage and Strike+
at 9 damage, both costing 1 energy and targeting one enemy. The permanent upgrade
is limited to one level for this card. These numbers were checked against the
pinned game assembly using static metadata/IL inspection. Combat, persistence and
replay tests exercise the Python implementation; no native game execution or
live differential comparison was performed.

## Source identity and method

- Game: v0.107.1, Steam build 23811903, macOS arm64; see the
  [pinned manifest](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json).
- Assembly: `sts2.dll`, SHA-256
  `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
- Repository base: `73348735724e80d5898a28aa0786f4f0d39f6cf6`.
- Retained reference read: `/private/tmp/sts-current-release-final/references/sts2.dll`.
- Toolchain: existing .NET SDK 9.0.303, `PEReader`, and the repository's
  [metadata names](../../bridge/Sts2AgentBridge/tools/Sts2AgentBridge.Verifier/MetadataNames.cs)
  and [IL decoder](../../bridge/Sts2AgentBridge/tools/Sts2AgentBridge.Verifier/IlDecoder.cs).

A scratch copy of the existing [static scanner](event_interactions_2026_09_09/scan.cs)
was restricted to exact selected type names and their nested types, instead of its
ordinary event-namespace selection. It retained the assembly hash, symlink and
size guards. It did not load or execute game types. Selected roots were
`MegaCrit.Sts2.Core.Models.Cards.StrikeIronclad`, `DefendIronclad`, `Bash`, followed
by `MegaCrit.Sts2.Core.Localization.DynamicVars.DynamicVar` and
`MegaCrit.Sts2.Core.Models.CardModel`. Only Strike and its immediate shared helpers
supported the initial implementation claim. Defend and Bash were inspected for
the subsequent batch described below, using the same retained output.
The scanner build passed with no warnings or errors. Raw selected IL remains in
`/private/tmp/sts-headless-hf13-native/il.json` and `helpers.json` while scratch
storage exists. It is not a runtime fixture or a committed game-source dump.

The method tokens below are decimal metadata tokens for this exact assembly;
offsets are decimal IL offsets. They provide reproducible inspection anchors with
any metadata reader without depending on those temporary files.

## Inspected anchors

| Method | Token | Relevant offsets and finding |
| --- | --- | --- |
| `StrikeIronclad..ctor` | 100693405 | Offset 1 supplies energy cost 1 to `CardModel..ctor(Int32,CardType,CardRarity,TargetType,Boolean)` at 6. |
| `StrikeIronclad.get_CanonicalVars` | 100693407 | Offset 0 supplies 6, converted to Decimal at 1 and passed to `DamageVar..ctor` at 7. |
| `StrikeIronclad.OnUpgrade` | 100693409 | Gets Damage at 6; supplies 3 at 11 and calls `DynamicVar.UpgradeValueBy(Decimal)` at 17. No cost mutation appears in this override. |
| `DynamicVar.get_BaseValue` | 100694850 | Loads `_baseValue` at 1. |
| `DynamicVar.UpgradeValueBy` | 100694863 | Reads BaseValue at 2, adds the argument with Decimal addition at 8 and writes BaseValue at 13. Thus the ordinary damage becomes 6 + 3 = 9. |
| `CardModel.get_MaxUpgradeLevel` | 100682151 | Returns 1 at offsets 0–1; Strike has no override. |
| `CardModel.UpgradeInternal` | 100682239 | Increments CurrentUpgradeLevel at 7–17, dispatches OnUpgrade at 23, then recalculates dynamic variables at 34. |
| `StrikeIronclad.OnPlay` | 100693408 | Dispatches the async play body below. |
| `StrikeIronclad+<OnPlay>d__5.MoveNext` | 100710839 | Requires `CardPlay.Target` at 26; reads damage BaseValue at 52; calls `DamageCmd.Attack` at 57, `FromCard` at 63 and `Targeting(Creature)` at 79. |

## Implemented boundary and limits

The original implementation at `7ca5f77` used an opt-in `strike_upgrade_v1`
profile in the combat adapter. That unreleased profile was retired in the
subsequent [game-engine refactor](../HEADLESS_ENGINE.md). The native source anchors
above remain unchanged; they support card values, not the refactor's other rules.

[Card definitions](../../game/headless/cards/ironclad.py) own Strike's base and
upgraded values. [Run deck rules](../../game/headless/run/deck.py) preview and
upgrade one persistent instance between rooms, preserving its ID and position
without RNG or ID allocation. The direct operation is not a rest-site action or
proof that an arbitrary game upgrade source is legal.

The [direct regression cases](../../tests/headless/test_game_engine.py) cover
same-ID mutation among duplicates, preview immutability, base/upgraded damage and
cost, typed legal actions, discard/reshuffle, branch isolation, invalid-operation
atomicity, JSON continuation and two combats with the same permanent deck.
An injected three-level card also proves that resolved cost/effect changes do not
require projection, encoder or per-feature profile registration.

The legacy public backend keeps its base content and rejects upgraded combat
launches. Public upgraded-card integration is deferred; no new actor/checkpoint
compatibility or full-game protocol capability is claimed by these direct tests.
Enemy rules, RNG, damage/status ordering, relic/enchantment hooks and the remaining
card pool retain the reduced simulator's evidence level. This isolated source
check does not establish their native parity, a full run, upgrade selection UI,
reward upgrades or training readiness for upgraded cards.

## Defend and Bash follow-up

Inspected for the basic-upgrade batch based on `a550ce8`. The retained assembly's
SHA-256 was recomputed and matched the pin above and the scanner output. This
reuses the existing bounded static scan; no native types were loaded or executed.
Both classes directly inherit `CardModel` and have no `get_MaxUpgradeLevel`
override, so the inspected one-level limit also applies to them.

| Method | Token | Relevant offsets and finding |
| --- | --- | --- |
| `DefendIronclad..ctor` | 100691449 | Cost 1 at offset 1, passed to `CardModel..ctor` at 6. |
| `DefendIronclad.get_CanonicalVars` | 100691452 | Block 5 at 0, passed to `BlockVar..ctor` at 7. |
| `DefendIronclad.OnUpgrade` | 100691454 | Gets Block at 6; supplies 3 at 11; `UpgradeValueBy` at 17 makes block 8. No cost change. |
| `DefendIronclad+<OnPlay>d__7.MoveNext` | 100709842 | Gets the owner's creature at 18–23 and Block at 29–34, then calls `CreatureCmd.GainBlock` at 46. No enemy selection. |
| `Bash..ctor` | 100690899 | Cost 2 at offset 1, passed to `CardModel..ctor` at 6. |
| `Bash.get_CanonicalVars` | 100690901 | Damage 8 at 8 → `DamageVar..ctor` at 15; Vulnerable 2 at 23 → `PowerVar<VulnerablePower>..ctor` at 29. |
| `Bash.OnUpgrade` | 100690903 | Damage +2 at 11/17; Vulnerable +1 (`Decimal.One`) at 33/38. No cost change. |
| `Bash+<OnPlay>d__5.MoveNext` | 100709572 | Requires a target at 28–43; reads Damage.BaseValue at 59, builds the targeted attack at 64–86 and awaits execution (113/198). Only then reads Vulnerable.BaseValue at 232 and calls `PowerCmd.Apply<VulnerablePower>` at 250. |

Thus Defend+ gains 8 block for 1 energy; Bash+ deals 10 damage before applying
3 Vulnerable for 2 energy. The only production changes are their additional
`CardSpec` levels in [Ironclad definitions](../../game/headless/cards/ironclad.py).
The shared effects and upgrade/persistence mechanisms are unchanged.

[Direct card tests](../../tests/headless/test_card_upgrades.py) distinguish base
and upgraded block, exact enemy targeting, damage-before-Vulnerable ordering and
energy costs. They also cover rejected targeting, preview and second-upgrade
atomicity, duplicate identity, RNG/allocator conservation, discard/reshuffle,
JSON continuation and persistence through two completed combats for each card.
The follow-up Strike in the Bash case is a regression for the existing simulator's
Vulnerable interaction; this inspection does not certify the full native power
lifecycle, damage modifiers, lethal-target behavior, relic hooks or upgrade-source
legality. Public upgraded-card integration remains deferred.
