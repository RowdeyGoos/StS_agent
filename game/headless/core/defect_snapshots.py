"""Validate orb identity/order, Defect play history and source-owned continuations."""

from game.headless.core.orbs import KINDS

TASK_ARITIES = {'orb_channel': 1, 'orb_insert': 1, 'orb_evoke': 2, 'orb_phase': 1,
    'orb_front_passive': 0, 'orb_trigger_once': 3, 'orb_trigger': 3, 'orb_damage': 3, 'orb_thunder': 2,
    'def_compact': 2, 'def_flak': 2, 'def_sunder': 3, 'def_scrape': 1,
    'def_scrape_draw': 2, 'def_scrape_after_shuffle': 2, 'def_discard': 1, 'def_status': 1,
    'def_energy_reset': 1, 'def_decrement': 1, 'def_before_draw': 1,
    'def_generate_power': 0, 'def_side_start': 1, 'def_start_power': 1,
    'def_early_end': 1, 'def_end_power': 1, 'def_generated': 2, 'def_rocket': 1,
    'def_damage': 2}


def natural(n):
    if type(n) is not int or n < 0:
        raise ValueError('Invalid Defect amount.')


def validate_state(r, p):
    natural(r.orb_slots)
    if not p.is_alive and (r.orb_slots or r.orb_order):
        raise ValueError('Dead owner retains active orbs.')
    order = r.before_side_end_order
    if not isinstance(order, list) or any(k not in ('player_doom', 'hailstorm') for k in order) or len(set(order)) != len(order):
        raise ValueError('Invalid side-end listener order.')
    if p.statuses.get('doom') and r.powers.get('hailstorm') and set(order) != {'player_doom', 'hailstorm'}:
        raise ValueError('Missing active side-end listener order.')
    if r.orb_slots > 10 or not isinstance(r.orbs, dict):
        raise ValueError('Invalid orb capacity or registry.')
    if set(r.orbs) != {f'orb.{i}' for i in range(len(r.orbs))}:
        raise ValueError('Invalid owned orb identities.')
    for orb in r.orbs.values():
        if not isinstance(orb, dict) or set(orb) != {'kind', 'value'} or orb['kind'] not in KINDS:
            raise ValueError('Invalid orb definition.')
        natural(orb['value'])
        if ((orb['kind'] == 'glass' and orb['value'] > 4)
                or (orb['kind'] == 'dark' and orb['value'] < 6)
                or (orb['kind'] not in ('glass', 'dark') and orb['value'])):
            raise ValueError('Invalid orb lifetime value.')
    if not isinstance(r.orb_order, list) or any(not isinstance(i, str) or i not in r.orbs for i in r.orb_order) or len(set(r.orb_order)) != len(r.orb_order) or len(r.orb_order) > r.orb_slots:
        raise ValueError('Invalid active orb queue.')
    for name in ('series_turn', 'zero_attacks_turn', 'energy_spent_turn', 'status_draws_turn', 'finished_plays_turn'):
        natural(getattr(r, name))
    if not isinstance(r.genetic_gains, dict) or any(not isinstance(k,str) or k not in p.deck._allocated_ids or type(v) is not int or v < 0 for k,v in r.genetic_gains.items()):
        raise ValueError('Invalid persistent Genetic Algorithm gains.')
    for identity, gain in r.genetic_gains.items():
        card = next((c for c in p.deck.all_cards() if c.instance_id == identity), None)
        if card is not None and (card.definition.definition_id != 'genetic_algorithm' or card.permanent_block < gain):
            raise ValueError('Genetic Algorithm gain differs from its physical card.')
    if 'feral' in r.powers and 'feral' not in r.auxiliaries:
        raise ValueError('Missing Feral usage counter.')


def validate_frame(frame, p, card):
    captured = frame['def_before']
    keys = {'storm', 'subroutine'} if card.spec.kind == 'power' else set()
    if not isinstance(captured, dict) or set(captured) != keys or any(type(v) is not int or v < 0 for v in captured.values()):
        raise ValueError('Invalid captured Defect powers.')
    if type(frame['def_feral']) is not bool:
        raise ValueError('Invalid Feral return marker.')
    if frame['def_feral'] and (frame['destination'] != 'hand' or frame['energy_value'] or card.spec.kind != 'attack'):
        raise ValueError('Invalid Feral return source.')
    if 'def_scrape' in frame:
        ids = frame['def_scrape']
        if card.definition.definition_id != 'scrape' or not isinstance(ids, list) or any(not isinstance(i, str) or i not in p.deck._allocated_ids for i in ids):
            raise ValueError('Invalid captured Scrape draw.')


def validate_task(task, r, p, context):
    op, *args = task
    def slot(n):
        natural(n)
        if n >= len(p.combat_enemies):
            raise ValueError('Invalid orb target slot.')
    def orb(identity):
        if identity not in r.orbs:
            raise ValueError('Unowned orb continuation.')
    def owner(identity, definition):
        card = next((c for c in p.deck.in_play if c.instance_id in r.plays and c.instance_id == identity), None)
        if card is None or card.definition.definition_id != definition or r.plays[identity]['context'] != context:
            raise ValueError('Defect continuation has no owning play.')
        return card
    if op in ('orb_channel', 'orb_insert'):
        if args[0] not in (*KINDS, *(['random'] if op == 'orb_channel' else [])):
            raise ValueError('Unknown channeled orb.')
    elif op == 'orb_evoke':
        if any(type(a) is not bool for a in args):
            raise ValueError('Invalid evoke properties.')
    elif op == 'orb_phase':
        if args[0] not in ('start', 'end'):
            raise ValueError('Invalid orb phase.')
        if (args[0] == 'end') != r.turn_ending or not r.player_side:
            raise ValueError('Orb passive outside its owner phase.')
    elif op in ('orb_trigger', 'orb_trigger_once'):
        orb(args[0])
        if args[1] not in ('passive', 'evoke'):
            raise ValueError('Invalid orb trigger kind.')
        if args[2] is not None:
            slot(args[2])
            if r.orbs[args[0]]['kind'] != 'lightning' or args[1] != 'passive':
                raise ValueError('Invalid targeted passive.')
    elif op in ('orb_damage', 'orb_thunder'):
        orb(args[0]); slot(args[1])
        if op == 'orb_damage': natural(args[2])
        elif r.orbs[args[0]]['kind'] != 'lightning':
            raise ValueError('Thunder has no Lightning source.')
    elif op == 'def_compact':
        owner(args[0], 'compact')
        if args[1] not in p.deck._allocated_ids: raise ValueError('Unowned transformed status.')
    elif op in ('def_flak', 'def_sunder', 'def_scrape', 'def_scrape_draw', 'def_scrape_after_shuffle'):
        definition = {'def_flak':'flak_cannon', 'def_sunder':'sunder', 'def_scrape':'scrape', 'def_scrape_draw':'scrape', 'def_scrape_after_shuffle':'scrape'}[op]
        owner(args[0], definition)
        for n in args[1:]: natural(n)
        if op == 'def_sunder':
            slot(args[1])
            if args[2] != 3: raise ValueError('Invalid Sunder reward.')
        if definition == 'scrape' and 'def_scrape' not in r.plays[args[0]]:
            raise ValueError('Missing Scrape capture.')
    elif op in ('def_discard', 'def_rocket'):
        if args[0] not in p.deck._allocated_ids: raise ValueError('Unowned Defect card hook.')
    elif op == 'def_status':
        if args[0] not in ('dazed', 'wound', 'slimed', 'burn', 'void'):
            raise ValueError('Invalid generated status.')
    elif op == 'def_before_draw': natural(args[0])
    elif op == 'def_generated':
        if args[0] not in ('arsenal', 'pillar_of_creation', 'smokestack', 'trash_to_treasure') or args[1] not in p.deck._allocated_ids:
            raise ValueError('Invalid status generation hook.')
    elif op == 'def_damage':
        slot(args[0]); natural(args[1])
    elif op in ('def_energy_reset', 'def_decrement', 'def_side_start', 'def_start_power', 'def_early_end', 'def_end_power'):
        choices = {'def_energy_reset':('lightning_rod','spinner'), 'def_decrement':('lightning_rod',),
            'def_side_start':('coolant','feral','biased_cognition'), 'def_start_power':('loop',), 'def_early_end':('hailstorm',),
            'def_end_power':('focused_strike','hotfix','synchronize','consuming_shadow')}
        if args[0] not in choices[op]: raise ValueError('Invalid Defect power hook.')
