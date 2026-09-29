"""Declared combat starts built through game-owned inventory and command APIs."""
from dataclasses import asdict, dataclass

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.full_policy import choose_action
from game.agent.headless.adapter import HeadlessAdapter
from game.headless.characters import definition
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_potion

SOURCE = 'ironclad_a0_curriculum_v1'
STRENGTH = ('inflame', 'pommel_strike', 'pommel_strike', 'shrug_it_off',
            'shrug_it_off', 'whirlwind', 'strike', 'defend')
CHOICE = ('armaments', 'strike', 'strike', 'defend', 'bloodletting')


@dataclass(frozen=True, slots=True)
class Start:
    name: str
    stage: int
    encounter: str
    deck: str = 'starter'
    hp: int = 80
    upgrades: bool = False
    relics: tuple[str, ...] = ('burning_blood',)
    potions: tuple[str, ...] = ()
    prefix: str | None = None
    campaign_combat: int = 0
    test_only: bool = False

    def make(self, seed):
        if self.campaign_combat:
            return campaign_start(seed, self.campaign_combat)
        cards = {'starter':definition('ironclad').deck, 'strength':STRENGTH, 'choice':CHOICE}[self.deck]
        run = RunEngine(seed=seed, card_ids=cards, hp=self.hp, max_hp=80,
                        gold=99, config=RunConfig(), rng_profile='native')
        for name in self.relics:
            run.obtain_relic(name)
        if self.upgrades:
            for card in tuple(run.state.deck):
                run.upgrade_card(card.instance_id)
        for name in self.potions:
            add_potion(run.state, name)
        run.start_combat(encounter_id=self.encounter)
        if self.prefix:
            adapter = HeadlessAdapter(run, decision_profile=f.PROFILE)
            frame = adapter.observe()
            nodes = {n.ref:n for root in (frame.decision.run, frame.decision.context)
                     for n in f.walk(root) if n.ref}
            kind = 'play_card' if self.prefix=='armaments' else 'use_potion'
            action = next(a for a in frame.decision.candidates if a.kind==kind and
                          nodes[a.subject].definition_id==self.prefix)
            result = adapter.step(frame.binding, action.ref)
            if result.status!='reconciled':
                raise RuntimeError('Curriculum prefix did not reconcile')
            ready = adapter.observe()
            if isinstance(ready, c.RunOutcome) or not any(
                    n.kind=='selection' for n in f.walk(ready.decision.context)):
                raise RuntimeError('Curriculum prefix did not open its selector')
        return run


STARTS = (
    Start('starter_nibbit', 0, 'overgrowth_nibbit'),
    Start('starter_fuzzy', 0, 'overgrowth_fuzzy'),
    Start('starter_mawler', 0, 'overgrowth_mawler'),
    Start('starter_nibbits', 0, 'overgrowth_nibbits'),
    Start('low_hp_cost', 1, 'overgrowth_nibbit', 'choice', hp=24),
    Start('upgraded_cubex', 1, 'overgrowth_cubex', 'strength', upgrades=True, relics=('burning_blood','vajra')),
    Start('armaments_choice', 2, 'overgrowth_nibbit', 'choice', prefix='armaments'),
    Start('colorless_choice', 2, 'overgrowth_nibbit', potions=('colorless_potion',), prefix='colorless_potion'),
    Start('gamblers_choice', 2, 'overgrowth_mawler', potions=('gamblers_brew',), prefix='gamblers_brew'),
    Start('low_hp_potions', 2, 'overgrowth_nibbits', hp=24, potions=('blood_potion','fire_potion')),
    Start('elite_strength', 3, 'overgrowth_byrdonis', 'strength', upgrades=True, relics=('burning_blood','vajra','anchor')),
    Start('boss_strength', 3, 'overgrowth_ceremonial_beast', 'strength', upgrades=True, relics=('burning_blood','vajra','anchor')),
    Start('campaign_first', 4, 'campaign', campaign_combat=1),
    Start('campaign_second', 4, 'campaign', campaign_combat=2),
    Start('transfer_choice_fuzzy', 2, 'overgrowth_fuzzy', 'choice', hp=36, test_only=True),
    Start('transfer_strength_kin', 3, 'overgrowth_the_kin', 'strength', upgrades=True,
          relics=('burning_blood','vajra','anchor'), test_only=True),
)


def start(name):
    for item in STARTS:
        if item.name==name:
            return item
    raise ValueError('Unknown curriculum start')


def training_names(stage):
    if type(stage) is not int or not 0 <= stage <= 4:
        raise ValueError('Choose a curriculum stage from 0 to 4')
    return tuple(s.name for s in STARTS if s.stage<=stage and not s.test_only)


def manifest():
    return [asdict(s) for s in STARTS]


def campaign_start(seed, ordinal):
    """Stop a genuine ordinary-inventory campaign at its first/second fight.

    The teacher sees public decisions only. Each requested campaign is attempted
    once; death or an unreachable prefix is a failed source, never a seed retry.
    Reattachment deliberately starts a new public history, as for other starts.
    """
    if ordinal not in (1, 2):
        raise ValueError('Only the two declared early campaign combats are supported')
    run = RunEngine.campaign(seed=seed, character='ironclad', first_act='overgrowth', rng_profile='native')
    adapter = HeadlessAdapter(run, decision_profile=f.PROFILE)
    seen, last = 0, None
    for _ in range(128):
        frame = adapter.observe()
        if isinstance(frame, c.RunOutcome):
            raise RuntimeError('Campaign ended before its declared combat start')
        if run.combat is not None and run.combat is not last:
            seen, last = seen+1, run.combat
            if seen==ordinal:
                return run
        action = choose_action(frame.decision)
        result = adapter.step(frame.binding, action.ref)
        if result.status!='reconciled':
            raise RuntimeError('Campaign prefix did not reconcile')
    raise RuntimeError('Campaign prefix exhausted its decision budget')


def environment(**settings):
    from .env import CombatTrainingEnv
    item = start(settings['encounter'])
    if item.test_only:
        raise ValueError('Held-out combinations cannot enter training')
    return CombatTrainingEnv(engine_factory=item.make, **settings)
