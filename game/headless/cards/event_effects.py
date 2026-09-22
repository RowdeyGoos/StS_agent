"""Rules needed by event-acquired cards."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToricBlock:
    def apply(self, card, player, target):
        before = player.block
        player.gain_block(card.spec.block_gain, powered=True)
        r = player.rules
        key = f"toric_toughness:{r.power_sequence}"
        r.power_sequence += 1
        r.powers[key] = 2
        r.auxiliaries[key] = player.block - before


def after_block_cleared(player):
    r = player.rules
    for key in tuple(r.powers):
        if key.startswith("toric_toughness:"):
            player.gain_block(r.auxiliaries[key])
            r.powers[key] -= 1
            if not r.powers[key]:
                del r.powers[key]
                del r.auxiliaries[key]
