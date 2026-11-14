# Determinized planner under public information on the boss benchmark — 2026-11-12

Status: **complete experiment.** A new experimental player with no network and
no training, measured on the 589 boss fights of the
[boss and elite benchmark](BOSS_ELITE_BENCHMARK_2026_10_17.md). No default
changed. The user asked for it after the
[ceiling measurement](COMBAT_CEILING_2026_11_12.md), to see how much of the
perfect-information gap survives without hindsight. It is not the production
search path and not a deployable agent (see Limits). Validation fights only; no
episode may become training data.

## Result

| Player, 589 boss fights, equal weight | Win rate | 95% interval | Thinking time |
| --- | ---: | --- | --- |
| Best network alone | 48.7% | 44.7–52.3% | none |
| Planner, 1 sampled world, 1 line | 49.8% | 46.3–53.7% | 0.4 s per decision |
| Network with search, 24 simulations | 55.5% | 51.8–59.3% | 1.9 s per searched decision |
| **Planner, 8 sampled worlds, 4 lines each** | **59.6%** | 55.9–63.2% | 5.3 s per decision |
| Perfect-information solver (hindsight, not a player) | 81.6% | 78.7–84.6% | not a player |

| Paired on the same 589 fights | Difference | 95% interval | Fights won by only one of the two |
| --- | ---: | --- | --- |
| Planner 8×4 − network with search | **+4.1** | +0.5 to +7.7 | 73 against 50 |
| Planner 8×4 − best network | +10.9 | +7.4 to +14.7 | 99 against 35 |
| Planner 8×4 − planner 1×1 | +9.8 | +6.4 to +13.2 | 84 against 25 |
| Planner 8×4 − perfect-information solver | −22.0 | −25.4 to −18.8 | 0 against 126 |
| Planner 1×1 − best network | +1.2 | −2.5 to +5.0 | 67 against 62 |
| Planner 1×1 − solver with a single line | −1.2 | −3.5 to +1.2 | 20 against 26 |

| Boss | Fights | Best network | Search | Planner 1×1 | Planner 8×4 | Solver |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Ceremonial Beast | 100 | 78.0% | 82.0% | 73.0% | 86.0% | 97.0% |
| The Kin | 100 | 48.0% | 60.0% | 42.0% | 49.0% | 76.0% |
| Vantom | 120 | 55.0% | 63.3% | 50.8% | 66.7% | 82.5% |
| Lagavulin Matriarch | 85 | 28.2% | 35.3% | 32.9% | 41.2% | 74.1% |
| Soul Fysh | 97 | 59.8% | 66.0% | 77.3% | 81.4% | 96.9% |
| Waterfall Giant | 87 | 23.0% | 26.4% | 23.0% | 33.3% | 63.2% |

| Boss entered with | Fights | Search | Planner 8×4 | Solver |
| --- | ---: | ---: | ---: | ---: |
| under 50% HP | 35 | 4 | 9 | 17 |
| 50–70% HP | 106 | 35 | 44 | 66 |
| 70–85% HP | 95 | 48 | 47 | 76 |
| 85% HP or more | 353 | 248 | 258 | 325 |

## What it means

**A planner with no network and no training beats the current best agent on
bosses.** It decides from public information only, ranks states by five
hand-set numbers, and wins 59.6% against 55.5% for the network with search. The
paired interval excludes zero, narrowly. It is ahead on five of the six bosses.

**Looking ahead along several lines is what helps.** One sampled world with one
line only matches the best network (49.8% against 48.7%). Eight worlds with four
lines each add 9.8 points.

**Hindsight itself is worth little for one line and a lot beyond it.** The
one-line planner is within about a point of the one-line perfect-information
solver. Against the full solver the 8×4 planner is 22 points short. How much of
that a larger budget or a learned evaluation can recover is not measured.

**The Kin is the exception.** The planner wins 49% there against 60% for search.
The suspected cause was that it counts damage to the Kin's followers as progress
although they die with the Priest. A [follow-up](#follow-up-2026-11-13-the-kin-and-the-progress-measure) did not confirm
this; the cause is open.

**It is slow in its present form.** 5.3 s per decision in Python, about three
times the search's time, because every simulated command restores a full engine
snapshot.

## How it decides

Each decision uses these steps (`runs/combat-public-planner-20261112/planner.py`,
SHA-256 `ea1ebe4f…`):

1. **Sample hypothetical worlds.** Each world is a copy of the fight with its
   hidden parts replaced. The free draw-pile cards are put in a canonical order
   and shuffled with the planner's own seed. Every combat RNG stream is advanced
   at least 2,049 draws.
2. **Plan in each world.** The beam search of the ceiling experiment runs inside
   the world under a fixed budget of engine commands. Inside a world its sampled
   draw order is that world's truth. The world's best line gets a value: 1 for a
   win, 0.25–0.75 for a line still alive when the budget ends, by its balance of
   own HP against enemy HP, and 0–0.25 when every kept line dies.
3. **Vote.** Each world backs the next move of its line with that value. Moves
   are named by public content (the card's printed state or the potion's kind,
   and the target), never by an internal card ID.
4. **Act and follow.** The winning move is applied to the real fight. Worlds
   that backed it, and whose public observation still equals the real one, are
   followed without new planning. When none is left, new worlds are sampled.
   The public observation is the digest of the public adapter's own projection.

| Setting | Worlds | Lines per world | Engine commands per world | Selection rule |
| --- | ---: | ---: | ---: | --- |
| 8×4 (`p8w4`) | 8 | 4 | 800 | pareto |
| 1×1 (`p1w1`) | 1 | 1 | 400 | scores |

Both settings were fixed before any benchmark fight was played, and both are
reported. Seeds depend only on the fight's public start digest, the number of
decisions so far and the world index.

**Outcomes.** All 1,178 episodes were replayed through the benchmark's public
adapter with the ceiling experiment's `verify`: every move was exactly one
advertised candidate that `commit_decisions_v1` allows, and the recorded outcome
is the adapter's own combat summary. No episode failed, was cut off or
disagreed with the planner's own count. The longest has 70 decisions.

## The information boundary

Only step 1 reads the real engine's hidden state, and only to replace it.

- **Draw order.** The author's checks took 281 real decision states from 24
  fights, gave each a different real draw order and sampled 1,124 worlds. The
  worlds were byte-identical whatever the real order was, and 103 full decisions
  were identical. None of the worlds sampled from the 234 states with a mixed
  pile had the real order.
- **Public facts.** Every one of those worlds projected the same public
  observation as the real state.
- **Random outcomes.** A sampled world cannot be reseeded, because the engine
  validates its streams against the run seed. Its streams are the real ones
  advanced at least 2,049 draws. A real fight drew at most 271 numbers from any
  one stream, so a world never sees a number the real fight will use. The hidden
  stream state therefore enters only as extra pseudo-randomness.
- **Other sources.** While a fight continues, the engine draws only from six of
  its nine combat streams. It constructs no other generator and never calls
  Python's random module. This was audited on all 1,178 episodes.

Three exceptions were found by the review. None can move the boss rate here.

1. **A choice among draw-pile cards with equal copies.** The engine lists the
   candidates in pile order, so the real fight takes the lowest equal copy. This
   happened in 1 of 19,273 decisions of the 8×4 planner and 1 of 19,098 of the
   1×1 planner.
2. **The public digest in that same state.** The projection numbers equal
   draw-pile copies in physical order, so the digest depends on the pile order
   there. One state per setting.
3. **Cards whose enchantment fixes their position** (Imbued, Perfect Fit) keep
   their real position in every world, and that position can be hidden. None of
   the 589 boss or 1,139 elite openings has such a card.

## Independent review

One independent review judged the claim "decisions use only public
information" **sound with the stated exceptions, with no blocking issue**, and
the recorded outcomes to be the benchmark's own. What it ran:
- RNG instrumentation on engine replays of the episodes: the sources and draw
  counts above. The author reran its script on all 589 episodes of the 8×4
  planner after the runs finished.
- Twin states that differ only in hidden state, kept in step through whole
  fights: 794 world pairs byte-identical under a reordered pile; under a shifted
  RNG, 846 world pairs differed only in RNG or in which copy of an equal card
  sits where.
- A census of 589 openings and 34,868 decision states: no pre-rolled value in
  enemy fields or relic memory, and no enemy turn, autoplay batch or deferred
  hook ever pending at a decision.
- `verify` on 48 episodes of both settings, wins and losses for every boss.

It also found that the engine's restore shared a few mutable containers with
the snapshot it read, and the search restores many engines from one snapshot.
In about 0.1% of expansions a sibling line's cost bookkeeping changed. This
affected the fidelity of the planner's own simulation, not the real fight or
the recorded outcomes. The ceiling solver shares the pattern. The engine was
fixed after these runs (`tests/headless/test_restore_ownership.py`), so a rerun
can differ slightly.

## Limits

- **Not a deployable agent.** It starts from the private engine state, which
  [the decisions](../../DECISIONS.md) exclude for production search. A live game
  has no such state; the production belief path would have to supply the worlds.
- **It uses the exact engine as its model of the game,** including each boss's
  full script. That is game knowledge a learned policy has to acquire.
- **Thinking time.** The 8×4 planner took a median of 166 s and at most 449 s
  per fight; 477 of the 589 fights took more than the 120 s that the benchmark's
  nine policies ran under, and none more than the 1,800 s of the search run. The
  1×1 planner took at most 29 s per fight.
- **One planner seed.** The intervals cover campaigns, not planner seeds.
- **Panel reuse.** The beam, the five numbers and the selection rule were
  developed on these same fights in the ceiling experiment. This is a
  development result, not a held-out one.
- **A discarded first run.** The first 1×1 run crashed in 6 of 589 fights: a
  world held a different copy of an equal card than the real hand. Moves were
  then matched by content, and everything was rerun. No result from before the
  fix is used.
- **Engine build.** The search and network outcomes come from earlier builds,
  matched by encounter and public start digest. Deterministic policies had
  identical results across those builds.
- **Conservative sampling.** The whole draw pile is reshuffled, so public
  knowledge of a card's position, after Headbutt for example, is thrown away.
  This can only weaken the planner.
- **Planner restrictions.** No potion discard, no undo, equal cards
  interchangeable. A fixed rule decided 1 decision of the 8×4 planner and 2 of
  the 1×1 planner.
- **Elites and normal fights were not run.**

## Reproduce

```bash
.venv/bin/python runs/combat-public-planner-20261112/checks.py \
  runs/combat-public-planner-20261112/checks.json 24
.venv/bin/python runs/combat-public-planner-20261112/run.py p1w1
.venv/bin/python runs/combat-public-planner-20261112/run.py p8w4
.venv/bin/python runs/combat-public-planner-20261112/analyze.py \
  runs/combat-public-planner-20261112/analysis.json p8w4 p1w1
```

They use the corpus and the per-fight player counts of the
[ceiling experiment](COMBAT_CEILING_2026_11_12.md#reproduce). Analysis output
`analysis.json`, SHA-256 `ecab94b3…`; checks output `checks.json`, SHA-256
`f0308592…`.

Elapsed times: the two runs took 118 minutes of wall time on 16 workers (8, 44
and 66 minutes for the 1×1 run and the two parts of the 8×4 run), or 30.6
worker-hours. The independent review took about 50 minutes in two parts.
Implementation time was not measured. User wait: the session paused once for
about 70 minutes while the 8×4 run continued.

## Follow-up, 2026-11-13: The Kin and the progress measure

Status: **complete; the change did not help.** The user approved it as the
first planner follow-up.

**Question.** The planner counts damage to the Kin's two followers as progress,
although they die with the Priest. Does counting only the enemies that must die
remove its weakness on The Kin?

| Planner 8×4 on the 100 Kin fights | Wins | 95% interval |
| --- | ---: | --- |
| Progress counts every living enemy, as recorded | 49 | 39–59% |
| Progress counts only the enemies that must die | 45 | 36–55% |
| Network with search, for reference | 60 | 50–69% |
| Perfect-information solver, for reference | 76 | 67–84% |

Paired on the same fights the change is worth −4.0 points, with a 95% interval
of −12.0 to +4.0. Six fights were won only with the change and ten only without
it; 84 ended the same way.

**What it means.**
- The change does not close the gap to search. The interval rules out a gain
  above 4 points, and the gap is 11.
- The suspected cause is not confirmed. Why the planner is weak on The Kin is
  open.
- With the change fights ended about half a turn earlier, won or lost: wins on
  turn 6.3 on average against 6.8.

**Method.**
- The engine ends a fight when no living enemy without the `minion` status is
  left. The changed measure leaves minions out of the enemy HP and the enemy
  count. Their Strength still counts as threat. This one variant was fixed
  before any fight was played.
- The variant is derived mechanically from the recorded planner
  (`runs/combat-planner-kin-20261113/required.py`, SHA-256 `d56a34f6…`). In
  twelve line searches on fights without minions it returned exactly the
  recorded planner's result.
- Both arms use the recorded 8×4 setting and the recorded seeds, on the engine
  of the 2026-11-13 working tree (build `9c3e75bd…`) and a corpus rebuilt for it
  with the same 1,728 openings.
- The unchanged arm reproduced the recorded run: the same outcome and the same
  number of decisions in all 100 fights.
- All 200 episodes were replayed through the benchmark's public adapter. None
  failed, was cut off or disagreed with the planner's own count.
- Among the benchmark's encounters only The Kin has minions, so no other
  benchmark fight is affected by the change.

**Limits.**
- 100 fights and one planner seed. A small effect in either direction cannot be
  seen.
- One way of leaving the followers out. Counting them in part was not tried.
- The solver of the ceiling experiment was not rerun with the change.
- No independent review. The change alters how sampled worlds are scored, not
  what the planner can see, and the `minion` status is public.
- A development result on the same panel.

**Reproduce.**

```bash
.venv/bin/python runs/combat-planner-kin-20261113/run.py
.venv/bin/python runs/combat-planner-kin-20261113/analyze.py \
  runs/combat-planner-kin-20261113/analysis.json
```

They use the corpus at `runs/combat-benchmark-20261113/corpus`, built with the
command of the [ceiling record](COMBAT_CEILING_2026_11_12.md#reproduce).
Analysis output `analysis.json`, SHA-256 `a4abc733…`.

Elapsed times: the run took 36 minutes of wall time on 16 workers, or 9.1
worker-hours; the corpus rebuild took 156 s. Implementation and analysis time
was not measured. User wait: none.
