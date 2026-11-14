# Where the network search's time goes — 2026-11-13

Status: **diagnostic profile**, with no strength claim. Three of its
candidates were implemented the same day; see the
[follow-up](#follow-up-same-day-the-three-contained-changes). A
[second follow-up](#follow-up-2026-11-14-shared-card-descriptions) the next
day reuses shared card descriptions. Together search is 1.72 times faster with
identical decisions. The
user approved the profile after the
[96-simulation benchmark](COMBAT_SEARCH_BENCHMARK_2026_10_17.md#follow-up-2026-11-13-96-simulations-on-the-boss-fights)
showed that search strength is limited by cost.

## Result

Almost four fifths of the search time is spent handling the public observation
of each simulated step. The network itself takes under a tenth, and so do the
game rules.

| Work inside a search | Share of search time |
| --- | ---: |
| Build the public observation from the simulated engine | 20.1% |
| Copy and check that observation | 24.5% |
| Encode it into network inputs | 23.3% |
| Compute keys from it, and the prediction cache | 11.3% |
| **Handling the observation, total** | **79.2%** |
| Run the network | 9.5% |
| Game rules: apply a command | 5.2% |
| Game rules: copy the fight for a simulation | 4.7% |
| Tree search, belief sampling and bookkeeping | 1.3% |

One simulation builds 6.5 observations, runs the network 4.0 times and applies
5.7 commands. An observation holds about 250 nodes: the whole deck, the piles,
relics, potions, enemies, the map and the action history. Every step builds it
from scratch, although one card play changes only a few nodes.

- **The run's `inference` timer is mostly encoding.** Of its 35.4%, encoding the
  observation is 23.3 points, the network 9.5 and the prediction cache 2.6. A
  faster network or a GPU would not help much.
- **The run's `projection` timer is more than half copying and checking.** Of
  its 44%, the copy is 20.4 points and the check 4.2. Building card
  descriptions and the text signatures that sort equal cards takes 14.3 points.
- **Reference paths are recomputed for every candidate action.** `_paths` walks
  the whole observation about 51 times per simulation (3.2%); once per
  observation would do.
- **Leaf rollouts are 54.8% of the search time.** Each simulation ends with up
  to four greedy steps, and each step builds, copies, encodes and evaluates a
  full observation.

## Candidates

None was implemented when the profile was taken; the first three were done the
same day, with signatures only for the third (see the [follow-up](#follow-up-same-day-the-three-contained-changes)). The
share is the measured time of the work that would go.

| Change | Share of search time | Same results | Size |
| --- | ---: | --- | --- |
| Take ownership of an observation the projection has just built without copying it | 20.4% | yes | Small. Changes an ownership guarantee of public observations, so it needs the independent review |
| Compute reference paths once per observation | about 2.8% | yes | Small and contained |
| Reuse card descriptions and signatures across steps | part of 14.3% | yes | Small to medium; their cache is discarded after every observation by design |
| Reuse the unchanged parts of the observation between steps, so that building, copying, keys and encoding touch only what changed | targets the 79% | yes | A redesign of the projection and encoding path |
| Shorter or cheaper leaf rollouts | part of 54.8% | no | A search change. Measured the same day: at equal time, no rollouts lose 3.8 boss points and two steps are level with four; see the [rollout test](COMBAT_SEARCH_BENCHMARK_2026_10_17.md#follow-up-2026-11-13-leaf-rollouts-at-equal-search-time) |

The first three together remove about a quarter of the search time, which is
1.3 to 1.4 times faster. A gain of several times needs the fourth.

The fourth has room. On 120 recorded boss fights an observation holds 242 nodes
on average, and 70% of them sit in sections that are identical to the previous
decision. The deck and the map alone are 52% of the nodes and never change
during a fight; the hand, the discard pile and the history change at almost
every step (`runs/combat-search-profile-20261113/observation_change.py`).

Search is deterministic, so a result-identical change can be accepted on a
strict test: the same choice and the same visit counts for every decision of
the benchmark's boss fights.

## What it means

On the bosses, four times the simulations bought 4.7 points, about 2.3 points
per doubling. If that rate holds:
- 1.35 times faster search is worth about 1 boss point at equal time;
- 4 times faster is worth about 5.

Neither closes the 21 points between 96-simulation search and the solver. The
contained changes still shorten every later search run and label collection by
about a quarter.

## Method and checks

- The first six validation boss openings of the benchmark corpus (five bosses),
  with the settings of the search benchmark at 24 simulations, on one worker:
  122 searched decisions, 2,971 simulations and 119.7 s of search.
- Wall-clock timers were wrapped around 36 named functions. Each function's
  own time excludes the other timed functions, and only calls made from inside
  a search are counted, so the own times add up to the search total exactly.
- The timed run had the same outcome and length as the unpatched benchmark run
  in all 12 episodes.
- The run's own timers agree with the full benchmark runs: projection 42% and
  inference 34% here, 43% and 35% on all 589 fights at 24 simulations, 45% and
  35% at 96.
- Call counts were cross-checked with a cProfile run on two fights.

## Limits

- Six fights and 24 simulations. The run's own timers show the same shares at
  96 simulations, but the breakdown inside them was not timed there.
- One worker on an otherwise idle machine: 0.98 s per searched decision,
  against 1.51 s with 16 workers in the benchmark run.
- The wrappers add an estimated 1% or less, mostly to the two card functions,
  which are called about 800 times per simulation.
- The candidate shares are upper bounds on the saving. No change was built or
  timed.
- A first attempt with a sampling thread was discarded. Its samples slid to
  the next call that releases the interpreter lock, so it put inference at 75%
  against the timers' 34%.

## Reproduce

```bash
.venv/bin/python runs/combat-search-profile-20261113/search_profile.py timers timers24 24 6
.venv/bin/python runs/combat-search-profile-20261113/analyze.py timers24 \
  runs/combat-search-profile-20261113/timers24.analysis.json
```

They use the corpus at `runs/combat-benchmark-20261113/corpus-planning`.
Analysis output `timers24.analysis.json`, SHA-256 `55603b7f…`.

Elapsed times: the timed run took 134 s, the cProfile run 136 s and the
discarded sampling run 510 s. About 20 minutes passed between the first run and
the final breakdown, including three harness corrections. User wait: none.

## Follow-up, same day: the three contained changes

Status: **implemented and verified**. The user approved the three contained
candidates. Search makes exactly the same decisions and is **1.35 times
faster** in the benchmark setting.

| Setting | Before | After | Faster by |
| --- | ---: | ---: | ---: |
| 589 boss fights, 24 simulations, 16 workers: search time | 22,696 worker-s | 16,845 worker-s | 1.35× |
| The same run: time per searched decision | 1.51 s | 1.12 s | |
| The same run: wall time | 1,518 s | 1,146 s | |
| Six boss fights, one worker: search time | 119.7 s | 79.6 s | 1.50× |

**What changed.**
1. **Search worlds keep the observation they have just built.**
   `PreparedPublic.adopt` checks that the graph consists of exact record types,
   runs the same validation as before and then keeps the object instead of
   copying it. Any other input still goes through the constructor. Only
   `SimulationWorld.project` asks for it; the live adapter still receives a
   private copy.
2. **Reference paths are computed once per observation.** `action_keys` and
   the two observation keys share one walk.
3. **Card signatures are reused across observations.** A bounded cache keyed
   by the description's typed fields and its child objects replaces the
   repeated JSON. It serves every projection, the live adapter's included.

| Work inside a search, six fights on one worker | Before | After |
| --- | ---: | ---: |
| Build the public observation | 24.1 s | 15.1 s |
| Copy and check that observation | 29.4 s | 6.9 s |
| Encode it into network inputs | 27.9 s | 26.5 s |
| Compute keys from it, and the prediction cache | 13.5 s | 8.5 s |
| Run the network | 11.3 s | 10.5 s |
| Game rules: apply a command | 6.2 s | 5.7 s |
| Game rules: copy the fight for a simulation | 5.6 s | 4.9 s |
| Tree search, belief sampling and bookkeeping | 1.6 s | 1.4 s |
| **Total** | **119.7 s** | **79.6 s** |

Encoding the observation is now the largest part, a third of the search time.
Handling the observation is still 72% in total; the network is 13% and the game
rules 13%.

**Checks.**
- The 24-simulation run on all 589 boss fights was repeated on the changed
  sources (build `188484ae…`, corpus `act1_combat_corpus_v2:31c16ec4…`) and
  compared with the run before the change:
  - all 1,178 episodes have the same outcome and length;
  - all 40,442 trajectory records are equal, apart from build and episode
    identity;
  - all 19,260 searched decisions are equal in choice, improved policy, action
    values, visit counts, leaf work and tree work.
- One independent review found nothing blocking. It compared the new type
  check with the copying reader on 100,000 mutated observations, checked about
  150,000 signatures against the uncached function, and replayed small
  searches with and without the change. Its two notes on wording and an unused
  import are applied.
- `tests/agent`: 1,875 passed, 22 of them new. They cover the agreement of the
  type check with the copying reader, adoption and its fallback, the unchanged
  private copy on the adapter path, signature reuse with exact scalar types,
  and the single path walk.

**Limits.**
- The gain is smaller with 16 workers than with one. In the 16-worker run the
  time inside the run's `inference` timer rose by 8% (7,893 to 8,521 s), while
  it fell by 6% on one worker. An observation that is no longer copied lies
  scattered in memory, which may cost more when 16 processes compete for
  cache; this explanation is not tested.
- The speed-up was measured at 24 simulations only.
- Card descriptions are still rebuilt for every observation (10% of the
  search time after the change).
- Adoption is asserted in tests for a plain search world. That the benchmark's
  belief worlds adopt as well follows from the timing: 0.06 copies per
  simulation remain, against 6.6 before.
- The review did not execute the receipt-based belief worlds or the real
  checkpoint path; the 589-fight comparison covers both.

**Reproduce.**

```bash
sh runs/combat-search-speed-20261113/run.sh
.venv/bin/python runs/combat-search-speed-20261113/compare.py \
  runs/combat-search96-20261113/s24 runs/combat-search-speed-20261113/s24 \
  runs/combat-search-speed-20261113/comparison.json
```

The recorded comparison is `comparison-final.json` (SHA-256 `e8943eeb…`), from
the run in `s24-final` on the final sources; `s24` holds an identical earlier
run that preceded two edits without effect on behaviour. The one-worker
breakdown is `runs/combat-search-profile-20261113/timers24-fast.analysis.json`
(`784c83d5…`).

Elapsed times: the two 589-fight runs took 1,181 s and 1,146 s, each corpus
rebuild about four minutes, the review 16 minutes and the agent tests 130 s
(not reproduced: the same suite took about ten minutes on 2026-11-14, on the
committed sources as well).
The whole change took roughly 70 minutes from approval to the final
comparison, most of it benchmark runs. User wait: none.

## Follow-up, 2026-11-14: shared card descriptions

Status: **implemented and verified**. The user approved a further speed step.
Search makes exactly the same decisions and is **1.28 times faster** in the
benchmark setting, **1.72 times** with the changes of the day before.

| Setting | Before | After | Faster by |
| --- | ---: | ---: | ---: |
| 589 boss fights, 24 simulations, 16 workers: search time | 16,845 worker-s | 13,169 worker-s | 1.28× |
| The same run: time per searched decision | 1.12 s | 0.88 s | |
| The same run: wall time | 1,146 s | 911 s | |
| Six boss fights, one worker: search time | 79.6 s | 65.4 s | 1.22× |

**The idea.** A card's printed spec and its mechanics are description nodes
below the card. They make up 39% of an observation's nodes and hold 61% of its
fields, and the projection already used one immutable object for each distinct
definition. Readers of an observation now keep what they derive from such an
object and look it up by object instead of reading its fields again.

**What changed.**
1. **A registry of shared descriptions** in the observation contract.
   `share_description` accepts only an exact record tree without references or
   links that passes every per-node check of `validate`. The card projection
   registers each spec and mechanic whenever it uses it.
2. **Six readers reuse their result for a registered description:** the
   exactness check and `validate`, the public key, the mapping traversal of the
   encoder, the feature rows, and the combat channels. Each keeps its own store
   and confirms the object itself, never only its id.
3. **Card definitions are described once per object.** `cached_static` returns
   the description it built for the same frozen spec or effect before.
4. **Bounded stores.** The registry and every store are emptied at 4,096
   entries and refill from use.

Only search worlds see registered descriptions. Every other projection still
returns a private copy with fresh nodes, so PPO rollouts, recordings and the
live adapter take the unchanged paths.

| Work inside a search, six fights on one worker | Before | After |
| --- | ---: | ---: |
| Build the public observation | 15.1 s | 13.9 s |
| Check that observation | 6.9 s | 4.6 s |
| Encode it into network inputs | 26.5 s | 15.7 s |
| Compute keys from it, and the prediction cache | 8.5 s | 8.3 s |
| Run the network | 10.5 s | 10.5 s |
| Game rules: apply a command | 5.7 s | 5.7 s |
| Game rules: copy the fight for a simulation | 4.9 s | 5.5 s |
| Tree search, belief sampling and bookkeeping | 1.4 s | 1.2 s |
| **Total** | **79.6 s** | **65.4 s** |

Handling the observation is now 65% of the search time; the network is 16% and
the game rules 17%. Encoding and building are level as the largest parts.

**Checks.**
- The 24-simulation run on all 589 boss fights was repeated on the changed
  sources (build `35020aae…`, corpus `act1_combat_corpus_v2:a253e8a0…`, with
  the same 589 boss openings) and compared with the run of the day before:
  - all 1,178 episodes have the same outcome and length;
  - all 40,442 trajectory records are equal, apart from build and episode
    identity;
  - all 19,260 searched decisions are equal in choice, improved policy, action
    values, visit counts, leaf work and tree work.
- One independent review, in two rounds, found nothing blocking.
  - It compared every reader with the committed implementation on 39 searched
    observations and 105 constructed ones, each read twice: no difference in
    any result or error.
  - It then emptied the registry and every store at random moments inside the
    readers, about 174,000 times in the heaviest run: no difference.
  - Its notes are applied: the stores recover at their limit instead of
    refusing new entries for good, a kept mapping summary is tied to its
    reference pattern, and an encoder drops kept rows when its names change.
- `tests/agent/test_shared_descriptions.py`, 34 tests, compares every reader on
  a search observation with the same reader on a private copy of it, where
  nothing is registered. It also covers the capacity errors of the mapping at
  every boundary, descriptions that must not be registered, depth limits,
  entries kept for another object, emptied stores, and encoders with their own
  entity check. Two deliberate faults were each caught.

**Limits.**
- The gain is below the 1.5 times estimated beforehand. The descriptions hold
  most fields, but the card, map and history nodes still have to be read at
  every step.
- The public key gained little (8.5 s to 8.3 s for keys and cache), although
  the key of a single opening observation was 1.6 times faster in isolation.
  The cause is not examined.
- With 16 workers the gain is larger than with one (1.28 against 1.22 times).
  The day before it was the other way round; neither is explained.
- A frozen spec or effect that is rewritten through `object.__setattr__` would
  keep its old description. Nothing in the engine does that.
- Temporary modified specs (enchanted or permanently grown cards) add entries
  at every step and so empty the stores more often. This costs speed only.
- The 589-fight run started on an idle machine; a research session in the same
  checkout had finished its analysis by then.
- Not done: reusing the map and the deck section between steps. The map is
  26% of the nodes and rebuilt for every observation.

**Reproduce.**

```bash
sh runs/combat-search-descriptions-20261114/run.sh
.venv/bin/python runs/combat-search-speed-20261113/compare.py \
  runs/combat-search-speed-20261113/s24-final runs/combat-search-descriptions-20261114/s24 \
  runs/combat-search-descriptions-20261114/comparison.json
.venv/bin/python runs/combat-search-profile-20261113/search_profile.py timers timers24-shared 24 6 \
  runs/combat-search-descriptions-20261114/corpus/corpus.json
```

The recorded comparison is `comparison.json` (SHA-256 `74d0671f…`) and the
one-worker breakdown `timers24-shared.analysis.json` (`e44dbd37…`).

`tests/agent`: 1,911 passed in 574 s. The committed sources take as long: run
side by side, a scratch copy of them took 637 s and the working tree 600 s.

Elapsed times: the 589-fight run took 914 s, two corpus rebuilds 235 s and
208 s, the two review rounds 500 s and 303 s, and the one-worker breakdown
78 s. User wait: none.
