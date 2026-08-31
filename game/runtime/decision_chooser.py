"""Public-only chooser protocol for ``headless_v0`` episodes.

This module intentionally accepts a :class:`PolicyView`, rather than a backend
or a full ``DecisionState``.  It keeps control bindings and private backend
state outside the policy boundary.
"""

from __future__ import annotations

from typing import Protocol

from game.contracts.headless_v0 import PolicyView


class DecisionChooser(Protocol):
    """Choose one currently advertised candidate ID from a public policy view."""

    def __call__(self, decision: PolicyView) -> str:
        """Return the ID of a candidate advertised by ``decision``."""
