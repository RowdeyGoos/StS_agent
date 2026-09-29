"""Small labelled public-teacher corpus, including potion and selector decisions."""
import json
from pathlib import Path

from game.agent.provenance import implementation
from game.agent.runner import prepare_directories
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run.inventory import add_potion
from .config import TrainingConfig
from .evaluation import BaselineCase, _episode
from .scenarios import SCENARIOS, episode_seed, scenario

SCHEMA = 'sts_imitation_demonstrations_v1'
SCENARIO_SET = 'ironclad_a0_imitation_v1'
SCENARIO_NAMES = tuple(s.encounter for s in SCENARIOS) + ('selector', 'potions')


def factory(name):
    if name not in SCENARIO_NAMES:
        raise ValueError('Unknown imitation scenario')
    if name not in ('selector', 'potions'):
        return scenario(name).make
    def make(seed):
        cards = ('armaments', 'strike', 'strike', 'defend', 'defend', 'defend', 'defend')
        run = RunEngine(seed=seed, card_ids=cards, hp=30 if name == 'potions' else 80,
                        max_hp=80, rng_profile='native', config=RunConfig())
        run.obtain_relic('burning_blood')
        if name == 'potions':
            for potion in ('gamblers_brew', 'blood_potion'):
                add_potion(run.state, potion)
        run.start_combat(encounter_id='overgrowth_nibbit')
        return run
    return make


def collect_demonstrations(*, output_dir, split='train', cases_per_scenario=1, start_index=0,
                           max_decisions=96, time_limit_seconds=30.0, config=None):
    from .checkpoint import publish
    config = TrainingConfig() if config is None else config
    if type(cases_per_scenario) is not int or not 1 <= cases_per_scenario <= 100:
        raise ValueError('Choose 1–100 demonstration cases per scenario')
    episode_seed(split, start_index)
    episode_seed(split, start_index + cases_per_scenario - 1)
    output = Path(output_dir).resolve()
    output, audit = prepare_directories(output, output.with_name(output.name + '-private'))
    path = output/'demonstrations.json'
    if path.exists() or path.with_name(path.name+'.partial').exists():
        raise FileExistsError(path)
    identity = implementation()
    report = {'schema': SCHEMA, 'split': split, 'scenario_set': SCENARIO_SET, 'status': 'complete',
              'teacher': identity.policy, 'training_config': config.to_dict(),
              'requested_episodes': len(SCENARIO_NAMES)*cases_per_scenario, 'episodes': []}
    for name in SCENARIO_NAMES:
        for index in range(start_index, start_index + cases_per_scenario):
            case = BaselineCase(name, split, episode_seed(split, index), 0, max_decisions, time_limit_seconds)
            row = _episode(case, 'heuristic', identity, output, audit, config,
                           engine_factory=factory(name), scenario_set=SCENARIO_SET)
            report['episodes'].append(row)
            if row['status'] not in ('terminated', 'truncated'):
                report['status'] = row['status']
                break
        if report['status'] != 'complete':
            break
    report['unattempted_episodes'] = report['requested_episodes'] - len(report['episodes'])
    publish(path, (json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n').encode())
    return path, report


def corpus_pairs(directory, *, split):
    """Explicit local corpus directory; manifest entries are basename-only pairs."""
    from .rewards import strict_json
    root = Path(directory).resolve()
    manifest = strict_json((root/'demonstrations.json').read_text())
    if (manifest['schema'] != SCHEMA or manifest['status'] != 'complete' or manifest['split'] != split or
            manifest['unattempted_episodes'] != 0):
        raise ValueError('Incomplete or incompatible demonstration corpus')
    pairs = []
    for row in manifest['episodes']:
        if row['status'] not in ('terminated', 'truncated'):
            raise ValueError('Failed episode in demonstration corpus')
        names = (row['trajectory'], row['training'])
        if any(type(n) is not str or Path(n).name != n or (root/n).resolve().parent != root for n in names):
            raise ValueError('Corpus entries must be explicit local basenames')
        pairs.append(tuple(root/n for n in names))
    return pairs
