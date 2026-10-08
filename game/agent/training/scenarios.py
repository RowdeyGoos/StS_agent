"""Controlled ordinary-inventory starts, not campaign-derived combat states."""
from dataclasses import dataclass

from game.headless.characters import definition
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine

SCENARIO_SET = 'ironclad_a0_overgrowth_v1'
SEED_SCHEDULE = 'interleaved_splits_v1'


@dataclass(frozen=True, slots=True)
class Scenario:
    encounter: str
    difficulty: str

    def planning_start(self):
        """Public constants of this controlled fresh-inventory scenario only.

        Never derive this declaration from a restored corpus or campaign state.
        The ordinary producer still verifies the sampled opening against it.
        """
        from game.agent.contracts.planning import CombatStart, StartingCard, StartingRelic
        from game.headless.cards.catalog import DEFAULT_CARDS
        from game.headless.run.construction import declared_combat_region
        declared_combat_region(self.encounter)
        start = definition('ironclad')
        return CombatStart('sts_declared_combat_start_v1', 'declared_fresh_inventory',
            DEFAULT_CARDS.snapshot_fingerprint(), 'ironclad', 0, self.encounter,
            start.max_hp, start.max_hp, 99, tuple(StartingCard(c, 0) for c in start.deck),
            (StartingRelic(start.relic, 0),), (None, None, None))

    def make(self, seed):
        start = definition('ironclad')
        run = RunEngine(seed=seed, card_ids=start.deck, max_hp=start.max_hp,
                        gold=99, config=RunConfig(character='ironclad', ascension=0,
                                                 act='underdocks' if self.encounter.startswith('underdocks_') else 'overgrowth'),
                        rng_profile='native')
        run.obtain_relic(start.relic)
        run.start_combat(encounter_id=self.encounter)
        return run


SCENARIOS = (
    Scenario('overgrowth_nibbit', 'weak'),
    Scenario('overgrowth_fuzzy', 'weak'),
    Scenario('overgrowth_slimes', 'weak'),
    Scenario('overgrowth_mawler', 'normal'),
    Scenario('overgrowth_nibbits', 'normal'),
    Scenario('overgrowth_cubex', 'normal'),
)


def scenario(name):
    for item in SCENARIOS:
        if item.encounter == name:
            return item
    raise ValueError('Unknown combat scenario')


def episode_seed(split, index):
    """Disjoint external Gym seed schedules; evaluator-only replay metadata.

    'validation' is the development/model-selection split, matching recordings.
    Gym derives a fresh game seed separately from policy/action-space randomness.
    """
    splits = ('train', 'validation', 'test')
    if split not in splits or type(index) is not int or not 0 <= index < 2**60:
        raise ValueError('Expected a known split and a nonnegative bounded seed index')
    return 3 * index + splits.index(split)
