"""Authored public inventories for split-bound search collection and evaluation.

These declarations describe fresh templates and explicit counters, not restored
campaign states. Only the evaluator receives a gameplay seed. Simulation rules
and combat setup continue to be owned by the ordinary headless engine.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from game.agent.contracts.planning import CombatStart, from_dict, to_dict
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.run.construction import declared_combat
from .evaluation import BaselineCase
from .rewards import strict_json

SCHEMA = 'sts_declared_search_benchmark_v1'


def _label(value):
    if type(value) is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,95}', value) is None:
        raise ValueError('Benchmark labels require lowercase identifiers')
    return value


@dataclass(frozen=True, slots=True)
class DeclaredCase(BaselineCase):
    scenario_id: str


@dataclass(frozen=True, slots=True)
class DeclaredScenario:
    name: str
    deck_profile: str
    role: str
    start: CombatStart

    def make(self, seed):
        s = self.start
        return declared_combat(deck=[(c.definition_id, c.upgrade_level) for c in s.deck],
            relics=[(r.definition_id, r.counter) for r in s.relics], potions=s.potions,
            hp=s.hp, max_hp=s.max_hp, gold=s.gold, encounter_id=s.encounter_id, seed=seed)

    def to_dict(self):
        return dict(id=self.name, deck_profile=self.deck_profile, role=self.role, start=to_dict(self.start))


@dataclass(frozen=True, slots=True)
class SearchBenchmark:
    name: str
    scenarios: tuple[DeclaredScenario, ...]

    @classmethod
    def from_dict(cls, value):
        if (type(value) is not dict or set(value) != {'schema', 'name', 'scenarios'} or
                value['schema'] != SCHEMA or type(value['scenarios']) is not list or
                not 1 <= len(value['scenarios']) <= 64):
            raise ValueError('Invalid declared search benchmark')
        name = _label(value['name'])
        scenarios = []
        for row in value['scenarios']:
            if (type(row) is not dict or set(row) != {'id', 'deck_profile', 'role', 'start'} or
                    row['role'] not in ('control', 'challenge')):
                raise ValueError('Invalid declared benchmark scenario')
            start = from_dict(row['start'])
            if start.card_catalog != DEFAULT_CARDS.snapshot_fingerprint():
                raise ValueError('Benchmark card catalog mismatch')
            scenario = DeclaredScenario(_label(row['id']), _label(row['deck_profile']), row['role'], start)
            # Validate content through the engine, before any experiment artifacts.
            # This disposable seed is unrelated to evaluated or simulated worlds.
            scenario.make(0)
            scenarios.append(scenario)
        if len({s.name for s in scenarios}) != len(scenarios):
            raise ValueError('Duplicate benchmark scenario')
        return cls(name, tuple(scenarios))

    @classmethod
    def load(cls, path):
        return cls.from_dict(strict_json(Path(path).read_text()))

    def to_dict(self):
        return dict(schema=SCHEMA, name=self.name, scenarios=[s.to_dict() for s in self.scenarios])

    @property
    def identity(self):
        data = json.dumps(self.to_dict(), sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        return SCHEMA + ':' + hashlib.sha256(data).hexdigest()
