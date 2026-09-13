# Headless full-game implementation backlog

Assessment date: 2026-09-12. Gameplay sources inspected at
`73348735724e80d5898a28aa0786f4f0d39f6cf6`; ongoing live-bridge changes were outside
this assessment. This is a source-and-test assessment and implementation guide,
not a new gameplay validation result. No gameplay suite, game launch, installation
inspection or profile access was performed for this documentation change.

The headless environment has a substantial deterministic execution and research
pipeline, but only a small structural gameplay model. Completing its route does
not simulate completing Slay the Spire 2. The largest remaining work is faithful
rules, persistent items and card changes, run generation and progression, content
coverage, and independent conformance evidence. Another learning algorithm is not
required to close those gaps.

[Status](STATUS.md) owns current capability claims; [roadmap](../ROADMAP.md) owns
priorities. This document owns the headless implementation task breakdown. Update
task status and dependencies here when implementation lands. Preserve the dated
assessment below as a baseline; do not silently turn its historical test references
into validation of changed code.

## Implementation progress after the assessment

- **2026-09-13 — complete A0 Overgrowth encounter roster:** all 22 native pool
  entries and 29 monster types are implemented, including all three elites/bosses,
  mixed groups, summons, revival and required powers/status cards. Every encounter
  has combat/restore/outcome coverage. Native map and encounter generation, later
  acts and ascension variants remain open.
  [Evidence and roster](evidence/overgrowth_roster_2026_09_13.md).
- **2026-09-13 — Aroma of Chaos:** mandatory one-card transformation/upgrade
  choices, automatic zero/one resolution and exact continuation are implemented.
  Permanent transforms preserve position, allocate a fresh unupgraded card and
  exclude the original from a restricted Ironclad pool. The right Act 1 branch
  uses Aroma. Broader pools and transformation hooks remain open.
  [Evidence](evidence/aroma_of_chaos_2026_09_13.md).
- **2026-09-13 — first ordinary event:** native Jungle Maze Adventure now offers
  Solo Quest (18 damage then larger gold) or Join Forces (smaller gold, no damage),
  with entry-time offers, exact event identities, terminal defeat and continuation.
  The authored Act 1 route visits it before treasure; shared-game primitives remain
  separate from the old event fixtures. Native float/RNG, multiplayer and event
  generation are still open. [Evidence](evidence/first_event_2026_09_13.md).

- **2026-09-13 — first treasure room:** closed/open/claimed chest decisions,
  automatic 42–52 A0 gold on opening, optional fruit relic, persistent offer
  depletion and repeatable Circlet fallback are implemented. The Act 1 route
  visits a chest after its third fight; all decisions restore exactly. Sampling
  and the treasure-only pool are authored; full global pools and modifiers remain
  HF-36 work. [Evidence](evidence/first_treasure_2026_09_13.md).

- **2026-09-13 — first shop:** repeatable card/relic/potion purchases, one card
  sale, cancelable permanent deck removal with A0 escalation, sold-out state,
  affordability/inventory checks and JSON continuation are implemented. The Act 1
  route can visit or bypass the shop. Stock and basis-point RNG are authored;
  full pools, discounts, restock and pickup selectors remain HF-35 work.
  [Evidence](evidence/first_shop_2026_09_13.md).
- **2026-09-13 — first boss and explicit act completion:** Vantom A0, Slippery,
  generated unplayable Wounds, Sword Boomerang, Impervious/Offering/Fiend Fire
  and their upgrades,
  restricted boss rewards and `ActCompletion` are implemented. The new authored
  `overgrowth-act1` route adds a second camp and boss to the existing four fights.
  [Evidence and limits](evidence/first_boss_2026_09_13.md). This covers representative
  HF-17/18/23/31/37 work, not a complete native Act 1 or later-act progression.

- **2026-09-13 — first elite and pickup relics:** Byrdonis A0 and Territorial
  now run on an optional Overgrowth path, with elite gold, one restricted relic
  reward and permanent Strawberry/Pear/Mango pickup effects. All six paths retain
  four combats; this is still `slice_complete`, not an Act 1 finish.
  [Source evidence and limits](evidence/first_elite_2026_09_13.md).

- **2026-09-13 — M1 combat content completed for its declared pool:** all four
  reward-card upgrades and Slimed's draw are implemented; solo Nibbit and the four
  included slime variants now have native source checks and full-cycle/branch
  tests. Corrected small/medium/small encounter slots, medium Twig's equal-choice
  and two-attack limit, and combat-ending effect handling. Tests acquire, smith
  and play every reward upgrade through the run with JSON continuation.
  [Evidence and limits](evidence/slice_combat_content_2026_09_13.md) distinguish
  these source-checked rules from native seed parity or live conformance.
- **2026-09-13 — M1 implemented with restricted content:**
  `RunEngine.ironclad_slice()` now plays Ironclad A0 through Nibbit → rewards →
  rest or smith → Overgrowth slimes → rewards → `slice_complete`. It includes
  native starter inventory, Burning Blood, Fire/Block Potions, independent reward
  claims/skips, persistent card upgrades and JSON continuation at every decision.
  This delivers representative work in HF-04/07/08/09/24/26/28/31/32/34; none of
  those broad tasks is thereby complete for all content. See the
  [engine guide](HEADLESS_ENGINE.md) for commands/ownership and the
  [source evidence](evidence/first_vertical_slice_2026_09_13.md) for native anchors
  and explicit sampling/content restrictions. The CLI is `sts-headless-play`.
  Full act progression, native generation, other items and broader selectors
  remain open. Completing this authored slice is not native run victory.
- **2026-09-13 — independent game engine:** [game/headless][game package] now owns
  combat, cards, monsters, statuses, persistent deck instances, RNG and private
  continuation, with authored map and basic room/reward operations. It imports no
  projections, contracts, encoders, bridge or training packages. `CombatEnv` consumes
  these combat rules through its existing research interface. See the
  [engine guide](HEADLESS_ENGINE.md) for architecture, extension examples and limits.
- **HF-13 is partial:** Strike+ deals 9 damage at cost 1; Defend+ gives 8 block
  at cost 1; Bash+ deals 10 damage then applies 3 Vulnerable at cost 2. Direct tests
  cover preview, duplicate identity, targeting/order, JSON continuation and
  persistence through two fights. The four reward cards now also have their
  upgrades; other card families and general temporary modifiers remain open. The
  [pinned source check](evidence/strike_upgrade_2026_09_13.md) owns the native evidence.
- **HF-14 is partial:** ordinary draws stop at 10 cards before any unnecessary
  reshuffle, preserving overflow, identities and RNG on blocked draws. Direct
  continuation and shared combat regression tests cover the rule. See the
  [draw source check](evidence/hand_limit_2026_09_13.md). Draw hooks and the remaining
  card-zone keywords are still open.
- The earlier `strike_upgrade_v1` adapter experiment at `7ca5f77` is retired.
  Gameplay changes no longer need per-feature profiles or projection changes.
  Accepted reduced backend artifacts retain their original behavior and identities.
- HF-04/08 have working foundations, not complete full-game coverage. HF-06 has
  ordered immediate card effects, not a general trigger/continuation system.
  Cancelable single-card rest-site smithing is implemented; event/reward and
  more complex combat selectors remain HF-16/31/33/34 work. The test-only direct
  between-room upgrade operation does not establish source legality.

## Scope and definition of complete

The first target follows [TARGET.md](TARGET.md): standard single-player Ironclad,
initially Ascension 0, against the pinned Slay the Spire 2 `v0.107.1`, Steam build
`23811903`. The [build manifest][build] owns the binary identity. Full-game coverage
means every decision and mechanic reachable in the declared mode, unlock profile,
act selection and difficulty, including neutral, generated, curse, status, special
and other-character content if it can enter that Ironclad run.

The repository does not yet have a complete target-content census or a finalized
unlock profile. Therefore an exact total of missing cards, relics, encounters or
branches cannot honestly be supplied from the reduced registry. HF-01 closes that
inventory gap. Until then, this is a complete workstream breakdown with explicitly
identified discovery dependencies, not a claim that every target model has already
been enumerated. The existing event inventory supplies a useful partial census.

A complete simulator for that scope must:

- Initialize a declared run and progress through all its acts, rooms, rewards and
  intermediate choices to the game's actual victory, defeat or abandonment.
- Implement all reachable content and interactions with correct legality, effect
  order, persistent changes, random distributions and relevant seed semantics.
- Expose player-visible state, observable history and every legal decision without
  exposing hidden draw order, future outcomes, world RNG or seed-derived features.
- Support deterministic reset, action replay, isolated branching and snapshot
  continuation at every supported decision boundary.
- Have named, independent evidence for rules and generation, plus complete-run
  integration checks. Test agreement with itself is insufficient for fidelity.
- Run through the maintained Python API and `sts-headless` workflow with accurate
  outcomes, failures and reproducible artifacts.

Faithful reduced-content full runs are an intermediate milestone. Excluding a
reachable unsupported card from a reward pool changes the game and cannot count
as full target coverage. Highest-difficulty coverage is a later gate, HF-38.
Other characters, co-op and alternate modes have separate breadth tasks HF-52–54;
they are not implied by completion of the initial Ironclad target.

## Assessed implementation at the September 12 baseline

This table records the pre-refactor assessment at `7334873`. Its source links name
the original entry points; several now re-export canonical game classes. Use the
progress notes above and current task ownership below for new implementation.

| Area | Implemented in the inspected checkout | Limit and implementation consequence |
| --- | --- | --- |
| Public backend interface | [Contract][contract] has typed observations, legal candidates, decision bindings, stale/rejected responses, evidence manifests and a separate `PolicyView` | Four actionable phase families: combat, reward, map and room. Eleven candidate kinds. Shops, items and selectors cannot be added by changing only the backend. HF-03/44/45/46 |
| Fixture playback | [Fixture backend][fixture] replays a small committed corpus and supports cursor snapshots | Playback is not counterfactual simulation. Do not count these fixtures as gameplay implementation |
| Combat adapter | [CombatV0Backend][combat-adapter] wraps `CombatEnv`, projects a public subset, maps candidates, accepts persistent decks and restores by action replay | `combat_v0` evidence only. It rejects upgraded persistent cards. No relic, potion or general selection interface. HF-09/13/16/24/26 |
| Reduced run composer | [ReducedRunBackend][composer], version `reduced_headless_v3`, composes combat → reward → map → rest/event → combat/reward → route completion | One configured encounter scenario is reused at every combat node. No acts, bosses, shop or true run lifecycle. HF-28–43 |
| Persistent state | [WorldState][state] stores HP/max HP, gold, ordered master-deck instances, map nodes/history, pending decision, continuation queue, terminal result, IDs and RNG | No character/difficulty/act state, relics, potions, encounter history, generation pools or generalized card modifiers. HF-04 |
| Combat persistence | `CombatLaunchSpec` carries HP/max HP and ordered card instances; `CombatResolution` binds to the issued launch | Only final HP returns from combat. Temporary combat cards stay out of the master deck, but permanent combat changes and item counters cannot survive. HF-09 |
| Randomness | [GameRandomService][rng] provides seeded Python MT19937 streams, isolated names, operation counts and snapshots | Structural stream names are `combat_launch`, `reward_offer`, `event_effect`; legacy combat uses a shared Python RNG internally. Target-game parity of the algorithm, seed derivation and draw order is unverified. HF-05 |
| Snapshots | [WorldSnapshotCodec][snapshots] serializes private state; composed restore checks manifests, phase ownership, provenance and accepted action history | Combat restore replays the combat prefix; composed restore also verifies outer history. Correctness infrastructure exists, but fast state cloning and full-game state coverage do not. HF-08/49 |
| Cards | [Card implementations][cards] and [reduced content][content] contain Strike, Defend, Bash, Pommel Strike, Shrug It Off, Iron Wave, Body Slam and Slimed | Seven persistent rewardable definitions; Slimed is combat-generated. No upgraded execution, power cards, general card keywords or full card pool. HF-13–18 |
| Enemy content | [Enemies][enemies] implement SimpleEnemy, Nibbit, Shrinker Beetle, Fuzzy Wurm Crawler, Mawler and four Leaf/Twig Slime size variants | SimpleEnemy is a synthetic smoke enemy. Eight named game enemy variants are partial combat research content, not a complete first-act pool. HF-19–23 |
| Combat scenarios | [Scenario adapter][scenarios] combines ten encounter selectors with two deck presets; the factory offers easy and partial hard Overgrowth pools and fixed encounters | Reduced runs admit only `simple__starter` and `nibbit__starter`; standalone combat breadth is not reduced-run breadth. HF-20/21/30 |
| Combat rules | Energy, block, Strength, Vulnerable, Shrink, turn cycling, multi-hit attacks, stable enemy slots, draw/discard/exhaust, Slimed generation | No general effect queue, trigger system, power lifecycle, summons, selections or items. `Deck.draw` has no hand-cap rule while the default discrete encoder accepts ten slots. HF-06/11–16/19 |
| Maps | Two fixed templates: `two_combat_rest` has two combats and a rest/event branch; `short_rest_path` has one combat and a rest | No procedural topology, room distributions, map modifiers, unknown-room resolution or act transitions. HF-29/30/37 |
| Rewards | Two tables: 25 gold with Strike/Defend/Bash; 35 gold with the four sequencing cards. Opening shuffles the entire fixed list once; choose/skip and proceed are supported | Fixed gold, no rarity/pool sampling, no relic/potion drops. Gold must be claimed and the card reward resolved before proceeding. These are fixture rules. HF-31/32 |
| Rooms/events | Rest heals a fixed 15 HP, capped at max HP. `quiet_cache` grants 20 gold; `cool_spring` heals 8 HP | No smithing, optional rest actions or target event catalog. At full HP, `cool_spring` reaches an explicit unsupported boundary because the fixture cannot express its no-effect case. HF-34/39–43 |
| Run outcomes | Terminal defeat and structural `route_complete`; the latter exposes `RunOutcome.VICTORY` while retaining the distinct non-policy reason | No actual final-boss/ending validation. Preserve the distinction in all future statistics and training labels. HF-37/46/47 |
| Runner and collection | [Episode runner][runner], baseline choosers, spawned workers, budgets, cancellation and deterministic matched panels | The generic runner stops on `WAITING`; the maintained collector factory admits only `reduced_headless` and three baseline chooser kinds. Extend existing seams for new rules. HF-07/47 |
| Data and actor | [Trajectories][trajectories] separate policy, target and audit streams; datasets bind accepted sources; variable-candidate encoder/model and deterministic CPU cloning exist | Encoder vocabularies, contract/content fingerprints and feature widths are frozen. The actor is a structural imitation smoke, not a full-run learner. HF-45/46 |
| Conformance | Contract/replay/metamorphic/public-boundary tests, a synthetic common-subset comparator, bounded named gold-transfer evidence/corpus tools | No broad target-game rules or generation certification. Comparison currently omits many identities, intents, costs, piles and ordering details. HF-02/48 |

### Evidence that can and cannot be reused

The current tests directly encode deterministic continuation, exact legality,
rejected-action atomicity, public/private separation, snapshot tamper rejection,
worker cancellation and artifact integrity. Relevant entry points are listed in
the validation map below. Their presence and the recorded acceptance establish
what was designed and previously checked; no new pass count is claimed here.

The [actor acceptance record][actor-evidence] documents an integrated September 5
cloning smoke on tiny structural datasets. Its successful training and persistence
do not establish strategy or game fidelity. [Card documentation][card-notes] and
[hard-pool documentation][enemy-notes] cite earlier wiki-based content research;
those are implementation references, not pinned-build differential acceptance.

The existing [gold case][gold-spec] checks a *conditional transfer* of 25 or 35
gold plus preservation of HP/max HP/deck count. It does not check reward generation,
card identity, complete world correspondence or RNG. The recorded
[September 4 live attempt][gold-evidence] encountered an unsupported gold amount,
issued zero gold-claim POSTs, and produced no eligible effect comparison. Do not
describe that result as a successful live gold-transfer conformance test.

Recent live bridge event, shop and item coverage is useful for selecting native
reference cases. It does not mean those rules exist in `game/engine/`. The
[event research map][event-map] covers 68 types and 105 branch groups, with source
references in its retained inventory; it is not an executable headless event engine
or a complete inventory of every gameplay content family.

## How an agent should pick up a task

Tasks were **open at the assessment**; progress notes and task status identify
subsequent partial implementation. “Extend” includes adding missing
behavior to an existing subsystem; it does not imply starting that subsystem over.
HF-01, HF-02 case design, HF-10 and the HF-14 hand-cap investigation can start from
the current checkout. HF-51 is a conditional backend experiment, not a prerequisite
for every Python change.

1. Read [AGENTS.md](../AGENTS.md), check the current checkout, then read the chosen
   task and its linked sources/tests. Recheck its status against code before acting.
2. Select one observable slice. Dependencies mean the portions required by that
   slice, not completion of every sibling content ticket. Implement one real caller
   through game state, rules, direct commands and relevant continuation.
3. Establish exact rules from the pinned build or accepted evidence. Where a value,
   timing rule or reachable content ID is unknown, record that uncertainty and run
   the smallest applicable source inspection or controlled experiment. Do not copy
   Slay the Spire 1 behavior or infer native rules from a Python fixture.
4. Implement gameplay inside `game/headless/`, following the owner map below.
   Preserve existing research behavior when migrating shared rules. Public adapters
   are downstream work, not a prerequisite for adding a card or mechanic. Do not
   edit frozen fixture rules to add gameplay or repin historical evidence.
5. Run the task's focused checks and affected consumers. For public information,
   protocol, RNG or persistence changes, apply the independent semantic review and
   integration requirements in AGENTS.md. Documentation alone needs document checks.
6. Record implementation, focused evidence, remaining cases and available elapsed
   times in the change summary. Mark the completed task/slice here, update Status
   only where capability meaning changes, and retain substantial native evidence
   under `docs/evidence/`.

For a content task, use a concrete instance such as `HF-18/<definition_id>` or
`HF-43/<event_id>/<branch_id>`. Before implementation, fill in the exact IDs,
reachable pool, difficulty variants, effect dependencies and reference cases from
HF-01. Keep the instance in the single coverage inventory; do not create a new
plan/handoff document for every card. A family is complete only when every in-scope
inventory row is covered or explicitly excluded by the declared target.

### Current implementation owners and sequencing

The game-first order is **rules and content → run progression → public adapter →
encoding/data/training**. HF-03 and HF-44–47 are consumer integration tasks. They
must not become prerequisites for completing a game-rule slice. References to
Contract or Actor/data acceptance below apply when that separate integration is
selected; direct game acceptance comes first. Native evidence and gameplay
correctness remain required for each claimed rule.

| Tasks | Primary implementation destination | Direct acceptance entry point |
| --- | --- | --- |
| HF-04/08/09 | `game/headless/run/state.py`, `run/engine.py`, `run/snapshots.py`, `core/snapshots.py` | Owned run/combat state, JSON continuation and isolated branches |
| HF-05–07/10–12 | `game/headless/core/`, `powers/`; add resolution modules with their first caller | Ordered effects, suspended choices, RNG and rejection behavior |
| HF-13–18 | `game/headless/cards/`, `core/deck.py`, `core/actions.py` | Construct an instance, resolve its legal action and inspect game state |
| HF-19–23 | `game/headless/monsters/`, `encounters/` | Seeded encounter and exact move/turn sequence |
| HF-24–27 | Add `game/headless/relics/` or `potions/` with the first implemented item | Acquire/use an item and verify its hooks and persistent state |
| HF-28–38 | `game/headless/run/`, `map/`; add shop/content modules with their first caller | Traverse an authored/generated route and assert run outcomes |
| HF-39–43 | `game/headless/events/` and shared game selections | Resolve a named event branch including its child choice and continuation |
| HF-03/44–47 | Existing `game/backends/`, `contracts/`, actor/data/training consumers | Adapt completed game capabilities without reimplementing their rules |
| HF-01/02/48–50 | Coverage inventory, independent cases and engine tests/benchmarks | Measured coverage, native fidelity and performance |

HF-51 is still a conditional native-backend experiment; HF-52–54 extend the game
scope. For public integration, replace the fixed reduced-run consumer's rule
ownership with an adapter over `RunEngine`. Keep its old synthetic fixtures frozen
until then. There must not be two evolving implementations of each new rule.

The initial direct cases are in `tests/headless/test_game_engine.py`. Add tests by
content/rule family as those grow. A content feature should normally touch its
owning definition/rule, direct test and coverage record. Update a private state
codec only when the mechanic adds persistent state. No per-card profile, public
fingerprint, encoder vocabulary or bridge package is required.

### Shared acceptance requirements

Every gameplay task must add an observable legal path and its meaningful edge case,
preserve invalid-action atomicity, and support continuation at any new decision.
Validate legal-action **completeness** as well as rejection of illegal actions.
RNG consumption follows the target's domains and ordering; independent streams
are appropriate only where the target is independent. When integrating consumers,
also verify stale request rejection and that hidden-state changes do not alter the
policy view before producing a player-observable difference.

Extend the bounded failure vocabulary when necessary. Unsupported behavior must
stop explicitly; exceptions, infinite effect loops and representation overflow
must not be converted into a normal loss, victory or successful room completion.
An artificial transition budget is truncation, not natural defeat. These common
checks are part of each task, not a reason to run the entire suite on every edit.

### Validation map

The named groups below identify **existing starting tests**, not a fixed acceptance
matrix. Add a focused test beside the affected subsystem when no case exists.

| Group | Existing test locations |
| --- | --- |
| Direct game | `tests/headless/test_game_engine.py`: content, ownership, legality, maps/rooms/rewards, RNG, snapshots and dependency boundary |
| Contract | `tests/contracts/test_headless_v0.py`, `tests/conformance/test_headless_v0_contract.py`, `tests/conformance/test_headless_v0_public_boundary.py`, `tests/conformance/test_headless_v0_capabilities.py` |
| State | `tests/engine/test_headless_state.py`, `test_random_service.py`, `test_headless_snapshots.py` in the same directory |
| Combat | `tests/simulation/test_basic.py`, `test_cards.py`, `test_encounters.py`, `test_integrated_workstreams.py`; `tests/backends/headless/test_combat_v0_backend.py`, `test_combat_candidates.py`, `test_combat_projection.py`, `test_combat_v0_characterization.py` |
| Content | `tests/content/test_reduced_v0.py`, `tests/backends/headless/test_scenarios.py` |
| Progression | `tests/engine/test_map_rules.py`, `test_reward_rules.py`, `test_room_rules.py`; `tests/backends/headless/test_reduced_run_backend.py` |
| Replay | `tests/conformance/test_headless_v0_replay.py`, `test_headless_v0_metamorphic.py`; `tests/runtime/test_episode_runner.py` |
| Differential | `tests/differential/test_common_public_subset.py`, `test_reward_gold_conformance.py`, `test_conformance_evidence.py`, `test_conformance_corpus.py` |
| Actor/data | `tests/agents/test_headless_encoding.py`, `test_headless_candidate_policy.py`; `tests/data/test_headless_trajectory.py`, `test_headless_policy_dataset.py`; `tests/training/test_headless_behavior_clone.py` |
| Operation | `tests/cli/test_headless.py`; `tests/training/test_headless_rollout.py`, `test_headless_benchmark.py`, `test_headless_matched_panel.py`, `test_headless_reporting.py`; `tests/test_lazy_public_api.py`, `test_package_layout.py` |

For example, a new upgrade using existing effects needs a direct card regression
and relevant continuation/ownership checks. Projection and encoding tests apply
when those consumers change, not for each new definition. Use the existing
environment: `PYTHONPATH=. python3 -m pytest -q <selected test paths>`. Follow
AGENTS.md for the scope of final integration. Do not launch the game or rebuild
the bridge solely for documentation or ordinary headless content work.

## Delivery order

| Milestone | Observable completion | Main tasks |
| --- | --- | --- |
| M0: trusted first mechanic | One named combat transition has independent expected legality, effects and post-state against the pinned target | HF-01/02 and necessary game rules in HF-04–17; evaluate HF-51 only if it could change backend direction |
| M1: persistent gameplay slice — implemented, restricted content | Start a declared run; use a real card upgrade, one relic and one potion; finish two encounters with exact persistent effects and replay | Representative HF-04–17, HF-24/26/28/31/32/34; evidence and limits above |
| M2: full-length reduced-content run | Traverse the target act structure, representative rooms and bosses to an actual ending, with explicit restricted-content labeling | HF-19–43 as required by the selected slice, plus HF-08/48 |
| Consumer integration | Expose completed game capabilities through public choices, collection and training | HF-03/44–47 after the corresponding game rules stabilize |
| M3: complete Ironclad A0 scope | Every reachable inventory row and decision family is implemented, all identified divergences resolved, full-run conformance accepted | All required HF-01–50 work for A0; no silent pool exclusions |
| M4: target difficulty | Verified highest standard Ironclad difficulty and every applicable modifier/variant pass the same gates | HF-38 and affected content/conformance cases |

This ordering does not supersede live-bridge priorities in ROADMAP.md. M2 does not
require every card to exist, and M1 does not require a general framework for every
event. Each milestone must state its content restriction and evidence scope.

## Task index

Entries remain open unless their task body records completion or a partial slice.
Dependencies and acceptance cases are in the linked task.

| ID | Feature |
| --- | --- |
| [HF-01](#hf-01--establish-the-target-content-and-rules-inventory) | Establish the target content and rules inventory |
| [HF-02](#hf-02--add-usable-differential-fixtures-for-named-mechanics) | Add usable differential fixtures for named mechanics |
| [HF-03](#hf-03--evolve-the-decision-contract-for-the-first-new-gameplay-slice) | Evolve the decision contract for the first new gameplay slice |
| [HF-04](#hf-04--extend-persistent-state-for-real-runs) | Extend persistent state for real runs |
| [HF-05](#hf-05--match-target-rng-algorithms-domains-and-consumption) | Match target RNG algorithms, domains and consumption |
| [HF-06](#hf-06--introduce-ordered-effects-and-trigger-resolution) | Introduce ordered effects and trigger resolution |
| [HF-07](#hf-07--suspend-and-resume-nested-decisions) | Suspend and resume nested decisions |
| [HF-08](#hf-08--snapshot-every-full-game-decision-and-support-isolated-branches) | Snapshot every full-game decision and support isolated branches |
| [HF-09](#hf-09--preserve-all-combat-produced-run-changes) | Preserve all combat-produced run changes |
| [HF-10](#hf-10--distinguish-unsupported-rules-from-engine-defects) | Distinguish unsupported rules from engine defects |
| [HF-11](#hf-11--complete-damage-block-hp-and-terminal-semantics) | Complete damage, block, HP and terminal semantics |
| [HF-12](#hf-12--implement-status-and-power-lifecycles) | Implement status and power lifecycles |
| [HF-13](#hf-13--execute-upgraded-and-modified-card-instances) | Execute upgraded and modified card instances |
| [HF-14](#hf-14--complete-card-zone-draw-and-hand-limit-behavior) | Complete card-zone, draw and hand-limit behavior |
| [HF-15](#hf-15--extend-card-costs-play-legality-and-targeting) | Extend card costs, play legality and targeting |
| [HF-16](#hf-16--support-decisions-inside-card-resolution) | Support decisions inside card resolution |
| [HF-17](#hf-17--verify-and-finish-the-existing-eight-card-definitions) | Verify and finish the existing eight card definitions |
| [HF-18](#hf-18--implement-all-remaining-reachable-card-content) | Implement all remaining reachable card content |
| [HF-19](#hf-19--generalize-enemy-behavior-and-combat-entity-lifecycle) | Generalize enemy behavior and combat entity lifecycle |
| [HF-20](#hf-20--verify-the-existing-overgrowth-enemy-slice) | Verify the existing Overgrowth enemy slice |
| [HF-21](#hf-21--complete-normal-encounters-across-every-target-act) | Complete normal encounters across every target act |
| [HF-22](#hf-22--implement-all-target-elite-encounters) | Implement all target elite encounters |
| [HF-23](#hf-23--implement-all-target-boss-encounters) | Implement all target boss encounters |
| [HF-24](#hf-24--add-relic-inventory-lifecycle-hooks-and-the-starter-relic) | Add relic inventory, lifecycle hooks and the starter relic |
| [HF-25](#hf-25--complete-reachable-relic-content-and-interactions) | Complete reachable relic content and interactions |
| [HF-26](#hf-26--add-potion-inventory-use-discard-and-replacement) | Add potion inventory, use, discard and replacement |
| [HF-27](#hf-27--complete-reachable-potion-definitions-and-generation-rules) | Complete reachable potion definitions and generation rules |
| [HF-28](#hf-28--initialize-declared-runs-and-starting-choices) | Initialize declared runs and starting choices |
| [HF-29](#hf-29--generate-and-expose-target-maps) | Generate and expose target maps |
| [HF-30](#hf-30--select-encounters-events-and-room-outcomes-from-real-pools) | Select encounters, events and room outcomes from real pools |
| [HF-31](#hf-31--generate-real-combat-and-room-rewards) | Generate real combat and room rewards |
| [HF-32](#hf-32--resolve-mixed-rewards-and-nested-pickup-effects) | Resolve mixed rewards and nested pickup effects |
| [HF-33](#hf-33--apply-permanent-deck-changes-and-modifiers) | Apply permanent deck changes and modifiers |
| [HF-34](#hf-34--implement-actual-rest-site-options) | Implement actual rest-site options |
| [HF-35](#hf-35--implement-shops-and-repeatable-purchases) | Implement shops and repeatable purchases |
| [HF-36](#hf-36--implement-treasure-and-remaining-non-event-room-families) | Implement treasure and remaining non-event room families |
| [HF-37](#hf-37--implement-act-transitions-and-real-run-termination) | Implement act transitions and real run termination |
| [HF-38](#hf-38--implement-difficulty-and-declared-unlock-variants) | Implement difficulty and declared unlock variants |
| [HF-39](#hf-39--add-a-real-event-state-machine-and-ordinary-choices) | Add a real event state machine and ordinary choices |
| [HF-40](#hf-40--compose-event-selectors-card-offers-and-deck-mutations) | Compose event selectors, card offers and deck mutations |
| [HF-41](#hf-41--run-event-combat-and-resume-its-parent) | Run event combat and resume its parent |
| [HF-42](#hf-42--model-custom-event-interactions-and-terminal-branches) | Model custom event interactions and terminal branches |
| [HF-43](#hf-43--complete-the-event-and-ancient-catalog) | Complete the event and ancient catalog |
| [HF-44](#hf-44--expose-sufficient-public-run-state-and-observable-history) | Expose sufficient public run state and observable history |
| [HF-45](#hf-45--extend-encoding-and-policies-without-dropping-legal-choices) | Extend encoding and policies without dropping legal choices |
| [HF-46](#hf-46--carry-full-run-semantics-through-datasets-and-artifacts) | Carry full-run semantics through datasets and artifacts |
| [HF-47](#hf-47--run-the-new-environment-through-existing-apis-and-cli) | Run the new environment through existing APIs and CLI |
| [HF-48](#hf-48--accept-complete-run-fidelity-and-close-coverage-gaps) | Accept complete-run fidelity and close coverage gaps |
| [HF-49](#hf-49--measure-and-improve-full-runbranching-performance) | Measure and improve full-run/branching performance |
| [HF-50](#hf-50--deliver-a-reproducible-supported-simulator-package) | Deliver a reproducible supported simulator package |
| [HF-51](#hf-51--test-whether-reusing-native-game-rules-shortens-the-fidelity-work) | Test whether reusing native game rules shortens the fidelity work |
| [HF-52](#hf-52--add-every-other-single-player-character) | Add every other single-player character |
| [HF-53](#hf-53--add-cooperative-multiplayer-semantics) | Add cooperative multiplayer semantics |
| [HF-54](#hf-54--add-alternate-modes-and-maintain-later-game-builds) | Add alternate modes and maintain later game builds |

## Foundation tasks

### HF-01 — Establish the target content and rules inventory

- **Depends on:** none; exact profile-sensitive reachability remains explicit until
  the declared profile is settled.
- **Implement:** one versioned inventory of character setup, acts, room kinds,
  encounters, enemies, cards/upgrades/modifiers, powers, relics, potions, events,
  ancients, rewards, RNG domains and difficulty changes. Record stable target ID,
  source/build reference, reachable pools, rule dependencies, simulator entry point,
  implementation/evidence status and concrete task instance. Reuse [game catalog] and
  the [event inventory][event-inventory]; do not reinterpret the latter's old bridge
  gap labels as headless coverage.
- **Accept:** every inspected registry member is accounted for; missing or unknown
  semantics are explicit. Produce a coverage query grouped by family/status and
  named first-slice IDs. Changing the target build invalidates affected coverage.
  Check registry uniqueness, dependency references and source identities in Content
  and Differential tests. Do not commit game binaries or raw source dumps.

### HF-02 — Add usable differential fixtures for named mechanics

- **Depends on:** HF-01's selected mechanic; fixture design can begin immediately.
- **Implement:** extend [conformance tools][conformance] and [common comparator]
  with pre-state/action/post-state cases that establish entity correspondence,
  complete legal choices and relevant ordered effects. Start with one existing
  card against one existing enemy; separately cover a reward transfer. Expected
  results must come from independent pinned rules/observations, not the simulator's
  computed post-state. Preserve provenance and the old narrow gold case unchanged.
- **Accept:** a deliberately wrong amount, target, order or missing legal candidate
  fails with a bounded field-level difference; an absent fact remains unobserved.
  Distinguish synthetic tests, source-derived expectations and observed native
  comparisons. New native collection follows the live guide and current authority.
  Tests: Differential, Contract, selected Combat/Progression cases.

### HF-03 — Evolve the decision contract for the first new gameplay slice

- **Status:** deferred consumer integration; not a prerequisite for core gameplay.
- **Depends on:** implemented game rules for the selected slice and HF-01/02 evidence.
- **Implement:** adapt `RunEngine` and its direct game commands through the existing
  backend family, retiring evolving rule ownership in the fixed reduced composer.
  Use a versioned evolution of [contract] supporting the slice's new
  state/action semantics, initially upgraded card records or a suspended selection.
  Define candidate identity, reference lifetime, action binding, transition events
  and public fields. Extend phase families only when needed; a new content ID does
  not inherently require a new phase. Keep runtime control bindings out of policy
  inputs and retain strict codecs and manifest compatibility checks.
- **Accept:** the representative feature runs through the backend and a public
  chooser; old artifacts either remain readable under their original contract or
  reject incompatibility clearly. Stale/forged candidates and private-field injection
  fail without mutation. Tests: Contract, Replay and affected Actor/data consumers.

### HF-04 — Extend persistent state for real runs

- **Status:** partial foundation: owned HP/gold/deck, IDs, RNG, phase and map history.
- **Depends on:** HF-01 for each newly implemented game field; HF-03 is later public integration.
- **Implement:** extend [run state] with declared character/difficulty/settings, current
  act/floor, persistent inventory and counters, card instance metadata, room/encounter
  history and generation-pool state as each first caller needs them. Give relics,
  potions, cards, rooms and combat entities durable engine identities. Public
  references are an adapter responsibility. Use typed/versioned records rather than unstructured
  feature-specific blobs or global mutable registries.
- **Accept:** two same-definition instances remain distinguishable; two independent
  runs do not share mutable objects; state serializes and validates at entry, room
  exit and combat boundaries. Invalid references and incompatible versions reject
  atomically. Tests: State, Progression, Contract and Replay.

### HF-05 — Match target RNG algorithms, domains and consumption

- **Depends on:** HF-01's RNG findings and HF-02 reference vectors.
- **Implement:** evolve [game rng] and its consumers for target seed conversion, integer
  ranges, weighted draws, shuffle, stream ownership and snapshot state. Map combat
  draw order, enemy moves, encounters, maps, reward rarity, relic/potion pools, shops
  and events to the actual domains. Keep policy/worker randomness separate. Preserve
  structural RNG behavior under its original identity where old fixtures need it.
- **Accept:** golden random vectors and at least one complete sequence of dependent
  game draws match the reference. Reads/rejections consume no unauthorized draws;
  restore reproduces the suffix. Test both independence and intentional coupling.
  Label distribution-only versus exact seeded parity separately. Tests: State,
  Differential and affected generation/combat tests.

### HF-06 — Introduce ordered effects and trigger resolution

- **Depends on:** a HF-02 reference case and HF-04; use HF-05 for random effects.
- **Implement:** a serializable resolution mechanism under `game/headless/core/`, integrating
  [game combat], [game cards], [game powers] and [game monsters]. Establish ordering for play/cost,
  damage, block, HP loss, draw, discard/exhaust, status changes, death and turn
  boundaries. Start with an existing card and one real trigger caller. Track source,
  owner and target; allow effects to enqueue effects without recursively bypassing
  decisions. Keep public events distinct from private execution records.
- **Accept:** exact order is asserted for a multi-effect card and a triggered effect;
  lethal damage interrupts subsequent work according to the target. A runaway
  effect chain produces a bounded infrastructure failure. Tests: Combat, State,
  Replay and Differential. Do not build an unused general-purpose rules language.

### HF-07 — Suspend and resume nested decisions

- **Status:** first combat parent → hand-choice → effect-suffix path is implemented,
  including sequential choices and JSON continuation. Reward/event children,
  autoplay/replay and general trigger chains remain open; extend the existing
  `core/selection.py` and card effect mechanism when those callers arrive.

- **Depends on:** HF-04/06.
- **Implement:** extend game-owned pending state and resolution in `game/headless/`
  to retain serializable parent/effect continuations. Drive automatic work to the next
  player decision or terminal boundary with a bounded drain. Cover card selection,
  reward pickup children and event combat without executable closures in snapshots.
  Preserve single-owner phase semantics. A synchronous simulator must not leave
  harmless internal work as a `WAITING` boundary that permanently stops [runner].
- **Accept:** one parent → child choice → parent completion path executes once,
  survives restore inside the child, and rejects stale parent choices. Cancellation,
  death and unsupported children have explicit outcomes. Tests: State, Replay,
  Progression and Contract.

### HF-08 — Snapshot every full-game decision and support isolated branches

- **Depends on:** HF-04/05/06/07 for implemented fields; extend incrementally.
- **Status:** direct combat/run JSON continuation and isolated branches are
  implemented for existing game state; future mechanics still need coverage.
- **Implement:** extend [game snapshots] and `core/snapshots.py` to capture new
  entity state, effects, pending choices, inventories and run progression. Keep
  exact suffix comparisons; restore currently decodes state without replaying the
  combat prefix. Define gameplay semantic keys
  separately from operational counters and policy-visible information keys.
- **Accept:** restore at combat, selector, reward, shop, event and act boundaries
  reproduces identical legal candidates and suffixes; branching cannot mutate its
  parent. Corrupt or incompatible snapshots reject atomically. Measure prefix-length
  dependence for later HF-49 work. Tests: State and Replay.

### HF-09 — Preserve all combat-produced run changes

- **Depends on:** HF-04/06. Integrate concrete item effects alongside HF-24/26;
  those effects are consumers of the extended handoff, not prerequisites for it.
- **Implement:** extend the owned `RunEngine.start_combat` / `finish_combat`
  handoff beyond final HP. Include item state/counters, consumed potions, max-HP
  changes, gold and intentional permanent card mutations, with exact identity and
  one-time launch/resolution binding. Keep temporary generated cards and temporary
  upgrades separate. Apply victory/defeat/end-combat hooks in target order.
- **Accept:** an item counter and one permanent change survive two combats; a
  temporary change does not. Duplicate/stale/foreign resolutions reject, and defeat
  cannot accidentally award victory rewards. Tests: State, Combat, Progression and
  Replay, extending the existing HP-only handoff tests.

### HF-10 — Distinguish unsupported rules from engine defects

- **Depends on:** none for a focused game-rule boundary improvement.
- **Implement:** add game-owned categories for unsupported content, illegal commands
  and defects at the first rule requiring them. Ensure invalid commands do not
  partly mutate state or RNG. When integrating the adapter, replace its broad
  exception-to-`REJECTED_BY_RULES` handling with these distinct outcomes, preserving
  rollback and keeping raw exceptions/private state out of policy responses.
- **Accept:** inject a failure before and after a mutation and verify unchanged
  state/RNG; the collector reports the right stop category and never retries an
  uncertain action. An implementation bug is distinguishable from an illegal move.
  Tests: Combat, Progression, Replay and Operation.

## Combat and card tasks

### HF-11 — Complete damage, block, HP and terminal semantics

- **Depends on:** HF-02/06.
- **Implement:** verify and implement target modifier order, integer rounding,
  Strength and other attributes, block gain/loss/caps, attack versus non-attack
  damage, direct HP loss, healing/max-HP changes, multi-hit effects and death timing.
  Replace assumptions in [game combat], [game player], [game monsters], [game powers] and damage
  helpers only where the pinned reference establishes the rule. Include simultaneous
  lethal effects, revival and victory checks when a reachable caller requires them.
- **Accept:** focused cases distinguish blocked hits, direct HP cost, per-hit
  rounding, negative modifiers and lethal trigger chains. The known simple combat
  path remains usable; changed legacy behavior has an explicit compatibility boundary.
  Tests: Combat and Differential; affected action-feature consumers must agree.

### HF-12 — Implement status and power lifecycles

- **Status:** Weak's 0.75 attack multiplier and the shared Weak/Vulnerable enemy-side
  duration boundary are implemented. Fresh player debuffs skip one duration tick;
  stacking preserves the existing flag. Private snapshot v3 and oracle clones/keys
  retain duration state. Uppercut and Shockwave are verified first callers. See
  [source and acceptance evidence](evidence/weak_and_area_debuffs_2026_09_13.md).
  Overgrowth also implements Frail, Artifact, Constrict/Shrink source ownership,
  Tangled, Ringing, Slow, Plow, Illusion, Infested and Minion behavior.
  Remaining: other power families, temporary attributes and general triggered
  hooks beyond these native callers.
- **Depends on:** HF-04/06/11.
- **Implement:** replace the two-status limitation with supported, typed status/power
  definitions and instance state. Cover application, stacking/replacement, removal,
  owner/source lifetime, duration timing, temporary attributes and triggered effects.
  Start with a verified missing basic status and retain Vulnerable/Shrink cases;
  then add each reachable status/power as an HF-12 content instance.
- **Accept:** source death, reapplication, zero stacks, owner-turn decay, immunity or
  prevention where applicable, and snapshot continuation match named references.
  Generalize Shrink's enemy-name cleanup only with equivalent verified behavior.
  Project visible stacks without private intent state. Tests: Combat, State,
  Contract and Differential.

### HF-13 — Execute upgraded and modified card instances

- **Status:** partial. Immutable definitions, mutable instances, arbitrary per-card
  levels and the verified first upgrades of all eleven current Ironclad cards are
  implemented. See [starter evidence](evidence/strike_upgrade_2026_09_13.md) and
  [reward-card evidence](evidence/slice_combat_content_2026_09_13.md). Rest-site
  selection works. Other card families, temporary modifiers and other upgrade
  sources remain open.
- **Depends on:** HF-01/02 for each rule and existing HF-04 state; coordinate
  persistent mutation with HF-33. No public contract dependency.
- **Implement:** add verified levels to [game cards]; add instance fields and
  resolution operations only for modifiers with concrete callers. Preserve instance
  identity and distinguish permanent changes from temporary combat changes.
  Existing effects read the resolved definition level automatically. Register new
  definitions once in [game catalog]; do not add profiles or card-name switches.
- **Accept:** upgrade one of two identical cards, inspect the correct preview, play
  both with different effects, restore, and enter another combat with the correct
  permanent version. Unsupported variants reject without mutation. Direct tests:
  `tests/headless/`; consumer integration belongs to HF-03/44–47.

### HF-14 — Complete card-zone, draw and hand-limit behavior

- **Depends on:** HF-02 for exact semantics; HF-04/06 for new instance/lifecycle state.
- **Status:** partial. The verified ten-card cap, blocked-draw conservation and
  needed-only reshuffle behavior are implemented for ordinary integer draws;
  encoder capacity does not control the rule. See the
  [source evidence](evidence/hand_limit_2026_09_13.md).
- **Implement:** complete native draw-prevention/after-draw hooks, shuffle ordering
  with hooks, retain/ethereal/innate or equivalent reachable keywords, inserted
  cards and cards in play/resolution. Preserve identities and zone conservation.
  Exact native RNG remains HF-05; the existing Python shuffle is not seed parity.
- **Accept:** draw at/beyond the hand limit, reshuffle during a multi-draw, retain
  while ending a turn, and generate/exhaust a temporary card without corrupting
  the master deck. Later consumer integration must represent every legal hand
  without truncation. Tests: direct game, State, Replay and Differential.

### HF-15 — Extend card costs, play legality and targeting

- **Depends on:** HF-06/11/13; external action encoding is later integration.
- **Implement:** add real current/base costs, temporary reductions, variable/X costs,
  alternate costs and play restrictions when the inventory establishes callers.
  Support self, one enemy, all enemies, random target and other reachable target
  modes through authoritative candidate generation. Keep stable enemy identities
  and one canonical action for untargeted cards. Extend `core/actions.py` and
  game legality first; inspect action encoding and candidate features when adding
  those action families to external consumers.
- **Accept:** zero energy, insufficient alternate resource, changed costs, dead
  targets and multi-target effects produce exactly the reference legal set. The
  actor cannot select the outcome of a random target. Tests: Combat, Contract,
  Differential and affected baselines/demo formatting.

### HF-16 — Support decisions inside card resolution

- **Status:** first callers implemented: Armaments (one/all combat upgrades) and
  True Grit (random/chosen exhaustion), with zero/one auto-selection, exact hand
  IDs, mandatory single choices and restoration while suspended. Both are in the
  eight-card slice reward pool and support Smith. See the
  [source and acceptance evidence](evidence/combat_card_choices_2026_09_13.md).
  Next: add a source-verified caller for discard/draw-pile selection or variable
  counts; optionality, ordered bundles, offered cards and replay/autoplay remain
  unimplemented. Do not replace the current mechanism just to anticipate them.

- **Depends on:** HF-07/13/14/15.
- **Implement:** first add one target-game card that asks for a hand/discard/draw-pile
  selection. Support operation, eligible originals, min/max count, optionality,
  ordering and confirmation semantics; extend to offered cards and bundles as
  required. Resume the originating effect exactly once. Handle copy/replay/autoplay
  callers with explicit cost, targeting and trigger semantics rather than recursive
  calls that skip the action boundary.
- **Accept:** zero/partial/full allowed choices, duplicate-definition cards,
  cancellation where legal and lethal follow-up effects work; restore within a
  selection yields the same suffix. Tests: Combat, Contract, State and Replay.

### HF-17 — Verify and finish the existing eight card definitions

- **Status:** implemented for the current base/upgrade definitions and supported
  interactions. Slimed draws one, exhausts and cannot upgrade. Source-checked
  damage/block/draw order, Body Slam scaling, terminal draws and every reward
  card's acquisition → smith → next-combat path have direct cases. See the
  [evidence](evidence/slice_combat_content_2026_09_13.md). Unsupported powers,
  enchantments and other modifier interactions remain their owning tasks; this
  is not live differential certification.
- **Depends on:** HF-02 and the applicable HF-11–15 behavior.
- **Implement:** separate named cases for Strike, Defend, Bash, Pommel Strike,
  Shrug It Off, Iron Wave, Body Slam and Slimed. Verify costs, targets, effect order,
  base/upgraded versions where applicable, tags and interactions against the pinned
  target. Keep resolved `CardSpec` and execution together in each definition;
  seven rewardable cards and generated Slimed have different pool eligibility.
- **Accept:** each definition has an independent positive case and a relevant
  modifier/order edge case; metadata and runtime results agree. Body Slam scaling,
  Bash application order and draw-after-play behavior have explicit cases. Tests:
  Combat and Differential; update [card notes][card-notes] only when facts change.

### HF-18 — Implement all remaining reachable card content

- **Depends on:** HF-01 inventory and the required HF-11–16 primitives.
- **Implement:** one bounded `HF-18/<definition_id>` ticket per base/upgrade family.
  Cover attacks (multi-hit, area/random targeting, conditional/variable damage),
  skills (block, draw, energy, HP costs, pile selection), powers (persistent hooks),
  curses/statuses and special/generated/off-color cards. Record generation pools,
  rarity, obtainability and upgrade restrictions. A novel rule becomes a small
  prerequisite extension to its owning mechanic task, not a silent approximation.
- **Accept:** every in-scope card inventory row has execution, metadata, acquisition
  eligibility and differential cases for each semantic variant. Pairwise cases
  cover meaningful trigger/keyword interactions; unsupported rows cannot enter a
  purported complete run. Tests: Content, Combat, Progression and Differential.

## Enemy and encounter tasks

### HF-19 — Generalize enemy behavior and combat entity lifecycle

- **Partial:** all Overgrowth callers now support owned move/cooldown counters,
  appended summon slots, immediate per-hit death reactions, secondary minion
  cleanup and illusion revival. Context aliases rebind on restore/search clone;
  Phrog child slots and Eye/Beast phases are validated. Other acts' entity
  mechanics remain open.

- **Depends on:** HF-04/05/06/11/12.
- **Implement:** extend [game monsters] for history-dependent/random move selection,
  visible intent updates, enemy-specific counters, phases, summoned entities,
  transformations, escape, death prevention/revival and encounter completion as
  required by a first named caller. Keep dead-target and new-entity identities
  stable; lift fixed capacity only through explicit representation changes.
- **Accept:** move restrictions and RNG consumption match the reference; source
  death and summons cannot renumber another target; a defeated phase or escaping
  enemy does not incorrectly finish the encounter. Hidden move state stays private.
  Tests: Combat, State, Contract, Replay and Differential.

### HF-20 — Verify the existing Overgrowth enemy slice

- **Status:** partial. Solo Nibbit, Leaf/Twig small/medium variants and SlimesWeak
  composition are source-checked with full-cycle/branch cases. Medium Twig's
  repeat constraint and slime slot order are corrected. Fuzzy Wurm, solo Mawler,
  paired Nibbit opening roles and their encounter compositions are also verified;
  the authored `overgrowth` route exercises these through four fights and two
  branch decisions. Shrinker Beetle is now source-checked, including owned-source removal and final
  multiplier rounding. Native RNG parity and ascension variants remain open.
  See [initial evidence](evidence/slice_combat_content_2026_09_13.md) and
  [expanded encounters/route](evidence/overgrowth_routes_2026_09_13.md).
- **Depends on:** HF-02/05 and relevant HF-11/12/19 rules.
- **Implement:** per-enemy tickets for Nibbit, Shrinker Beetle, Fuzzy Wurm Crawler,
  Mawler, Leaf Slime S/M and Twig Slime S/M. Verify HP sampling, opening moves,
  damage, debuffs/generated cards, repetition restrictions, probabilities and
  difficulty variants. Verify the three-slime composition and slot ordering.
  Keep SimpleEnemy explicitly synthetic.
- **Accept:** each real enemy has full-cycle or branch-covering reference traces;
  stochastic constraints/distributions and deterministic continuations are checked
  separately. Easy/hard pool names retain honest partial-coverage labels until
  HF-21/30 complete them. Tests: Combat and Differential.

### HF-21 — Complete normal encounters across every target act

- **Status:** all 16 native Overgrowth normal/easy encounter entries are implemented
  at A0, including mixed and variable compositions. The complete 22-entry census
  includes elites/bosses; see [roster evidence](evidence/overgrowth_roster_2026_09_13.md).
  Other acts and native pool selection remain open.

- **Depends on:** HF-01/19 and each enemy's implemented mechanics. HF-30 later
  integrates these encounter definitions into run sampling.
- **Implement:** `HF-21/<act_id>/<encounter_id>` tickets for each missing easy/hard
  hallway encounter. Specify members, positions, count/HP variation, shared powers,
  scripted coordination and entry conditions. Reuse enemy definitions and scenario
  factories; do not duplicate the registry in the run composer.
- **Accept:** every encounter is constructible, projects all legal decisions,
  reaches victory/defeat and restores exactly. Verify mixed-enemy interactions and
  difficulty variants. HF-30 owns normal-run pool and history-rule acceptance.
  Tests: Content, Combat, Progression and Differential.

### HF-22 — Implement all target elite encounters

- **Partial across the full game; Overgrowth A0 complete:** Byrdonis, Bygone
  Effigy and Phrog Parasite have verified moves, required powers, summon/death
  rules and elite reward handoff. Other acts and ascension variants remain open.
  See [roster evidence](evidence/overgrowth_roster_2026_09_13.md).

- **Depends on:** HF-01/19 and the elite's card/status mechanics. Integrate the
  resulting definition with HF-30/31 when run sampling/rewards are available.
- **Implement:** one `HF-22/<encounter_id>` ticket per elite, including phase/counter
  rules, opening/conditional moves, group mechanics, difficulty variants and
  elite-specific reward routing. Reuse combat execution; elite is encounter metadata,
  not another combat backend.
- **Accept:** representative victories and defeats plus every special transition
  match references; expose the exact encounter outcome for HF-30/31 integration.
  Dead allies, summons and on-death effects have cases
  where applicable. Tests: Combat, Progression and Differential.

### HF-23 — Implement all target boss encounters

- **Partial across the full game; Overgrowth A0 complete:** Vantom, Ceremonial
  Beast and The Kin have verified moves, phase/minion rules, boss rewards and
  exact boss-ID act completion. Other acts and ascension variants remain open.
  See [roster evidence](evidence/overgrowth_roster_2026_09_13.md).

- **Depends on:** HF-01/19 and the boss's mechanics. HF-30/31/37 consume the
  resulting encounter; they are not prerequisites for implementing its combat.
- **Implement:** `HF-23/<encounter_id>` tickets for every selectable boss in every
  target act. Include phase transitions, invulnerability/revival, minions, special
  resources, turn/card limits or rule overrides only where that boss has them.
  Distinguish defeating a body/phase from winning the encounter.
- **Accept:** all boss-specific branches and true victory/defeat boundaries have
  reference cases; expose an unambiguous outcome for the HF-31/37 reward and act
  transitions. Restore on both sides of a phase boundary. Tests: Combat, State,
  Progression, Replay and Differential.

## Relic and potion tasks

### HF-24 — Add relic inventory, lifecycle hooks and the starter relic

- **Partial:** run-owned item identities, Burning Blood victory healing and
  max-HP pickup hooks are implemented. General ordered triggers, counters,
  charges and pickup selectors remain open.

- **Depends on:** HF-01/04/06/09/11.
- **Implement:** introduce relic definition/instance state, acquisition/removal,
  counters, charges, disabled state and ordered hooks. Wire the pinned Ironclad
  starter relic through new-run setup, combat completion and persistence first.
  Inventory changes can schedule child choices through HF-07. Do not store relic
  behavior solely in the live bridge or attach ad hoc callbacks to each room.
- **Accept:** the starter relic's actual effect occurs at its exact boundary,
  persists correctly over two fights, and respects HP caps and death semantics.
  Duplicate obtain/removal and restore do not double-trigger. Tests: State, Combat,
  Progression, Replay and Differential.

### HF-25 — Complete reachable relic content and interactions

- **Partial:** Strawberry, Pear and Mango permanently gain 7/10/14 max HP and
  heal by the same amount on pickup. Restore never replays the effect; removal
  does not reverse it. Other relics and combat-time acquisition remain open.

- **Depends on:** HF-01/24 and mechanic-specific tasks.
- **Implement:** per-ID relic tickets covering combat triggers, persistent counters,
  resource/cost changes, map/rest/shop/reward modifiers, pickup selectors, pool
  replacement/exclusion and event/ancient-specific items. Include relic removal,
  replacement and ordering when multiple relics react to the same effect. The
  [event inventory][event-inventory] already identifies immediate pickup interactions.
- **Accept:** every reachable relic has obtain/use/remove cases where applicable;
  pickup children resume correctly and counters survive rooms, acts and snapshots.
  Interactions with cards/potions and generation use the same authoritative hooks.
  Tests: State, Combat, Progression, Contract and Differential.

### HF-26 — Add potion inventory, use, discard and replacement

- **Depends on:** HF-04/06/07/09/15.
- **Implement:** potion instances and slots/capacity, legal use contexts and targets,
  consumption timing, discard, acquisition and full-inventory replacement/skip.
  Implement one verified targeted and one untargeted potion end to end. Distinguish
  player choice from automatic potion effects and let capacity-changing relics use
  shared inventory rules. Expose only actually legal item candidates.
- **Accept:** use costs no unintended card energy, consumes exactly the correct
  instance and persists to the next room; wrong targets/context reject. Full and
  expanding inventory, duplicate definitions, nested choices and restoration work.
  Tests: Contract, State, Combat, Progression and Replay.

### HF-27 — Complete reachable potion definitions and generation rules

- **Depends on:** HF-01/26 and the relevant effect/status/card primitives.
- **Implement:** per-ID cases for damage, block, healing, attributes/statuses,
  card/resource generation, selection, delayed and automatic effects in the target
  potion inventory. Include rarity/pool eligibility, potency modifiers and character
  restrictions; implement target drop-state behavior with HF-30/31 rather than
  embedding arbitrary chance in individual potion classes.
- **Accept:** each legal context, consumption boundary and effect matches a named
  reference; item modifiers and potion-triggered selections have integration cases.
  Failed/illegal uses do not consume inventory or RNG. Tests: Content, Combat,
  Progression and Differential.

## Run progression and room tasks

### HF-28 — Initialize declared runs and starting choices

- **Depends on:** HF-01/04 and starter content, including HF-24. A first starting
  choice can be implemented with HF-39; HF-43 later completes the offer catalog.
- **Implement:** extend `RunEngine` initialization with a target run
  configuration: character, difficulty, unlock/settings manifest, base deck, HP,
  gold, inventory, act setup and starting/ancient choices. Distinguish structural
  debug configurations from target configurations. Consume supplied configuration;
  normal headless reset must not read the user's profile or save files.
- **Accept:** reset matches the declared starting state and legal choices; identical
  settings/seeds reproduce the run, unknown settings/content reject before mutation,
  and the first map/combat receives the chosen effects. Tests: State, Content,
  Progression, Contract and Operation.

### HF-29 — Generate and expose target maps

- **Depends on:** HF-01/04/05/28.
- **Implement:** extend [game map] beyond authored DAG navigation to target topology,
  coordinates/edges, starting destinations, room placement constraints, visible
  boss/act information and map-altering effects. Preserve graph/history across
  rooms and acts. Represent visibly unknown nodes without revealing their private
  eventual outcomes. Retain fixed templates as explicit fixture configurations.
- **Accept:** golden map cases and structural constraints match the pinned target;
  only reachable next nodes are legal, visited nodes cannot be replayed, and map
  changes preserve identity/history. Tests: Progression, State, Contract and
  Differential, including generation distributions.

### HF-30 — Select encounters, events and room outcomes from real pools

- **Depends on:** HF-01/04/05/29 and the selected content implementations.
- **Implement:** persistent pool state for act-specific easy/hard encounters,
  elites/bosses, event eligibility/weights, unknown-room resolution, no-repeat rules,
  seen flags and any target pity/exclusion counters. Select an encounter for each
  combat node. Relic/difficulty modifiers must act at the correct selection
  boundary. Never reroll because the selected content is unimplemented.
- **Accept:** complete sampled sequences match target restrictions and seeded
  references where available; marginal/conditional distributions have independent
  expectations. Reads and rejected map actions do not consume rolls. Tests:
  Content, State, Progression and Differential.

### HF-31 — Generate real combat and room rewards

- **Boss slice:** Vantom awards 100 gold, a potion roll and three rare cards from
  Impervious/Offering/Fiend Fire. No elite relic is substituted into boss rewards.
  Native rare-only base odds and scalar/card rules are source-checked; the full
  rare pool, native upgraded offers and native sampling remain open.

- **Partial:** source-checked hallway 10–20 and elite 35–45 gold, three card
  offers, potion rolls and an elite relic are implemented. Card/potion/relic
  pools and Python sampling are explicitly restricted; native rarity/upgrade
  chances, full pools and native RNG parity remain open. Owned relics are
  excluded; the restricted pool rejects exhausted elite entry without a roll.

- **Depends on:** HF-01/04/05/30; applicable HF-18/25/27 content.
- **Implement:** extend [game rewards] for actual gold ranges/modifiers, card count,
  rarity and upgrade chances, pool exclusions, persistent rarity/drop state,
  relic/potion rewards, elite/boss variations and special combat extras. Determine
  when outcomes are sampled and revealed; shuffling a fixed complete card list is
  not target reward generation. Keep generation separate from collection choices.
- **Accept:** known random vectors, pool membership, count/order and modifier cases
  match references; repeated observation/opening cannot reroll an offer. Generation
  distribution evidence is distinct from conditional transfer evidence. Tests:
  Content, Progression, State and Differential.

### HF-32 — Resolve mixed rewards and nested pickup effects

- **Partial:** gold/card/potion/relic claims and forfeits are independent.
  Simple relic pickup commits once with persistent HP and exact ownership.
  Multiple entries of one kind and nested pickup selectors remain open.

- **Depends on:** HF-07/24/26/31; HF-33 for pickup selectors.
- **Implement:** gold, card, relic, potion and special reward entries, including
  multiple card menus, optional selections, bundles, item skip/replacement and
  pickup-triggered children. Match native leave/proceed legality instead of assuming
  every gold/card entry must be resolved as in the structural fixture. Maintain
  exact reward identity and parent progress across nested choices.
- **Accept:** choose/skip/choose through multiple entries, fill/replace potion slots,
  obtain a relic with a selector, restore inside it and finish the parent once.
  No repeated claims or duplicated rewards on replay. Tests: Progression, State,
  Contract, Replay and Differential.

### HF-33 — Apply permanent deck changes and modifiers

- **Depends on:** HF-04/07/13 and target metadata from HF-01.
- **Implement:** shared add/remove/upgrade/transform/enchant operations used by
  rests, shops, events and relic pickups. Retain exact original-card identity,
  selection eligibility, counts, order, generated replacements and modifier
  stacking/replacement. Support automatic/zero-choice paths and multi-card/bundle
  choices when target semantics require them. Temporary combat state remains separate.
- **Accept:** changing one of two identical cards affects only that instance;
  removal plus grant, multi-transform, optional empty choice and an upgraded
  replacement survive the next combat and restore. Tests: State, Progression,
  Combat, Contract and Differential.

### HF-34 — Implement actual rest-site options

- **Depends on:** HF-01/07/11/13/33; HF-24/25 for modifier-driven options.
- **Implement:** extend [game rooms] with pinned rest healing/rounding and smithing,
  legal card selection, one-use/leave semantics, disabled choices and additional
  relic/character/difficulty-enabled actions. Use shared deck and heal effects.
  Preserve the fixed-15 fixture under its own content identity rather than
  presenting it as native healing.
- **Accept:** damaged/full-HP visits, no eligible upgrade, duplicate cards and a
  relic-modified rest all offer the right legal choices and return to the map once.
  Upgrade → next combat works end to end. Tests: Progression, State, Combat,
  Contract and Differential.

### HF-35 — Implement shops and repeatable purchases

- **Partial:** the first supported merchant has exact offer IDs, repeat purchases,
  one sale, sold-out state, card/relic/potion acquisition, full-slot/affordability
  rejection and a cancelable exact-card removal service. A0 removal is 75 + 25
  per previous successful removal, once per shop. Its optional Act 1 node and all
  shop decisions restore exactly. Native base costs and variation bands are
  verified; stock composition and discrete variation sampling are authored.
  Remaining: complete native pool generation, discounts/restock modifiers,
  colorless stock, pickup child selectors and event-owned merchants. See
  [first-shop evidence](evidence/first_shop_2026_09_13.md).

- **Depends on:** HF-01/05/07/24/26/33; HF-29/30 for normal entry.
- **Implement:** shop inventory generation and display, prices/sales/discounts,
  cards/relics/potions, repeat purchases, sold-out/restock rules, card-removal service
  and persistent removal pricing. Re-evaluate affordability and legality after every
  purchase and pickup child. Distinguish normal shops from event-owned shops while
  sharing item and deck effects. Add explicit enter/leave lifecycle to `RunEngine`.
- **Accept:** buy two different items, run a removal/pickup selector, decline an
  unaffordable item and leave; balances, inventory and parent continuation are exact.
  Snapshot midway and exercise price-changing relics. Tests: Progression, State,
  Contract, Replay and Differential.

### HF-36 — Implement treasure and remaining non-event room families

- **Partial:** the ordinary A0 chest now grants 42–52 gold on opening and offers
  one optional relic through shared acquisition rules. Leaving closed grants
  nothing; leaving open retains the gold. The restricted fruit pool excludes
  owned and previously offered entries and falls back to stackable Circlet.
  Exact chest/claimed-item IDs, gold, pool depletion and RNG restore; Act 1 has
  a chest after its third combat. Native global grab bags, rarity weighting,
  tutorial/multiplayer rules, treasure suppression, extra rewards and other fixed
  room families remain open. See [first-treasure evidence](evidence/first_treasure_2026_09_13.md).

- **Depends on:** HF-01's room census, HF-07/25/29/30/32.
- **Implement:** chest/treasure generation, open/leave choices, pool effects and
  pickup children, then one ticket per other fixed room family reachable in the
  target. Route rooms through the game run engine; do not encode unsupported
  room kinds as harmless events. Share reward acquisition with HF-32.
- **Accept:** normal, modified and empty/exhausted-pool cases follow reference
  rules; collected rewards persist and cannot be claimed twice; leaving reaches
  the correct next map/act boundary. Tests: Content, Progression, State, Contract
  and Differential.

### HF-37 — Implement act transitions and real run termination

- **Partial:** leaving the first supported boss reward records Act 1 completion
  with the exact boss ID and ends at `act_complete`. Reward claims/forfeits restore
  exactly. Later-act setup, pool reset, inter-act effects and full-run victory
  are not implemented; `slice_complete` retains its original milestone meaning.

- **Depends on:** HF-23/28/29/31/32. Add event/ancient-specific transition callers
  through HF-42/43 after the base act lifecycle exists.
- **Implement:** act completion, inter-act state/reset/healing rules, boss rewards,
  next act/ancient selection, final encounter/ending requirements and explicit
  abandonment. Define which counters persist or reset. Replace authored terminal
  placeholders with verified ending rules in `RunEngine`. Later consumer integration
  must distinguish actual run victory from the old `route_complete` fixture.
- **Accept:** boss → rewards → next act and final boss → actual ending are separate
  tested paths. Death and abandonment stop at any reachable phase; no post-terminal
  actions or double rewards. Tests: Progression, State, Contract, Replay and
  Operation, with target references for the ending conditions.

### HF-38 — Implement difficulty and declared unlock variants

- **Depends on:** HF-01 and the affected combat/run/content tasks.
- **Implement:** verify the highest standard Ironclad difficulty in the pinned build,
  inventory every modifier, and apply it at its owning layer: starting state,
  encounters/moves, rewards, map/room generation, rest/shop rules or terminal flow.
  Model unlock/settings effects through explicit configuration and pool eligibility.
  Never infer that difficulty is only an enemy-HP multiplier.
- **Accept:** boundary cases isolate each modifier and combined target-difficulty
  runs exercise their composition. A0 behavior remains separately tested; identical
  content/settings identities reproduce results. Tests: Content, Combat, Progression
  and Differential. User profile construction/access is separately authorized work.

## Event and ancient tasks

### HF-39 — Add a real event state machine and ordinary choices

- **Partial:** Jungle Maze Adventure is source-verified in Overgrowth and runs
  through explicit catalog, event/map IDs, owned stage/data, exact choice commands
  and terminal departure. Both branches, repeat/stale rejection, entry failure,
  death at the 18-HP boundary and JSON restore are covered. Authored integer gold
  sampling approximates the native float variation. Event selection weights,
  availability/no-repeat rules, multiplayer, additional pages/branches and remaining
  content are open. See [first-event evidence](evidence/first_event_2026_09_13.md).

- **Depends on:** HF-01/05/06/07/11. HF-28 consumes this engine for starting choices;
  a directly initialized event fixture is sufficient for the first implementation.
- **Implement:** event definitions and instance state for eligibility, pages,
  conditional choices, prices/HP costs, random branches, repeated options and
  explicit finish. Start with one pinned ordinary event, using [event-map] source
  references. Keep native event semantics separate from the structural `quiet_cache`
  and `cool_spring` fixtures. Shared effects should execute rewards, healing and loss.
- **Accept:** disabled/unaffordable choices, revisiting a page, a legal no-effect
  option at full HP, random resolution and death during an event behave correctly.
  The unchanged `cool_spring` fixture can remain explicitly unsupported. Tests:
  Progression, State, Contract, Replay and Differential.

### HF-40 — Compose event selectors, card offers and deck mutations

- **Partial:** Aroma of Chaos implements mandatory transform/upgrade selection,
  zero/one automatic resolution, no cancel and exact event/deck continuation.
  Shared permanent transformation has owned RNG/IDs and explicit candidate pools.
  Source/replacement coverage is restricted to implemented Ironclad cards; other
  pools, modifiers, removal/enchantment, offers and nested children remain open.
  See [Aroma evidence](evidence/aroma_of_chaos_2026_09_13.md).

- **Depends on:** HF-07/32/33/39.
- **Implement:** event-owned removal, upgrade, transformation, enchantment, offered
  cards and bundles. Cover mutations before selection, mutations after selection,
  repeated/nested children and automatic selection. Named implementation candidates
  in the retained research include Amalgamator, Wood Carvings, Scroll Boxes and
  Colorful Philosophers; confirm the exact target branch before choosing one.
- **Accept:** a selector plus subsequent grant resumes its parent correctly;
  optional zero/partial/full selection and a sequence of card reward menus conserve
  identities and effects. Snapshot inside each child. Tests: Progression, State,
  Contract, Replay and Differential. Bridge acceptance alone is not headless parity.

### HF-41 — Run event combat and resume its parent

- **Depends on:** HF-07/09/19/31/32/39.
- **Implement:** event-selected encounters, temporary combat rules/objectives,
  bounded training/expiry where applicable, victory/defeat/escape result handling,
  non-resuming exits and resuming event pages with rewards/selectors. Start with a
  named Battleworn Dummy or Dense Vegetation branch; add the target's extra special
  rewards through the common reward engine.
- **Accept:** training expiry is distinguishable from ordinary combat victory;
  death cannot resume the parent; victory can return through a reward child to the
  right event page. No duplicate combat launch or grant after restore. Tests:
  Combat, State, Progression, Replay and Differential.

### HF-42 — Model custom event interactions and terminal branches

- **Depends on:** HF-07/32/35/37/39 and each caller's effects.
- **Implement:** separate bounded tickets for Fake Merchant inventory/combat,
  Crystal Sphere tools/fog/reveals/rewards, Trial's abandonment decision and any
  Architect progression branch required by HF-01. Represent game decisions and
  state transitions headlessly; UI geometry/animation does not need simulation.
  Hidden custom-screen contents remain private until revealed by a legal action.
- **Accept:** each custom interaction has a public legal path to completion and
  a meaningful cancellation/terminal/failure case; repeated reveals/purchases
  cannot repeat rewards. Match any gameplay-relevant timing as a rule, not wall-clock
  sleeps. Tests: Contract, State, Progression, Replay and Differential.

### HF-43 — Complete the event and ancient catalog

- **Depends on:** HF-01/24/25/28/39–42 as applicable.
- **Implement:** instantiate a ticket for each reachable event/ancient branch in
  the [retained inventory][event-inventory], incorporating the corrections linked
  from [event-map]. Cover initial/act-specific offers, pool eligibility, item
  selection, immediate relic pickup effects, special cards, automatic transformations
  and finish/terminal conditions. Add newly discovered branches to the same census.
- **Accept:** every in-scope branch has exact prerequisites, legal choices, effects,
  RNG behavior and completion evidence. Zero-choice/empty-pool and nested pickup
  variants are included. “Shared selector implemented” does not mark all its event
  callers complete. Tests: Content, Progression and Differential.

## Public data, operation and completion tasks

### HF-44 — Expose sufficient public run state and observable history

- **Depends on:** HF-03/04 and each new mechanic.
- **Implement:** evolve [projection] and phase observations to include the visible
  master deck/modifiers, relics/counters, potions/slots, act/floor/difficulty,
  inspectable pile contents in their public form, map context and public event
  history needed to choose intelligently. The present reward/map/room views expose
  only deck size. Distinguish unknown, absent and empty fields, and define reference
  lifetimes and observable-memory updates across phases.
- **Accept:** two decks or inventories with different visible effects are
  distinguishable; two privately different states with identical public history
  remain indistinguishable. Inspection never advances RNG or resolves a hidden
  outcome. Tests: Contract, Replay, Differential and Actor/data.

### HF-45 — Extend encoding and policies without dropping legal choices

- **Depends on:** HF-03/44 and the first new content/action family.
- **Implement:** version [headless encoding] and its schema/candidate joins for new
  entities, actions and public fields. Preserve variable candidate scoring, masks,
  semantic identities and padding. Audit the 128-item contract limit, fixed legacy
  combat capacities and frozen categorical vocabularies against reachable states.
  Explicitly migrate/retrain incompatible checkpoints. [Card records][card-records]
  are a possible reuse source, not an already integrated solution.
- **Accept:** all legal candidates survive encoding/collation, permutation tests
  remain sound and no private identifier/seed becomes a feature. Test large legal
  states, unknown semantics and old checkpoint rejection. Tests: Actor/data,
  Contract and affected combat encoders/baselines.

### HF-46 — Carry full-run semantics through datasets and artifacts

- **Depends on:** HF-03/37/44/45; extend for each schema change.
- **Implement:** evolve [trajectories], [policy dataset], [reporting] and [cloning]
  schemas for new decisions, content/build/rules/settings identities, run progress,
  actual outcomes and truncations. Keep policy history, hindsight targets and
  operational/private diagnostics separated. Preserve externally anchored manifests,
  split separation and cancellation-safe publication. Existing trajectory evidence
  admission accepts only `combat_v0`/`structural_fixture`; broaden it deliberately
  if new evidence classes are needed, never by relabeling old files.
- **Accept:** a multi-act trajectory round-trips and trains/loads through affected
  consumers without losing item/selection candidates. Structural completion cannot
  become a real victory label; held-out sources and private fields remain excluded.
  Tests: Actor/data, Replay and Operation.

### HF-47 — Run the new environment through existing APIs and CLI

- **Depends on:** HF-03/07/28/37/46 for the delivered slice.
- **Implement:** extend the existing backend factory/configuration, [runner],
  [rollouts] and [headless CLI] for the declared target mode. Preserve bounded
  transitions, cancellation/worker cleanup, independent policy RNG and artifact
  reporting. Supply a simple public-only chooser that handles each new action
  family; strategy can remain basic. Keep pure headless help/execution free of
  unnecessary Torch/Gymnasium imports.
- **Accept:** one maintained command starts and finishes the supported run scope,
  another configuration reproduces it in a worker, and failures/budgets/unsupported
  cases are accurately reported. Add a dedicated full-run smoke configuration;
  the current 16-transition smoke is not a complete-run gate. Tests: Operation,
  Replay, Contract and package/lazy-import checks.

### HF-48 — Accept complete-run fidelity and close coverage gaps

- **Depends on:** HF-02 and all mechanics/content in the proposed coverage scope.
- **Implement:** extend named conformance into multi-decision, cross-room and
  cross-act sequences. Compare every meaningful public boundary and legal set,
  relevant ordered effects and independently authorized private diagnostics.
  Add generated action-sequence tests for conservation, legality, ownership and
  liveness; minimize mismatches into regression cases. Track untested and divergent
  inventory rows explicitly, separate from implementation status.
- **Accept:** selected reference runs and held-out sequences match under declared
  content/settings, targeted negative controls fail, and every known reachable
  discrepancy is resolved or narrows the claim. Report generation/seed parity and
  conditional effect parity separately. Tests: Differential, Replay, integration.
  A full agent win-rate or near-optimality campaign is a separate research task.

### HF-49 — Measure and improve full-run/branching performance

- **Depends on:** a stable faithful slice, HF-08/47; optimize only measured costs.
- **Implement:** benchmark reset, action application, observation/candidate building,
  snapshot/restore, branching, recording and worker throughput/memory under declared
  hardware/settings. Investigate replay-prefix cost and repeated whole-state
  validation before adding accelerators. Reuse current process collectors and
  profiling mechanisms. Add direct snapshots/checkpoints, batching or caching only
  when measurements justify them.
- **Accept:** before/after matched workloads report throughput, latency, memory and
  full-run/branch costs; deterministic traces and the affected conformance suite
  remain equal. Multiple runs/workers share no mutable state. Choose numerical
  throughput targets from actual training/search needs, not invented acceptance
  claims. Tests: State, Replay and Operation.

### HF-50 — Deliver a reproducible supported simulator package

- **Depends on:** HF-47/48 and HF-49 measurements for the declared milestone.
- **Implement:** maintain installable canonical packages and `sts-headless`, target
  configuration examples, content/rules/build manifests and a concise support matrix.
  Provide documented local content preparation if required, without bundling game
  binaries/assets. Verify source-to-package identity and retain validation evidence;
  avoid a second CLI/package pipeline for each mechanic.
- **Accept:** a clean declared environment installs, resets, executes, records,
  validates and restores the supported scope from documented commands. Incompatible
  inputs fail clearly, dependencies and Python 3.10+ policy are explicit, and current
  evidence never borrows historical hashes. Tests: package/lazy imports, Operation
  and one final milestone integration gate.

## Conditional backend and later breadth tasks

### HF-51 — Test whether reusing native game rules shortens the fidelity work

- **Status:** optional investigation before committing to a large reimplementation;
  not a requirement to replace the current Python backend.
- **Depends on:** one HF-02 reference case and a bounded setup consistent with the
  [live development guide](LIVE_DEVELOPMENT.md). See the [backend design question]
  for the existing architectural option.
- **Implement:** test one representative combat plus one nested noncombat decision
  through actual engine-hosted rules, if feasible. Measure deterministic reset,
  snapshot/branching, isolation, headless execution and throughput through the same
  public backend interface. Record lifecycle and local setup/distribution constraints.
- **Accept:** evidence supports retain-Python, native-backed or hybrid ownership of
  rules. Map every affected backlog task to the chosen implementation; native reuse
  does not eliminate observation, persistence, content coverage or conformance work.
  Do not create another production bridge/mod or read user profiles for this spike.

### HF-52 — Add every other single-player character

- **Status:** outside the initial Ironclad target; implement when breadth is selected.
- **Depends on:** HF-01–50's shared facilities and a new per-character scope inventory.
- **Implement:** one ticket per character for starting deck/relic/stats, resources,
  summons/companions or other unique mechanics, cards/upgrades, restricted items,
  generation pools, character-specific events/ancients and difficulty modifiers.
  Shared off-color content reachable by Ironclad already belongs in HF-18/25/27.
- **Accept:** each character has mechanic reference cases and complete A0 and target
  difficulty runs under its declared profile; public representation and policies
  handle its full action set. Reuse the same simulator and CLI. Tests: all affected
  mechanic groups plus HF-48's per-character completion gate.

### HF-53 — Add cooperative multiplayer semantics

- **Status:** outside the initial single-player target; requires its own target contract.
- **Depends on:** HF-52 as required by selected teams, plus shared run/state infrastructure.
- **Implement:** multiple player inventories/resources, action ownership and ordering,
  shared room decisions, ally targeting, team-only content, scaling, death/revival,
  reward ownership and multiplayer RNG semantics. Define each actor's observable
  information and legal choices. Simulate gameplay scheduling independently of any
  optional network-transport adapter.
- **Accept:** two players with independent policies complete representative combats,
  shared choices and a full run; schedule/replay ordering is deterministic and one
  player cannot act for another. Test disconnect/abandon semantics only if they are
  in the declared gameplay scope. Add team differential and information-boundary cases.

### HF-54 — Add alternate modes and maintain later game builds

- **Status:** outside the pinned standard-mode target; select explicit mode/build tickets.
- **Depends on:** HF-01/38/48/50 and each selected mode's mechanics.
- **Implement:** inventory custom/challenge/daily-style modes actually present in
  the chosen build, their seeds, modifiers, content eligibility, scoring and endings.
  For a new patch, capture a new immutable build identity, diff the content/rules
  inventory, implement changed semantics and rerun affected conformance. Keep
  cross-build snapshots, data and checkpoints explicitly compatible or rejected.
- **Accept:** each claimed mode/build has reproducible configuration, complete
  coverage accounting and its own completion gate. Existing pinned runs keep their
  original behavior/evidence; no historical manifest is overwritten to imply a port.

## Next bounded implementation assignment

The Overgrowth A0 combat roster is complete. The next batch toward a complete
Act 1 is **HF-29/30: native map topology and encounter progression**, using the
existing 22-entry encounter catalog:

1. Inspect pinned Overgrowth room count, map generation, guaranteed room positions,
   edge restrictions and first-three weak-fight selection. Record native discovery
   settings explicitly; support a declared unlocked-content configuration.
2. Generate an owned seeded Act 1 map through `map/graph.py`, retaining the small
   authored routes as fixtures. Validate connectivity, reachable choices, room
   frequencies/restrictions and exact JSON restore without generation rerolls.
3. Add run-owned weak/normal/elite/boss encounter histories and selection rules.
   Reference catalog IDs; do not duplicate monster data. Restore must preserve
   used pools and the next encounter decision. Test exclusions and no-repeat rules.
4. Drive a full-length map through existing combat, reward and room lifecycles.
   Keep unsupported event/item/card content excluded by an explicit pool setting;
   never silently replace an unsupported event with a harmless room. Record this
   as restricted-content Act 1 progression until HF-18/24–27/31–36/39–43 close the
   remaining Ironclad cards, relics, potions, rewards, shops and event branches.
5. Add native reference traces for multi-room seeds, installed execution and exact
   continuation at map/room/boss decisions. Full native RNG parity is HF-05;
   later acts and higher ascensions remain separate from the A0 Act 1 milestone.

[build]: ../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json
[contract]: ../game/contracts/headless_v0.py
[fixture]: ../game/backends/headless/fixture_backend.py
[composer]: ../game/backends/headless/reduced_run_backend.py
[combat-adapter]: ../game/backends/headless/combat_v0_backend.py
[state]: ../game/engine/headless_state.py
[rng]: ../game/engine/random_service.py
[snapshots]: ../game/engine/snapshots.py
[content]: ../game/content/reduced_v0.py
[cards]: ../game/simulation/card.py
[enemies]: ../game/simulation/enemy.py
[scenarios]: ../game/backends/headless/scenarios.py
[combat core]: ../game/simulation/core.py
[player]: ../game/simulation/player.py
[statuses]: ../game/simulation/status.py
[deck]: ../game/simulation/deck.py
[combat encoder]: ../game/simulation/encoding.py
[actions]: ../game/simulation/actions.py
[action features]: ../game/simulation/action_features.py
[candidates]: ../game/backends/headless/combat_candidates.py
[projection]: ../game/backends/headless/combat_projection.py
[map rules]: ../game/engine/map_rules.py
[reward rules]: ../game/engine/reward_rules.py
[room rules]: ../game/engine/room_rules.py
[runner]: ../game/runtime/episode_runner.py
[rollouts]: ../game/training/headless_rollout.py
[headless CLI]: ../game/cli/headless.py
[trajectories]: ../game/data/headless_trajectory.py
[policy dataset]: ../game/data/headless_policy_dataset.py
[headless encoding]: ../game/agents/headless_encoding.py
[cloning]: ../game/training/headless_behavior_clone.py
[reporting]: ../game/training/headless_reporting.py
[card-records]: ../game/simulation/card_records.py
[conformance]: ../game/analysis/conformance_evidence.py
[common comparator]: ../tests/differential/common_public_subset.py
[gold-spec]: ../tests/differential/reward_gold_case_spec.json
[gold-evidence]: archive/phase-1/research/PHASE_1_NEXT_INCREMENT_ACCEPTANCE.md#live-result-and-claim-boundary
[actor-evidence]: archive/phase-1/research/PHASE_1_ACTOR_READY_ACCEPTANCE.md#2026-09-05--cloning-smoke-acceptance-and-final-headless-join
[card-notes]: IRONCLAD_CARDS.md
[enemy-notes]: OVERGROWTH_HARD_V1.md
[event-map]: EVENT_INTERACTION_MAP.md
[event-inventory]: evidence/event_interactions_2026_09_09/inventory.json
[backend design question]: LONG_TERM_ARCHITECTURE_ROADMAP.md#104-fast-backend-decision

[game package]: ../game/headless/
[run state]: ../game/headless/run/state.py
[game rng]: ../game/headless/core/rng.py
[game snapshots]: ../game/headless/run/snapshots.py
[game cards]: ../game/headless/cards/ironclad.py
[game catalog]: ../game/headless/cards/catalog.py
[game combat]: ../game/headless/core/combat.py
[game player]: ../game/headless/core/player.py
[game powers]: ../game/headless/powers/status.py
[game deck]: ../game/headless/core/deck.py
[game monsters]: ../game/headless/monsters/overgrowth.py
[game map]: ../game/headless/map/graph.py
[game rewards]: ../game/headless/run/rewards.py
[game rooms]: ../game/headless/run/rooms.py
