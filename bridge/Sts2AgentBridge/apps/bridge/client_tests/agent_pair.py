"""Authored matching public setups; no native RNG or live parity claim."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).absolute().parents[1] / 'client'))
from agent_host import c, choose_action

FIXTURE = Path(__file__).with_name('agent_pair.json')


def normalize(decision):
    """Normalize refs and the candidate set; retain meaningful visible ordering."""
    refs, counts = {}, {}
    def walk(value):
        if type(value) is dict:
            return {key: walk(item) for key, item in value.items()}
        if type(value) is list:
            return [walk(item) for item in value]
        if type(value) is str and ':' in value:
            kind, number = value.split(':', 1)
            if kind in ('card', 'enemy', 'power', 'relic', 'potion', 'orb', 'reward', 'node', 'action') and number.isdigit():
                if value not in refs:
                    refs[value] = f'{kind}:{counts.get(kind, 0)}'
                    counts[kind] = counts.get(kind, 0) + 1
                return refs[value]
        return value
    result = walk(c.to_dict(decision))
    result['candidates'].sort(key=lambda a: (a['kind'], a['subject'] or '', a['target'] or ''))
    for index, candidate in enumerate(result['candidates']):
        candidate['ref'] = f'action:{index}'
    return result


def compare(rows):
    expected = json.loads(FIXTURE.read_text())
    assert len(rows) == len(expected['decisions']) == 5
    for index, (actual, wanted) in enumerate(zip(rows, expected['decisions'])):
        actual = c.from_dict(actual)
        c.require_ready(actual)
        assert normalize(actual) == wanted, f'Public scenario {index} differs'
        assert choose_action(actual).kind == expected['actions'][index]


if __name__ == '__main__':
    result = subprocess.run([sys.argv[1], sys.argv[2], '--emit'], check=True, capture_output=True, text=True, timeout=15)
    compare([json.loads(line) for line in result.stdout.splitlines()])
    print(json.dumps({'status': 'passed', 'paired_decisions': 5, 'target_game_executed': False}))
