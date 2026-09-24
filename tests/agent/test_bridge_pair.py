"""The paired bridge fixture must remain an actual headless producer result."""
import importlib.util
from pathlib import Path

from game.agent.headless import HeadlessAdapter
from game.agent.policy import choose_action
from game.headless.monsters.overgrowth import SimpleEnemy
from tests.agent.test_headless_adapter import fury_game


def test_authored_bridge_pair_matches_headless_decisions_and_deterministic_transitions():
    path = Path(__file__).parents[2] / 'bridge/Sts2AgentBridge/apps/bridge/client_tests/agent_pair.py'
    spec = importlib.util.spec_from_file_location('agent_pair', path)
    pair = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pair)
    run = fury_game()
    run.state.current_node_id = 'first'
    run.state.visited_nodes = ['first']
    run.state.gold = 99
    run.combat.enemies[:] = [SimpleEnemy()]
    adapter = HeadlessAdapter(run)
    rows = []
    for index in range(5):
        frame = adapter.observe()
        rows.append(pair.c.to_dict(frame.decision))
        if index < 4:
            assert adapter.step(frame.binding, choose_action(frame.decision).ref).status == 'reconciled'
    pair.compare(rows)
