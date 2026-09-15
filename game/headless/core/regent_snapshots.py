"""Validate Regent resources and owned command continuations."""

TASK_ARITIES = {'regent_forge': 2, 'regent_knockout': 4,
    'regent_energy_reset': 1, 'regent_before_draw': 1, 'regent_remove': 1,
    'regent_side_start_all': 0, 'regent_side_start': 1,
    'regent_start_power': 0, 'regent_end_card': 1, 'regent_preplay': 0}
CHOICES = frozenset('regent_' + op for op in ('begone', 'begone_up', 'charge', 'charge_up',
    'guards', 'guards_up', 'topdeck', 'cosmic_indifference', 'heirloom_hammer',
    'decisions_decisions', 'quasar', 'foregone_conclusion', 'tyranny'))


def validate_state(r, p):
    if type(r.regent_end_requested) is not bool:
        raise ValueError('Invalid pending card turn end.')
    if not isinstance(r.regent_hits, dict) or any(not isinstance(k, str) or not k.isdigit() or str(int(k)) != k or int(k) >= len(p.combat_enemies) or type(v) is not int or v <= 0 for k, v in r.regent_hits.items()):
        raise ValueError('Invalid captured per-enemy hit history.')
    if r.regent_end_requested and not any(c.definition.definition_id == 'void_form' for c in p.deck.in_play):
        raise ValueError('Turn-end request has no owning Void Form.')
    for key in r.powers:
        if (key.startswith(('monologue:', 'orbit:')) or key == 'void_form') and key not in r.auxiliaries:
            raise ValueError('Missing Regent power counter.')


def validate_frame(frame, r):
    if any(type(frame[k]) is not int or frame[k] < 0 for k in ('star_value', 'stars_spent')):
        raise ValueError('Invalid play Stars.')
    if frame['auto'] and frame['stars_spent']:
        raise ValueError('Autoplay cannot spend Stars.')
    captured = frame['regent_before']
    if not isinstance(captured, dict) or any(not isinstance(k, str) or not k.startswith('monologue:') or k not in r.powers or type(v) is not int or v <= 0 for k, v in captured.items()):
        raise ValueError('Invalid captured Monologue instances.')


def validate_task(task, r, p, context):
    op, *args = task
    if op == 'regent_forge':
        frame = r.plays.get(args[0])
        card = next((c for c in p.deck.in_play if c.instance_id == args[0]), None)
        if frame is None or card is None or frame['context'] != context or card.definition.definition_id != 'beat_into_shape' or type(args[1]) is not int or args[1] != frame.get('forge_amount') or args[1] < (7 if card.upgraded else 5):
            raise ValueError('Unowned queued Forge amount.')
    elif op == 'regent_knockout':
        if args[0] not in r.plays or r.plays[args[0]]['context'] != context:
            raise ValueError('Knockout has no owning play.')
        card = next(c for c in p.deck.in_play if c.instance_id == args[0])
        if card.definition.definition_id != 'knockout_blow' or any(type(n) is not int or n < 0 for n in args[1:]) or args[1] >= len(p.combat_enemies) or args[3] != 5:
            raise ValueError('Invalid Knockout continuation.')
    elif op in ('regent_energy_reset', 'regent_before_draw', 'regent_side_start', 'regent_remove'):
        allowed = {'regent_energy_reset': ('genesis', 'energy_next_turn', 'star_next_turn'),
                   'regent_before_draw': ('spectrum_shift', 'foregone_conclusion'),
                   'regent_side_start': ('furnace', 'reflect'),
                   'regent_remove': ('foregone_conclusion',)}[op]
        if args[0] not in allowed or not r.player_side:
            raise ValueError('Invalid Regent setup command.')
    elif op in ('regent_side_start_all', 'regent_preplay') and not r.player_side:
        raise ValueError('Regent setup outside player side.')
    elif op == 'regent_start_power' and not r.powers.get('tyranny'):
        raise ValueError('Unowned Tyranny task.')
    elif op == 'regent_end_card':
        card = next((c for c in p.deck.all_cards() if c.instance_id == args[0]), None)
        if not r.turn_ending or card is None or card.definition.definition_id != 'i_am_invincible':
            raise ValueError('Unowned card postplay hook.')


def validate_selection(r, p, s, *, deferred=False):
    from game.headless.cards.regent_effects import Regent, choice_settings
    from game.headless.core.piles import stratagem_cards
    operation = s['operation'].removeprefix('regent_')
    upgraded = operation.endswith('_up')
    operation = operation.removesuffix('_up')
    source = next((c for c in p.deck.in_play if c.instance_id == s['source']), None)
    if operation in ('foregone_conclusion', 'tyranny'):
        if s['source'] != operation or not r.powers.get(operation):
            raise ValueError('Unowned Regent power selection.')
        cards = stratagem_cards(p) if operation == 'foregone_conclusion' else list(p.hand)
        minimum = maximum = r.powers[operation]
    else:
        if source is None:
            raise ValueError('Regent choice has no owning card.')
        index = r.plays[source.instance_id].get('effect_index')
        if type(index) is not int or not 0 <= index < len(source.definition.effects):
            raise ValueError('Invalid Regent choice effect.')
        effect = source.definition.effects[index]
        if not isinstance(effect, Regent) or effect.operation != operation:
            raise ValueError('Regent choice differs from owning effect.')
        if operation in ('begone', 'charge', 'guards') and upgraded != source.upgraded:
            raise ValueError('Minion upgrade differs from source.')
        if operation == 'quasar':
            cards, minimum, maximum = list(p.deck.offered), 0, 1
            if len(cards) != 3 or any(c.definition.pool != 'colorless' or c.upgraded != source.upgraded for c in cards):
                raise ValueError('Invalid Quasar offer.')
        else:
            cards, minimum, maximum = choice_settings(p, operation)
    candidates = [c.instance_id for c in cards]
    if deferred:
        if s['selected'] or not set(s['candidates']) <= p.deck._allocated_ids:
            raise ValueError('Invalid deferred Regent choice.')
        candidates = s['candidates']
    maximum = min(maximum, len(candidates))
    minimum = min(minimum, maximum)
    if s['candidates'] != candidates or (s['minimum'], s['maximum']) != (minimum, maximum) or s['destination'] != 'hand' or s['free'] or 'whitelist' in s:
        raise ValueError('Regent selection differs from its source.')
