"""Allowlisted combat facts for controllers; independent of wire observations."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CombatSummary:
    """One owned fight, including its completed post-hook HUD values.

    ``combat_ref`` is attachment-local, not an engine identity or scenario ID.
    Net HP change is not a measurement of cumulative damage taken.
    """
    combat_ref: str
    outcome: str
    hp: int
    max_hp: int
    turn: int
    schema: str = 'sts_combat_summary_v1'

    @property
    def completed(self):
        return self.outcome in ('victory', 'defeat')


def summarize(combat, epoch, *, completed_state=None):
    if completed_state is None:
        owner, outcome = combat.player, 'ongoing'
    else:
        if not combat.done or combat.winner not in ('player', 'enemy'):
            raise ValueError('Combat was detached without an authoritative result')
        owner = completed_state
        outcome = 'victory' if combat.winner == 'player' else 'defeat'
    return CombatSummary(f'combat:{epoch}', outcome, owner.hp, owner.max_hp, combat.turn)
