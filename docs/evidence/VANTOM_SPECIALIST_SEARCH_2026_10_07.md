# Vantom specialist versus combat search — 2026-10-07

**Search did not improve the observed win rate: both controllers won 26/42 fights (61.9%).** It rescued two specialist defeats and lost two specialist wins. The paired 95% interval is -9.5 to +9.5 percentage points, so this comparison does not establish a benefit.

Evaluation only: the same frozen 250k-decision specialist on 42 paired, previously used validation openings. No retraining and no held-out test games.

| Controller | Wins | Win rate | Actual defeats | Cutoffs | Mean completed return |
|---|---:|---:|---:|---:|---:|
| Original specialist | 26/42 | 61.9% | 16 | 0 | 0.6353 |
| Specialist with search input view | 26/42 | 61.9% | 16 | 0 | 0.6353 |
| Same specialist + search | 26/42 | 61.9% | 16 | 0 | 0.6373 |

## Paired results

Search versus the original specialist: **+0.0 percentage points**, paired 95% bootstrap interval **[-9.5, +9.5] percentage points**. Search gained 2 wins and lost 2 wins on matched starts.

Search versus the same-input specialist (primary comparison): **+0.0 percentage points**, paired 95% bootstrap interval **[-9.5, +9.5] percentage points**. Search gained 2 wins and lost 2 wins on matched starts.

Mean remaining HP on victories was 22.04 for the specialist and 24.69 with search. Both consumed 17 potions across the panel. Across all 42 paired completed fights, the mean end-HP change was +1.64, with a 95% interval of [-1.38, +4.79]; a health benefit is not established either.

The input-view control separates planning from detaching action history and anonymizing card references. The checkpoint was originally trained on the raw input view; this control matters for interpreting its use inside search.

## Actual search coverage and cost

- Search ran on 606/1224 decisions (49.5%), or 62.2% excluding forced actions.
- 42/42 fights used search. It selected a lower-prior action on 103/606 searched decisions.
- 14544 simulations completed; 606/606 searched decisions reached the 24-simulation budget.
- Searched actions: median 2.493s, p95 2.952s. This includes public conditioning and was measured with four simultaneous fights.
- Search-arm wall time: 6.5 minutes.

There were no search-budget cutoffs, game cutoffs or execution failures. The maximum recorded action time was 4.341s. Fallback counts below count affected decisions after coverage ended, not independent triggering events.

Fallback counts: `forced_action`: 249, `opening_scope:card:havoc`: 44, `opening_scope:card:hellraiser`: 12, `opening_scope:card:infernal_blade`: 14, `opening_scope:card:juggling`: 45, `opening_scope:card:pillage`: 59, `opening_scope:end_turn_draw_trigger`: 39, `opening_scope:intrinsic_retention`: 29, `opening_scope:potion:bottled_potential`: 11, `opening_scope:potion:colorless_potion`: 21, `opening_scope:potion:fysh_oil`: 24, `opening_scope:potion:liquid_memories`: 26, `opening_scope:potion:radiant_tincture`: 27, `opening_scope:potion:stable_serum`: 18.

## Scope and reproducibility

The stock direct-belief model rejects all 42 inventories. This comparison uses a separately identified experimental adapter admitted only for these verified fresh Vantom openings. It constructs hypothetical worlds from the public opening and independent analysis seeds, runs ordinary engine startup and combat mechanics, and permanently falls back to the specialist after unsupported real transitions. It never copies actual draw order, future RNG or private card identities into search. This is partial search coverage, not full training-corpus or bridge support.

Configuration: Gumbel search, 24 simulations, depth limit 16, four policy rollout actions per leaf, two belief particles, five-second action ceiling, no exploration noise. Objective: victory plus 0.1 times settled winning HP fraction; defeat zero. Episodes are separately bounded at 512 actions and 30 minutes.

Checkpoint SHA-256: `4da8789591fc9379522b3b30745bb6b6615ee53bb4bfc21215affecf28dfae6a`. Historical raw specialist: 26/42 wins. Current-versus-historical outcome/length/HP/return differences: 0 cases.

Action-sequence differences: 0 cases versus the historical specialist, and 0 cases between the raw and search-input controls.

Each opening is a distinct source group. Confidence intervals resample paired groups 50,000 times with a fixed seed. These are development results on a validation-selected specialist, not a held-out promotion test. No policy or search setting was fitted to these comparison outcomes.

Preflight verified snapshot hashes and exact historical public openings under the current engine. Focused checks cover hidden draw/RNG/identity invariance, no mutation, startup healing and counters, known top placements, selectors, terminal cleanup, unsupported-transition fallback and budget exhaustion. One independent semantic review approved this bounded experiment.

An earlier partial attempt was invalidated after an audit found that hypothetical potion generation used a restricted default pool. Its frozen inputs and partial outputs remain separate. This report uses only the complete rerun with the canonical Ironclad pool. The corrected checks compare every serialized combat-rules field for all 42 openings, normalizing only private relic and potion identities. The search settings were unchanged.

Measured focused validation: 10.18s. The two control evaluations took 12.95s and 13.04s. Implementation and review were not separately timed. No release packaging or user setup was required.

- [Exact production sources and environment](../../runs/vantom-specialist-search-20261007/source-archive.json)
- [Machine-readable comparison](vantom_specialist_search_2026_10_07.json)
- [Frozen protocol and source bindings](../../runs/vantom-specialist-search-20261007/protocol.json)
- [Focused checks](../../runs/vantom-specialist-search-20261007/checks.json)
- [Independent semantic review](../../runs/vantom-specialist-search-20261007/review.json)

The complete local bundle is `runs/vantom-specialist-search-20261007/`, including public trajectories, private replay audits, search diagnostics, the reviewed experimental adapter and frozen inputs. The invalidated attempt is retained in its `invalidated-attempt/` subdirectory. The prototype is experiment-local; no production search or training interface was changed.
