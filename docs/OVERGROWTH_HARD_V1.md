# Overgrowth Hard V1 Benchmark

`overgrowth_hard_v1` is a deliberately partial benchmark, not a representation
of the complete Overgrowth hard encounter pool. Each reset samples one of these
three encounters uniformly with the environment RNG:

- one Mawler
- two Nibbits
- one Shrinker Beetle followed by one Fuzzy Wurm Crawler

The same encounters are available directly as `mawler`, `nibbits`, and
`shrinker_fuzzy` in `sts-watch` and `sts-oracle`. Training and sweeps accept the
sampled `overgrowth_hard_v1` name.

Mawler has 72 HP and opens with Claw for 4 damage twice. Later moves are sampled
uniformly from Claw, Rip and Tear for 14 damage, and Roar for 3 Vulnerable,
subject to two constraints: it cannot repeat its previous move, and it can use
Roar only once per fight. Its structured intent reports per-hit `attack_damage`
and `attack_count`; incoming-damage projection and execution resolve every hit
separately so block, Strength, Vulnerable, and integer damage rounding remain
correct.

The easy Slimes encounter is also canonicalized alongside this benchmark. It
now always contains one random medium slime, one Leaf Slime (S), and one Twig
Slime (S). The medium remains slot 0 and the small enemies are seed-shuffled
between slots 1 and 2.

## Compatibility

This benchmark extends the observation encoder with Mawler, three move names,
and an intent attack-count feature. It also extends action features with a
Mawler target indicator. Existing neural checkpoints can still be deserialized
using their saved model dimensions, but they cannot consume observations or
action features from the expanded encoder. Existing tabular state keys likewise
do not transfer to the expanded representation. Retrain agents before comparing
them on this benchmark, and treat pre-correction Slimes results as a different
environment version.

Exact oracle search remains exponential. Use explicit node or time limits for
the hard-v1 encounters, especially the two-enemy fights.

## Sources

- [Overgrowth encounter table](https://slaythespire.wiki.gg/wiki/Slay_the_Spire_2%3AOvergrowth),
  accessed 2026-08-26
- [Mawler](https://slaythespire.wiki.gg/wiki/Slay_the_Spire_2%3AMawler),
  accessed 2026-08-26
