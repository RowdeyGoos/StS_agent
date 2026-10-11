# Campaign Search and witnessed combat validation — October 9, 2026

## Result and scope

The headless campaign controller can now run `campaign_belief_v1` through
Ironclad A0 Act 1. New combat corpora can carry public entry/reveal receipts.
A validation diagnostic builder records a frozen portfolio's attempts and
independently replays winning public traces before marking a fight witnessed.
Unresolved fights remain in the natural benchmark and every denominator.

The bounded acceptance run produced **56 witnessed wins and three unresolved
cases among 59 validation fights**. Search and the raw 150k student each won
55/59, with one win exchanged in each direction. In a separate four-pair campaign
check, Search cleared Act 1 once and the raw student never cleared it. These are
development/acceptance results, not evidence sufficient to promote a controller:
the campaign paired 95% interval is **[-1, 1]**.

No weights were trained or promoted. The existing Vantom artifacts and their
test partition were not rebound or evaluated. Native bridge execution is not
implemented by this change. Campaign-model search collection rejects explicitly;
existing Vantom collection/reanalysis retain their previous semantics.

## Implementation and boundaries

- An engine-owned, ephemeral observer exposes the moment after room-entry
  effects and before combat setup. The adapter projects public inventory there
  and records public setup/action reveals. Recording must not change game state
  or consume its RNG.
- Search translates this public receipt into declared inventory and invokes the
  existing rules to construct hypothetical worlds. Public enemy types identify
  an ordinary encounter; the actual private map assignment is never an input.
  Entry context excludes event-owned fights even if they share an enemy roster.
- Conditional draws, generation and opening HP reuse existing likelihood-aware
  proposals. Complete public observations must reconcile. Permanent growth,
  enchantments, displayed counters and known lifetime-card history survive.
- Each new fight resets its belief while retaining campaign work statistics.
  Terminal conditioning uses the public settled combat result, including cleanup.
  Historical references to consumed items remain reserved during attachment;
  simulated generation cannot reuse them and change a past action's meaning.
- Event fights, Toy Box/Silver Crucible history, stored Pael's Tooth cards and
  missing history have explicit fallbacks. Budget exhaustion is distinct from
  these unsupported capabilities and from game defeat/cutoff. The future bridge
  needs equivalent public entry and reveal receipts, not a private snapshot.

The model remains an approximate finite-particle belief. This change does not
remove the earlier limitation that simulated tree edges omit intermediate reveal
journals. It also does not establish every content/history combination merely
because all 42 ordinary Act 1 opening fixtures pass.

## Frozen source population

Artifacts are under `runs/campaign-search-validation-20261009/`; operational
commands and interpretation are in the [training guide](../AGENT_TRAINING.md#campaign-search-and-witnessed-validation).

The corpus used the frozen general campaign collector at
`runs/act1-increased-500k-8workers-20260930/chunk-15/final.sts-model`, with
`--record-planning --train-campaigns 1 --validation-campaigns 4 --test-campaigns 1
--start-index 43000 --max-decisions 768 --time-limit 120 --route-policy mixed_elites
--capture-turns 2`. Counts are per region. These are genuine generated starts,
without assisted HP/decks, under the existing corpus collector's start profile;
the separate campaign evaluator uses its normal all-unlocked Ancient start.

| Validation population | Count/range |
| --- | ---: |
| Source campaigns | 8 |
| Whole-fight openings | 59 |
| Overgrowth / Underdocks | 30 / 29 |
| Normal / elite / boss fights | 48 / 8 / 3 |
| Distinct encounters | 31 |
| Opening public receipts | 59 |
| HP at capture | 13–80 |
| Deck size | 10–21 |
| Opening/continuation starts combined | 117 |

The corpus separately contains 18 training fights and 14 held-out fights.
Qualification and subsequent comparison use validation openings only. The
builder assigns whole campaigns to splits before playing them. The source
collector determines which fights/decks are reached; this is not an unbiased
sample of every possible combat. Its coverage manifest records missing content,
including Vantom in this small validation population. The existing Vantom
benchmark remains a separate diagnostic population.

## Qualification portfolio

Before attempts, `qualification/combat-plan.json` froze all 59 cases, six policies,
checkpoints and budgets. Each fight received 256 decisions and 300 seconds. Search
used 16 simulations, depth 16, four policy-rollout leaf steps, two particles,
256 opening proposals, 512 recovery proposals, two seconds for belief work and
five seconds per search action. Eight workers ran independent fights.

| Policy | Wins / natural population | Defeats | Cutoffs/failures |
| --- | ---: | ---: | ---: |
| Public heuristic | 52 / 59 | 7 | 0 |
| Random legal | 36 / 59 | 23 | 0 |
| General campaign actor | 52 / 59 | 7 | 0 |
| PPO Vantom specialist, 250k | 54 / 59 | 5 | 0 |
| Search student, 150k, network only | 55 / 59 | 4 | 0 |
| Same student with Search | 55 / 59 | 4 | 0 |

The general checkpoint supplies only actor choices in this comparison; its
campaign critic never supplies combat search values. Search uses the student's
undiscounted `victory + 0.1 × winning HP fraction` critic and its original action
restriction.

The first winning attempt in the predeclared attempt order becomes the witness.
The verifier loads the public trace and terminal sidecar, checks policy identity,
split and exact start digest, then replays only advertised actions through the
engine to confirm the completed victory. All 354 attempts remain recorded.

`qualification/combat-diagnostics.json` contains:

- **56 witnessed wins**, including four cases the heuristic lost;
- **three unresolved cases**: Bygone Effigy, Phantasmal Gardeners and The Kin;
- every case's source campaign, attempt outcomes, policy identity, and witness
  trace/sidecar hashes where available.

“Unresolved” means this portfolio did not record a win under this budget. It is
not proof of impossibility. A winning witness applies to that frozen stochastic
realization, not all plausible hidden draws. Qualification-policy performance
on the subset it helped select is not an independent generalization test.

A second invocation of `sts-agent-evaluate --combat-corpus ...
--combat-diagnostics ... --candidate student=...` loaded the frozen labels and
retained all 59 natural cases. It reproduced 55/59 student wins and additionally
reported **55/56 on witnessed cases, 0/3 on unresolved cases**. Its heuristic
and random results also reproduced. This checks consumption of the frozen set,
not a new independent efficacy experiment.

The existing trace viewer also successfully exported the two Search episodes
where student/Search win outcomes disagreed to `decision-examples/`, including
recorded search probabilities and values. No simulator/private input is used by
that viewer.

## Campaign and coverage acceptance

`campaigns/search.json` uses four paired new campaign roots (`--start-index
44000`), alternating regions, with the same Search settings above, a 768-decision
and 600-second campaign ceiling, and four workers. Noncombat choices use the same
heuristic in both arms.

| Measure | Student | Student + Search |
| --- | ---: | ---: |
| Act 1 clears | 0 / 4 | 1 / 4 |
| Actual campaign defeats | 4 | 3 |
| Episode cutoffs / execution failures | 0 / 0 | 0 / 0 |
| Completed combats | 25 | 36 |
| Combat victories | 21 | 33 |

The clear occurred in Overgrowth. Extra reached fights are consequences of
campaign survival, so the two arms' combat totals are not a matched combat sample.
The paired Act 1 difference is +0.25 with source-group Hoeffding 95% interval
[-1, 1]; **inconclusive, no promotion**.

| Search work | Qualification fights | Campaigns |
| --- | ---: | ---: |
| Decisions / forced choices | 827 / 169 | 629 / 130 |
| Successfully searched choices | 601 | 491 |
| Coverage excluding forced choices | 91.34% | 98.40% |
| Belief-budget fallbacks | 57 | 8 |
| Simulations completed | 9,616 | 7,856 |
| Mean recorded search/update time | 0.969 s | 0.963 s |
| Largest episode p95 | 4.112 s | 4.036 s |

No unsupported-content fallback occurred in these particular populations. Budget
fallbacks remain a measurable gap; supporting a content family does not guarantee
that a bounded belief update succeeds. All searched choices completed the requested
simulation budget. Timing includes conditioning but excludes ordinary environment
dispatch/recording. These runs overlapped each other and validation on the local
Mac; they are operational timing observations, not isolated throughput benchmarks.

## Validation and provenance

Focused checks cover all 42 ordinary Act 1 opening rosters, multi-fight passive
recording in both regions, engine/public successor equality, room-entry effects
exactly once, permanent modifiers, hidden RNG/draw independence, consumed-item
reference reuse, event-entry fallback, missing-history fallback, aggregate work,
opening/continuation corpus attachment, parallel portfolio execution, winning
replay, unmodified denominators, cutoffs, held-out exclusion and tamper rejection.

Final validation used the existing `.venv` environment:

- `python -m compileall -q game tests` and `git diff --check` passed.
- `PYTHONPATH=. python -m pytest -q tests` completed in **1,654.92 s**:
  **9,104 passed, one skipped, one sandbox permission failure**. The failure was
  the existing analysis HTTP test binding a temporary `127.0.0.1` port. That exact
  test passed separately with the required execution permission (**one passed in
  0.59 s**); there were no other failures.
- The lifetime-card cleanup regression, added after the broad suite collected
  its cases, passed separately (**one passed in 0.23 s**). It checks both explicit
  fallback without history and native expiration/terminal reconciliation with
  recorded history. Production sources were unchanged between these checks.

The explicit `tests/` scope excludes copied historical test trees under `runs/`.
An initial unscoped invocation discovered those obsolete experiment copies and
was stopped during collection; its collection errors are not current-suite
results. No pytest configuration or historical experiment source was changed.

One independent source-level semantic review cleared the final public-information,
RNG and diagnostic persistence boundaries after three findings were fixed:
historical reference reuse, unsupported campaign collection admission and
contradictory diagnostic summary/provenance fields. The reviewer did not claim
to run gameplay checks. Author validation owns the actual executions above.

Measured artifact-operation times: corpus collection **48.13 s**, portfolio
evaluation **236.31 s**, paired campaign evaluation **219.64 s**, subsequent
frozen-label comparison **10.65 s**. The first number excludes model load; portfolio
evaluation timing excludes subsequent witness replay. Implementation/review wall
time was not separately measured.

Implementation identity (dirty checkout based on `d74937f9`):

```text
build  cd4268326e884147bd6e5bc19d06066ae9c6040689f5444a56d5ec18a14057bd
rules  405aff937c0abe2e3fae24e84c54e5528069cefdcb954cc2284faadd2738cc33
```

Checkpoint SHA-256:

```text
general     fce362d2e0cc8f337cb06642c198ddc53c8a5e2b312f2e3596feac488a30352f
specialist  4da8789591fc9379522b3b30745bb6b6615ee53bb4bfc21215affecf28dfae6a
student     7805954e02238a6928a3c15ce2b6d65e492f1743a3a1bb87054dc8ffa5d9c9b0
```

Artifact SHA-256 (paths relative to the run directory):

```text
corpus/corpus.json
62ec4ab7dbe7ea97e7c013f08e48ecb2ad58d72e1c50c4b10f7a4445cd68e092
qualification/combat-plan.json
fd997f5dc4b43281680bf24c2a9da99e3024cd912a34ffbfb02e448209d7bbf8
qualification/combat-benchmark.json
916040e1e5a49fae72f1687f9d0d1b7b4a8c38b75fef635f00953600fd4c3875
qualification/combat-diagnostics.json
e19cf876a6aa6038655b8b06a430535814353da785ef35033cb867e2b3dc019b
campaigns/search.json
e7fb450cc27387fdc54dde5b486545ba5b8859f40dc314055cf7695b56be7edc
```

Original reports, traces and source snapshots stay under the run directory;
private trees retain owner-only permissions. These hashes identify the recorded
artifacts and are not substitutes for the replay/test evidence. Later source
changes must create a new compatible corpus, never repin these records.
