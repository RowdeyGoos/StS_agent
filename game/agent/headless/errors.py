"""Adapter failures are operational results, never game outcomes."""
from game.agent.contracts import ExecutionReport


class UnsupportedProfile(ValueError):
    """This producer cannot completely represent the current decision."""

    def __init__(self, capability):
        self.capability = capability
        self.report = ExecutionReport('sts_execution_report_v1', 'unsupported', 'none',
                                      'unsupported_capability')
        super().__init__('Unsupported public projection: ' + capability)


class AdapterFault(RuntimeError):
    """Execution failed; the adapter is stopped until explicitly attached again.

    Mutation is uncertain. Do not retry the command or turn this into a defeat.
    The v1 transport report has no backend-exception reason, so this stays a
    local exception rather than mislabelling it as a transport failure.
    """
