"""Relic labels at a settled public decision, not serialized hook memory.

These mappings follow the pinned native relics' ShowCounter, DisplayAmount and
Status. A hidden counter remains absent even when the engine needs its value.
"""

# Persistent counters whose displayed value wraps at a public threshold.
WRAPPED = {'galactic_dust': 10, 'pollinous_core': 4, 'fake_happy_flower': 5,
           'iron_club': 4, 'paels_wing': 2, 'happy_flower': 3, 'nunchaku': 10,
           'pen_nib': 10, 'pendulum': 3, 'tuning_fork': 10,
           'book_of_five_rings': 5, 'lasting_candy': 2, 'fishing_rod': 3}
ACTIVE_LAST = frozenset(('galactic_dust', 'nunchaku', 'pen_nib', 'tuning_fork', 'iron_club'))
ACTIVE_COMBAT = frozenset(('pollinous_core', 'fake_happy_flower', 'happy_flower', 'pendulum'))
ATTACK_THREE = frozenset(('kunai', 'shuriken', 'ornamental_fan', 'kusarigama'))


def labels(relic, player=None, *, empty_belt=False, before_boss=False, rest_status='normal'):
    name, count = relic.definition_id, relic.counter
    memory = player.rules.relic_data.get(relic.instance_id, {}) if player else {}
    shown, amount, status = False, None, 'normal'
    extra = {}
    if name == 'pantograph' and before_boss:
        status = 'active'
    elif name == 'regal_pillow':
        status = rest_status
    if name in WRAPPED:
        shown, amount = True, count % WRAPPED[name]
        if amount == WRAPPED[name] - 1 and (name in ACTIVE_LAST or player and name in ACTIVE_COMBAT):
            status = 'active'
    elif name in ('girya', 'joss_paper', 'sword_of_stone', 'pumpkin_candle'):
        shown, amount = True, count
        if name == 'joss_paper' and count == 4:
            status = 'active'
        elif name == 'pumpkin_candle' and count <= 0:
            status = 'disabled'
    elif name in ('maw_bank', 'lizard_tail', 'lava_rock', 'silken_tress'):
        status = 'disabled' if count else 'normal'
    elif name in ('venerable_tea_set', 'fake_venerable_tea_set'):
        status = 'active' if count else 'normal'
    elif name == 'wongos_mystery_ticket':
        shown, amount = count < 5, max(0, 5 - count)
        status = 'disabled' if count >= 6 else 'normal'
    elif name == 'toy_box':
        shown, amount = count < 12, count % 3
        status = 'disabled' if count >= 12 else 'normal'
    elif name == 'silver_crucible':
        shown, amount = count < 3, max(0, 3 - count)
        if count >= 3 and relic.data.get('treasures', 0) > 0:
            status = 'disabled'
    elif name == 'winged_boots':
        shown, amount = count < 3, max(0, 3 - count)
        status = 'disabled' if count >= 3 else 'normal'
    elif name in ('bone_tea', 'ember_tea', 'tea_of_discourtesy'):
        remaining = max(0, (5 if name == 'ember_tea' else 1) - count)
        shown, amount = name == 'ember_tea', remaining
        status = 'disabled' if remaining == 0 else 'normal'
        extra['remaining_combats'] = remaining  # Visible tooltip, also when no icon counter.
    elif name == 'paels_tooth':
        amount = len(relic.data.get('cards', ()))
        shown = amount > 0
        status = 'normal' if shown else 'disabled'

    if player:
        active = None
        if name in ATTACK_THREE or name == 'letter_opener':
            shown, amount = True, memory.get('turn_skills' if name == 'letter_opener' else 'turn_attacks', 0) % 3
            active = amount == 2
        elif name == 'rainbow_ring':
            active = memory.get('rainbow_triggered', False)
        elif name == 'brilliant_scarf':
            amount = memory.get('turn_manual', 0)
            shown, active = amount < 5, amount == 4
        elif name in ('diamond_diadem', 'velvet_choker'):
            shown, amount = True, memory.get('turn_plays', 0)
            active = name == 'diamond_diadem' and amount <= 2
        elif name == 'metronome':
            amount = memory.get('count', 0)
            shown, active = amount < 7, amount == 6
        elif name == 'paels_legion':
            amount = memory.get('cooldown', 0)
            shown, active = amount > 0, amount <= 0
        elif name == 'emotion_chip':
            active = memory.get('damaged', False)
        elif name in ('burning_sticks', 'throwing_axe', 'unsettling_lamp', 'vambrace'):
            active = not memory.get('used', False) and (name != 'vambrace' or 'triggering_card' not in memory)
        elif name == 'pocketwatch':
            shown, amount = True, player.rules.finished_plays_turn
            active = amount <= 3
        elif name == 'paels_flesh':
            amount = player.rules.round_number
            shown, active = amount < 3, amount >= 3
        elif name == 'stone_calendar':
            amount = player.rules.round_number
            shown = amount < 7
            active = amount == 7 and player.rules.player_side and not player.rules.turn_ending
        elif name == 'red_skull':
            active = player.hp * 2 <= player.max_hp
        elif name == 'meat_on_the_bone':
            active = player.hp <= player.max_hp // 2
        elif name in ('art_of_war', 'ripple_basin'):
            active = player.rules.attacks_finished == 0
            if name == 'ripple_basin':
                active = active and player.rules.player_side and not player.rules.turn_ending
        elif name == 'belt_buckle':
            active = empty_belt
        elif name == 'paels_eye':
            # An in-flight manual play clears the native status before its
            # finished-play hook updates turn_manual (selectors may suspend it).
            manual_in_flight = any(not v.get('auto') for v in player.rules.plays.values())
            active = not memory.get('used') and not memory.get('turn_manual') and not manual_in_flight
        if active is not None:
            status = 'active' if active else 'normal'
    if relic.data.get('_melted'):
        status = 'disabled'
    return dict(show_counter=shown, display_counter=amount if shown else None,
                status=status, wax=bool(relic.data.get('_wax')),
                melted=bool(relic.data.get('_melted')), **extra)
