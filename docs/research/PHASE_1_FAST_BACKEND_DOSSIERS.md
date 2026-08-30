# Phase 1 Fast-Backend Candidate Dossiers

- **Audit type:** revision-pinned static inspection only
- **Target:** Slay the Spire 2 `v0.107.1`, Steam build `23811903`
- **Target identity:**
  [`sts2-steam-main-build-23811903-macos-universal.json`](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json)
- **Parent plan:** [`PHASE_1_INTEGRATION_SPIKE.md`](../PHASE_1_INTEGRATION_SPIKE.md)
- **Local project revision:** `3d3b12e4803de72c30d0d10f71558d9f66420ec7`
- **Inspected third-party revisions:**
  [`wuhao21/sts2-cli@d11aa88`](https://github.com/wuhao21/sts2-cli/commit/d11aa883b582dd68bd39b331f3370746b30d447e)
  and
  [`zhiyue/sts2-rl-agent@1b7e7ce`](https://github.com/zhiyue/sts2-rl-agent/commit/1b7e7ce35e608722650763938c153ea8bc370333)

No third-party candidate was cloned, installed, built, or executed. No personal
profile or save was inspected. Therefore no candidate has passed compatibility,
fidelity, determinism, reliability, snapshot, or performance gates.

## 1. Evidence vocabulary and static disposition

- **Upstream claim** means a statement in the pinned project's documentation;
  it was not reproduced here.
- **Source-verified** means the property is directly visible in the pinned
  source, tests, or build files. It does not imply correct runtime behavior.
- **Unknown** means an executable target-build experiment, live differential
  corpus, or rights review is still required.

| Candidate | Best supported role after static audit | Do not assign yet | License / reuse category | Principal knockout risk |
| --- | --- | --- | --- | --- |
| `ENGINE-CLI` — `sts2-cli` | Optional, locally built engine-hosted compatibility and corpus probe | Search backend, fidelity authority, distributable dependency | Authored source declares `MIT`; copied/patched game assemblies and extracted game data are outside that grant | No arbitrary snapshot/branching; behavior-changing patches and recovery mutations; older build coupling |
| `PY-PRIOR` — `sts2-rl-agent` | Reference-only design and validation inventory | Code dependency, production simulator, search backend | No license found: SPDX `NOASSERTION`, reference-only; committed decompiled game source adds a separate provenance boundary | No reuse permission; exact parity and live full-run flow unproved; no snapshot API; lossy fixed policy contract |
| `PROJECT-PY` — this repository | Keep as project-owned `combat_v0`, bounded search laboratory, and future backend-adapter seed | Final full-game contract or full-run simulator | No repository license or package license field found: SPDX `NOASSERTION`; project-internal code can continue to be developed, but external distribution terms remain unset | Combat-only coverage and private implementation-coupled cloning |

**Static recommendation:** preserve `PROJECT-PY` and put a backend-neutral
adapter beside it. If the user accepts the local assembly and rights boundary,
test `ENGINE-CLI` only as an engine-hosted evidence path. Treat `PY-PRIOR` as
reference-only. Do not select a production fast backend until the executable
tests in section 6 pass.

## 2. `ENGINE-CLI`: `wuhao21/sts2-cli@d11aa88`

### 2.1 Identity, dependencies, and assembly boundary

**Source-verified**

- The commit is dated May 30, 2026 and predates the pinned target release. The
  code contains explicit adaptation comments for **STS2 build `23372702`**, not
  target build `23811903`; see
  [`RunSimulator.cs`](https://github.com/wuhao21/sts2-cli/blob/d11aa883b582dd68bd39b331f3370746b30d447e/src/Sts2Headless/RunSimulator.cs).
- The host targets .NET 9, uses project-supplied Godot stubs, and references a
  local game assembly and its dependencies; see
  [`Sts2Headless.csproj`](https://github.com/wuhao21/sts2-cli/blob/d11aa883b582dd68bd39b331f3370746b30d447e/src/Sts2Headless/Sts2Headless.csproj).
  The Python front end requires Python 3.9+ according to the
  [README](https://github.com/wuhao21/sts2-cli/blob/d11aa883b582dd68bd39b331f3370746b30d447e/README.md).
- [`setup.sh`](https://github.com/wuhao21/sts2-cli/blob/d11aa883b582dd68bd39b331f3370746b30d447e/setup.sh)
  copies `sts2.dll` and listed dependencies from a user-owned Steam install into
  the repository's `lib/`, retains `sts2.dll.original`, downloads Mono.Cecil
  through NuGet, then rewrites the copied assembly. The IL patch makes
  `YieldAwaiter.IsCompleted` return true and makes an action-queue wait return a
  completed task. It deletes the copied unpatched `lib/sts2.dll` and replaces
  it with the derived patched DLL; it does not patch the Steam source file in
  place.
- Runtime Harmony patches additionally bypass waits/yields, replace
  localization behavior, intercept bundle selection, and special-case a card
  execution path. The host enables game test/debug facilities and constructs a
  test run through game singletons.

**License and reuse**

- [`LICENSE`](https://github.com/wuhao21/sts2-cli/blob/d11aa883b582dd68bd39b331f3370746b30d447e/LICENSE)
  is the MIT License, copyright Hao Wu 2025: SPDX `MIT` for the project's
  authored source.
- That file does not establish permission to redistribute the copied or patched
  game DLLs, nor game-derived localization files committed in the repository.
  Reuse category: **MIT source may be evaluated or adapted after provenance
  review; game binaries/data must remain outside our repository and require a
  separate local-use/distribution decision.** This is a classification for the
  project gate, not legal advice.

### 2.2 Run coverage and contracts

**Upstream claims**

- The README calls the host a real-engine headless CLI, says all five characters
  are playable, and says damage, cards, AI, relics, and RNG are identical to the
  game.

**Source-verified facts**

- The JSON loop exposes map selection, combat, card rewards, rest sites, events,
  shops, card/bundle selection, potion use, room exit/proceed, and terminal
  state. `Program.cs` also accepts `start_run`, `action`, `load_save`, `get_map`,
  `write_continue_save`, `set_player`, `enter_room`, `set_draw_order`, and
  `quit`; see
  [`Program.cs`](https://github.com/wuhao21/sts2-cli/blob/d11aa883b582dd68bd39b331f3370746b30d447e/src/Sts2Headless/Program.cs).
- Normal and privileged commands share one protocol. Actions primarily identify
  cards, targets, rewards, and options by their current list indices. There is
  no versioned decision ID, expected-state hash, candidate-lifetime ID,
  idempotency key, or typed commit outcome.
- Several phases are not faithful decision surfaces: treasure code automatically
  obtains the first relic; combat rewards automatically collect gold, relics,
  and potions while exposing card choices; act transitions and between-act
  healing are manually driven; an explicit boss-relic decision was not found in
  the inspected flow. These shortcuts disqualify the current protocol from a
  complete near-optimal full-run policy interface.
- Failure recovery can cancel/retry actions, use reflection/direct state
  mutation, and ultimately emit `game_over` to escape a stuck combat. The
  pinned [`bug.md`](https://github.com/wuhao21/sts2-cli/blob/d11aa883b582dd68bd39b331f3370746b30d447e/agent/bug.md)
  records an unresolved process EOF around slime splitting, an unverified
  Regent playability case, and unreliable Slice, Phantom Blades, Danse Macabre,
  and Doom-potion behavior. These are stronger evidence than the README's
  identity claim.
- The integration tests launch a locally built process against the copied game
  DLL and exercise representative map/combat/reward/rest/shop/event/save paths.
  Debug commands create convenient scenarios. They are not a target-build live
  differential suite.

**Unknown**

- Complete decision coverage, all-character/full-run completion rate, public
  information completeness, side-effect passivity, and semantic equivalence on
  build `23811903` remain unknown.

### 2.3 Determinism, snapshot/branching, and throughput

**Source-verified**

- Runs accept a seed, and the host delegates much randomness to the game engine.
  `set_draw_order` is a privileged test mutation, not a public chance-control
  contract.
- `load_save` consumes a native serialized run. `write_continue_save` writes the
  current map state, but for a non-map room it deliberately rolls serialization
  back to a pre-room checkpoint; the two pinned
  [save/load tests](https://github.com/wuhao21/sts2-cli/blob/d11aa883b582dd68bd39b331f3370746b30d447e/tests/test_save_load.py)
  cover a map checkpoint and the initial event. There is no arbitrary current
  combat/modal snapshot, in-memory restore, fork, or branch API.
- Global game managers and static host state imply one active simulation per
  process. Independent multi-process scaling is possible in principle but is
  not measured.
- No throughput benchmark or hardware-qualified performance result exists in
  the pinned repository. The
  [`play_full_run.py`](https://github.com/wuhao21/sts2-cli/blob/d11aa883b582dd68bd39b331f3370746b30d447e/python/play_full_run.py)
  driver starts one process per run and enforces a 500-step safety cap; it is a
  smoke driver, not a benchmark.

**Role consequence:** this revision is knocked out as a search backend. Its
possible value is a local engine-hosted corpus/compatibility probe, contingent
on target-build, fidelity, safety, and rights gates.

## 3. `PY-PRIOR`: `zhiyue/sts2-rl-agent@1b7e7ce`

### 3.1 Identity, dependencies, and provenance

**Source-verified**

- The commit is dated May 22, 2026 and predates the target release. No target
  Steam build or assembly hash is pinned in the inspected repository.
- [`pyproject.toml`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/pyproject.toml)
  requires Python 3.11+, Gymnasium 1.0+, and NumPy 1.26+; training extras add
  Stable-Baselines3, sb3-contrib, and PyTorch. Direct adoption would raise this
  project's Python 3.10 floor.
- The optional live bridge targets .NET 9 and Godot.NET SDK 4.5.1, references
  local `sts2.dll`/Harmony assemblies, uses wildcard BaseLib/ModAnalyzers
  package versions, and an assembly publicizer; see
  [`STS2BridgeMod.csproj`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/bridge_mod/STS2BridgeMod.csproj).
  It does not statically rewrite `sts2.dll`, but
  [`MainFile.cs`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/bridge_mod/MainFile.cs)
  applies runtime Harmony patches to unlock AutoSlay and accelerate waits and
  animation.
- The repository commits a large `decompiled/` game-source tree. That makes its
  implementation/reference provenance and any proposed redistribution a
  separate review item even if a software license is later added.

**License and reuse**

- No `LICENSE`, `COPYING`, `NOTICE`, SPDX declaration, or package license field
  was found at the exact
  [revision root](https://github.com/zhiyue/sts2-rl-agent/tree/1b7e7ce35e608722650763938c153ea8bc370333).
  A README statement about research/educational purpose is not a software
  license. SPDX: `NOASSERTION`; reuse category: **reference-only**. Do not copy
  source, tests, fixtures, or decompiled material into this project without an
  explicit license and provenance resolution.

### 3.2 Run coverage and contracts

**Upstream claims**

- The pinned
  [README](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/README.md)
  reports 577 cards, 260 powers, 121 monsters, 290 relics, 63 potions, 88
  encounters, 68 events, five characters, and a full-run simulator. These are
  inventory claims, not behavioral proof.

**Source-verified facts**

- `RunManager` implements phases for map, combat, card reward, boss relic, shop,
  rest site, event, treasure, and run over, and returns semantic dictionary
  actions; see
  [`run_manager.py`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/sts2_env/run/run_manager.py).
- The actual route configuration contains only `ACT_0`, `ACT_1`, and `ACT_2` in
  `ALL_ACTS`; see
  [`map/acts.py`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/sts2_env/map/acts.py).
  This agrees with the RunEnv's “Acts 0-2” description but conflicts with the
  README's four-act content statistic. Act-4 monster files existing in the tree
  do not make that content reachable in a normal run.
- The Gym contract is a fixed `float32[151]` observation and `Discrete(157)`
  action space. It reserves 115 combat actions, five map choices, seven card
  reward slots, three boss relics, ten shop actions, five rest actions, four
  event actions, one overloaded treasure/reroll slot, and seven acting-player
  selections; see
  [`run_env.py`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/sts2_env/gym_env/run_env.py)
  and
  [`action_space.py`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/sts2_env/gym_env/action_space.py).
  Masks use `min(...)` caps, so excess candidates are omitted rather than
  represented dynamically.
- The 20 run-level features contain only act/floor, HP ratio, gold, deck size,
  relic count, potion counts, phase, ascension, and elite/boss flags. They do
  **not** encode persistent deck identities, relic identities, potion identities,
  the map graph, or the identities/effects/prices of reward/shop/rest/event
  candidates. The combat vector likewise uses a compact fixed catalog encoding;
  see
  [`observation.py`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/sts2_env/gym_env/observation.py).
  An action mask communicates legality but not what a noncombat option means.
  The fixed Gym surface is therefore not an adequate near-optimal full-run
  information/action contract even if its rules were exact. The richer internal
  `RunManager` dictionaries are only a possible source for a future adapter.
- `STS2RunEnv.step()` logs internal exceptions and then converts them into a run
  loss. That is useful for keeping training alive but contaminates outcome data
  unless simulator faults are separately surfaced and excluded.
- The project's own
  [`PARITY_GAPS.md`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/docs/PARITY_GAPS.md)
  says exact parity is not guaranteed, calls for broader card/relic/RNG audit,
  says the bridge's normal full-run flow is not proven, and requires full-run
  replay or equivalent lifecycle proof before claiming exactness. Its
  [`PARITY_COVERAGE_BACKLOG.md`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/docs/PARITY_COVERAGE_BACKLOG.md)
  explicitly warns that direct source/test mentions are a coverage gate, not
  full behavioral proof.
- The bridge protocol uses request IDs for correlation and stable enemy slots,
  but its TCP server accepts one client and falls back to random actions after a
  timeout/disconnect; see
  [`PROTOCOL.md`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/docs/PROTOCOL.md).

**Unknown**

- Content and RNG compatibility with build `23811903`, complete reachable run
  coverage, live bridge reliability, public-state completeness, and the rate of
  simulator-fault losses remain unknown. The
  [`KNOWN_ISSUES.md`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/docs/KNOWN_ISSUES.md)
  notes version-sensitive Harmony signatures and scene paths.

### 3.3 Determinism, snapshot/branching, and throughput

**Source-verified**

- [`rng.py`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/sts2_env/core/rng.py)
  implements a .NET-compatible seeded generator with explicit seed and counter.
  `RunState` creates separately named streams for map, shuffle, rewards, shops,
  transformations, monster AI, targets, card generation, and other chance
  surfaces. This is promising deterministic structure, not proof that every
  call is assigned to the correct stream.
- No public `snapshot`, `restore`, serialized state, environment clone, or fork
  contract was found in `RunState`, `RunManager`, `CombatState`, or `RunEnv`.
  Pending choices and resumptions store lambdas/closures, making naïve pickle
  unsafe; arbitrary deepcopy correctness was not established. Seed/counter
  visibility alone cannot restore all mutable state or branch a run.
- The
  [`bridge_replay.py`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/sts2_env/parity/bridge_replay.py)
  harness can record normalized bridge state/action traces and replay supported
  phases into a purpose-built simulator scenario. This is useful test prior art,
  but it is not an arbitrary snapshot and its own docs say live full-run smoke
  validation is outstanding.
- The README's approximately 1,200 combats/s and 28,000 steps/s are upstream
  claims from
  [`scripts/benchmark.py`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/scripts/benchmark.py),
  which measures only random actions in `STS2CombatEnv` for 1,000 single-combat
  episodes. It provides no CPU identity, warm-up, repeated-run variance,
  correctness gate, full-run rate, snapshot/branch rate, or worker-scaling test.
  The displayed sample is internally inconsistent: 28,101 steps in 0.78 seconds
  is about 36,000 steps/s, not the displayed 28,101. No throughput claim should
  be carried into our architecture decision.

**Role consequence:** absent a license, this is reference-only. Even with
permission, it cannot be a search backend until arbitrary snapshots, isolated
branches, full state/candidate contracts, target-build differential fidelity,
and qualified throughput are demonstrated.

## 4. `PROJECT-PY`: current repository at HEAD

### 4.1 What is reusable now

**Source-verified**

- `CombatEnv` is a deterministic, inspectable single-combat environment with
  structured observations, explicit legal-action generation, stable enemy
  slots, and a separate learned encoding. Its seeded `random.Random` is shared
  with the deck and with enemies built through encounter factories; the legacy
  default `enemy_factory()` path instead constructs its own deterministic
  `Random(0)` enemy RNG.
- [`bruteforce.py`](../../game/analysis/bruteforce.py) implements bounded exact
  combat search. Its branch clone copies mutable combat state, copies each RNG
  through `getstate`/`setstate`, and preserves shared-RNG identity. Its
  transposition key includes turn, complete ordered piles, player/enemy mutable
  state, RNG aliasing, and RNG states. Search reports whether optimality was
  proved rather than treating a cutoff result as exact.
- Tests directly verify clone isolation and RNG aliasing, deterministic seeded
  behavior, stable targeting, legal masks, encoders, search proof/cutoff status,
  trace analysis, and worker infrastructure. The repository also has useful
  profiling and benchmark scaffolding.

These are reusable project foundations:

1. seeded RNG discipline and chance-boundary tests;
2. structured debug state separated from learned representation;
3. authoritative legal-action generation and target stability;
4. clone/state-key/search diagnostics;
5. deterministic fixture, trace, profiling, and benchmark practices;
6. the current mechanics only after live differential validation.

### 4.2 What must not become the final full-game contract

- The implementation covers one combat with a deliberately small card, enemy,
  and status set. It has no route/map, rewards, shops, events, rest, treasure,
  potions, relics, deck evolution, act transitions, profile, save/resume, or
  complete-run state machine.
- Its tuple action API and fixed global hand-slot/enemy-slot action grid are
  combat-prototype details, not a dynamic candidate contract. Its fixed catalog
  vector is a policy encoding, not canonical public state.
- `clone_combat_env` is optimized private Python cloning, not a versioned,
  serialized backend snapshot/restore contract. It knows concrete built-in card
  types and object internals. There is no run-level snapshot or cross-process
  branch contract.
- The exact search key includes draw-pile order and future RNG state. That is
  valid for privileged oracle/conformance analysis but must not leak into the
  deployed policy's public information state.
- Trajectories contain player-step transitions rather than a canonical ordered
  event stream. There are no run, decision, entity, candidate-lifetime,
  expected-state, idempotency, or commit-result identifiers.
- The repository has no `LICENSE` file and `pyproject.toml` declares no license:
  SPDX `NOASSERTION`. Continued internal development is natural because this is
  the project itself; choose explicit terms before external source/data/model
  distribution.
- No versioned raw simulator transitions/s or snapshot/s result at this exact
  revision establishes full-run or search throughput. Training-throughput and
  policy-evaluation benchmarks answer different questions.

**Integration boundary:** freeze this behavior as a named `combat_v0` research
adapter. Introduce canonical backend/public-state/candidate/snapshot/event
contracts beside it. Adapt the implementation to those contracts only after
the Phase 1 evidence gates; do not reshape the full-game architecture around
current `CombatEnv` internals.

## 5. Comparative role decision

| Required property | `ENGINE-CLI` | `PY-PRIOR` | `PROJECT-PY` |
| --- | --- | --- | --- |
| Target build `23811903` proven | Unknown; source names older `23372702` | Unknown; no build pin | No; independent prototype |
| Complete actor-visible full-run decisions | No: broad but auto-resolved/absent surfaces | Internal phases broad; fixed Gym contract omits essential semantics; only 3 configured acts | No: combat only |
| Deterministic replay proven | Seed input only; altered async/recovery behavior | Promising named RNG streams; live equivalence unknown | Proven for covered combat fixtures |
| Arbitrary snapshot/restore | No; map/pre-room native checkpoint only | No public API | Internal combat clone only, not versioned serialization |
| Isolated branching | No | Unknown / not exposed | Functional for covered in-process combat states; cost unqualified |
| Qualified throughput evidence | None | Unqualified combat-only upstream claim | Infrastructure exists; no accepted fast-backend result |
| Code reuse allowed | MIT authored source only; game boundary separate | No, reference-only | Yes inside this project; external license unset |
| Recommended static role | Optional local engine/corpus probe | Reference-only | `combat_v0` and search foundation |

The likely architecture remains hybrid: an independently controlled live path
is semantic authority; a project-owned simulator supplies training and search;
both implement the same versioned contracts and are continuously compared.
This table does not yet select either third-party project as a dependency.

## 6. Exact executable validation queue

All measurements must record source revision, target manifest, toolchain,
machine/CPU, OS, configuration, warm-up, repetitions, failure counts, and the
hash of every corpus/fixture. Privileged fixture state must be excluded from the
actor projection.

### 6.1 `ENGINE-CLI` tests

1. **Rights and artifact boundary:** decide permitted local-use/distribution
   mode. In a disposable source/build directory, hash the pristine Steam
   assemblies before and after setup; assert the installation files are
   unchanged, enumerate every copied/derived output, and prohibit committing or
   packaging those outputs.
2. **Compile compatibility:** build the exact revision against build `23811903`
   with pinned .NET/NuGet inputs. Record every missing/changed type or member and
   every runtime-patch target. A compile pass is not a fidelity pass.
3. **Decision inventory:** drive one controlled fixture for every canonical
   decision kind—map, combat, nested card choice, potion, card/relic/potion
   reward, boss relic, shop purchase/removal/leave, rest, event branch,
   treasure, act transition, death, victory. Fail if a player choice is
   auto-resolved or cannot carry stable candidate identity.
4. **Differential trace:** for each accepted fixture, replay identical public
   actions through the normal pinned live game and engine host. Compare ordered
   public states, legal candidates, outcomes, events, and RNG-visible results;
   classify every difference. Debug commands may construct fixtures but cannot
   count as policy actions.
5. **Replay:** start the same seed in three fresh processes and compare complete
   normalized trace hashes. Repeat after stop/restart. Instrument and fail on
   cancellation, reflection fallback, forced state mutation, or forced
   `game_over`.
6. **Snapshot/fork:** at map, combat before/after draw, pending card selection,
   reward, shop, and event states, snapshot and restore into two fresh
   instances. Replay the same 100-decision suffix and require identical hashes;
   then choose two legal branches and require the parent to remain unchanged.
   The current API is expected to fail outside its limited map/pre-room save.
7. **Regression stress:** run targeted Leaf Slime split, Particle Wall, Slice,
   Phantom Blades, Danse Macabre, Doom potion, Vantom, reward, and relic-session
   fixtures 100 times each with zero EOF, deadlock, forced-loss, or unexplained
   divergence.
8. **Performance:** after 10 warm-up runs, measure five 60-second samples at
   1/2/4/8 independent processes. Report committed decisions/s, complete runs/h,
   p50/p95/p99 latency, CPU, peak RSS, startup time, error rate, and scaling
   efficiency. Measure snapshot/restore and branch creation separately if they
   become available.

### 6.2 `PY-PRIOR` tests

1. **License/provenance gate first:** obtain explicit software reuse permission
   and resolve the decompiled-source/content boundary. If not resolved, perform
   no executable or code-integration work and retain reference-only status.
2. **Target content manifest:** enumerate every reachable character, card,
   relic, potion, monster, encounter, event, act, ascension rule, and modifier
   against build `23811903`; distinguish registered, reachable, tested, and
   live-conformant counts. Inventory equality alone is not a pass.
3. **Contract alias test:** create paired noncombat states with equal
   151-vectors/masks but different decks, relics, potions, map branches, rewards,
   shop inventory, prices, rest choices, or event effects. Require the future
   canonical projection and candidate features to distinguish every
   decision-relevant pair; the current Gym contract is expected to fail.
4. **Capacity test:** construct legal states with more than five route choices,
   six reward cards, ten shop actions, four event choices, five enemies, ten
   hand cards, nine potion slots, or seven selectable players wherever the
   target permits them. Require no silent truncation, overloaded meaning, or
   index drift.
5. **Snapshot/fork:** define a versioned snapshot and round-trip every phase,
   including pending callbacks/choices. Restore twice, replay a 100-decision
   suffix, compare complete state plus every RNG stream/counter, then branch all
   legal actions with parent isolation. Naïve pickle/deepcopy is not an accepted
   substitute.
6. **RNG differential:** use target-build live fixtures to compare stream
   selection, call count, inclusive/exclusive bounds, shuffle order, map/event/
   reward generation, monster AI, and clone/instance-ID behavior. Record the
   first divergent random boundary.
7. **Full-run differential:** replay a preregistered corpus spanning the target
   Ironclad scope, configured Ascensions, every target-build act, events, shops,
   nested choices, and known high-risk interactions. Compare every canonical
   event and checkpoint; never convert a simulator exception into a gameplay
   loss in the conformance result. Audit the other advertised characters later
   as a separate breadth claim, not as an initial-target blocker.
8. **Performance:** run the same five-by-60-second protocol for combat decisions,
   full-run decisions, snapshots, restores, and one-ply branches at 1/2/4/8
   workers. Publish both correctness-on and correctness-off results; do not reuse
   the README sample as baseline evidence.

### 6.3 `PROJECT-PY` tests before expanding its role

1. Freeze current supported mechanics, observation/action meaning, fixtures,
   and trace hashes under a named `combat_v0` adapter; keep the existing API
   available to current experiments.
2. For every supported card, enemy, status, target shape, and stochastic
   boundary, compare canonical events and outcomes to build `23811903`. Label
   uncovered content unsupported rather than approximate.
3. Add adapter conformance tests proving that public state omits pile order and
   future RNG while privileged oracle state preserves both. The actor and oracle
   projections must be impossible to confuse by type/configuration.
4. Specify and test a versioned serialized combat snapshot independent of
   `clone_combat_env`; require round-trip equality, RNG-alias preservation,
   cross-process restore, all-legal-action parent isolation, and stale-version
   rejection.
5. Benchmark normal step, structured projection, encoding, clone, serialized
   snapshot/restore, state hashing, and branch expansion with the common
   measurement protocol. Set thresholds only after the live corpus and intended
   search workload are known.
6. Do not call `PROJECT-PY` a full-run backend until map through terminal run
   phases, persistent content, canonical events/candidates, save/resume, and
   target-build differential gates exist behind the shared contract.

## 7. Decision record for the next increment

- **Keep:** `PROJECT-PY` as `combat_v0` and the immediate search/testing
  foundation.
- **Probe only if authorized:** `ENGINE-CLI`, in a disposable local build, for
  target-compatibility and corpus-generation evidence.
- **Reference only:** `PY-PRIOR`; borrow questions and test ideas, not code or
  fixtures.
- **Do not freeze:** either third-party protocol, either fixed Gym vector/grid,
  or the current private clone as the project's full-game interface.
- **Revisit selection after:** exact-build compilation, complete decision
  inventory, live differential traces, arbitrary snapshot/fork tests, qualified
  throughput, and the relevant rights decisions.
