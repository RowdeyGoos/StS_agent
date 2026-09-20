"""Ownership checks for Silent continuations, choices and delayed card copies."""

TASK_ARITIES = {
    'silent_shivs': 3, 'silent_random_poison': 1, 'silent_strength_loss': 2,
    'silent_knife': 3, 'silent_hunt': 3, 'silent_echo': 4,
    'silent_escape_draw': 2, 'silent_escape_after_shuffle': 2, 'silent_escape_block': 3,
    'silent_area_damage': 1, 'silent_damage': 2,
    'silent_strangle': 2, 'silent_outbreak_reset': 0,
    'silent_poison_begin': 1, 'silent_poison_tick': 1, 'silent_poison_decrement': 1,
    'silent_retain': 0, 'silent_side_start': 1, 'silent_side_start_all': 0,
}
PLAY_TASKS = frozenset(('silent_hunt', 'silent_echo', 'silent_escape_draw', 'silent_escape_after_shuffle', 'silent_escape_block'))
CHOICES = frozenset(('discard', 'hand_trick', 'nightmare', 'well_laid_plans'))


def validate_state(r, p):
    from game.headless.core.snapshots import restore_card
    from game.headless.cards.colorless_effects import catalog
    if not isinstance(r.nightmares, dict):
        raise ValueError('Invalid delayed card copies.')
    if set(r.nightmares) != {k for k in r.powers if k.startswith("nightmare:")} or any(r.powers[k] != 3 for k in r.nightmares):
        raise ValueError("Unowned Nightmare template.")
    for record in r.nightmares.values():
        if not isinstance(record, dict):
            raise ValueError('Invalid Nightmare blueprint.')
        card = restore_card(record, catalog(p))
        if card.instance_id not in p.deck._allocated_ids:
            raise ValueError('Nightmare references an unallocated original.')
    if r.skills_finished > r.skills_started or r.shivs_finished > r.attacks_finished:
        raise ValueError('Invalid Silent play history.')
    if r.auxiliaries.get('outbreak', 0) >= 3 and not any(t[0] == 'silent_outbreak_reset' for t in r.tasks):
        raise ValueError('Unfinished Outbreak has no reset.')


def validate_frame(frame, p):
    if 'echo_kills' in frame and (type(frame['echo_kills']) is not int or frame['echo_kills'] < 0):
        raise ValueError('Invalid captured attack kill results.')
    captured = frame.get('silent_before')
    if not isinstance(captured, dict) or set(captured) != {'afterimage', 'serpent_form', 'strangle'}:
        raise ValueError('Invalid captured pre-play powers.')
    if any(type(captured[k]) is not int or captured[k] < 0 for k in ('afterimage', 'serpent_form')):
        raise ValueError('Invalid captured power amount.')
    if not isinstance(captured['strangle'], list) or len(captured['strangle']) > len(p.combat_enemies) or any(type(n) is not int or n < 0 for n in captured['strangle']):
        raise ValueError('Invalid captured Strangle participants.')


def validate_task(task, r, p, context):
    op, *args = task
    def natural(n):
        if type(n) is not int or n < 0:
            raise ValueError('Invalid Silent task amount.')
    def flag(v):
        if type(v) is not bool:
            raise ValueError('Invalid Silent task flag.')
    def slot(n):
        natural(n)
        if n >= len(p.combat_enemies):
            raise ValueError('Invalid Silent task target.')
    if op in PLAY_TASKS:
        if args[0] not in r.plays or r.plays[args[0]]['context'] != context:
            raise ValueError('Silent task has no owning play.')
        card = next(c for c in p.deck.in_play if c.instance_id in r.plays and c.instance_id == args[0])
        expected = {'silent_hunt':'the_hunt', 'silent_echo':'echoing_slash', 'silent_escape_draw':'escape_plan', 'silent_escape_after_shuffle':'escape_plan', 'silent_escape_block':'escape_plan'}[op]
        if card.definition.definition_id != expected:
            raise ValueError('Silent task differs from its owning card.')
        for n in args[1:]:
            if type(n) is not bool:
                natural(n)
        if op == 'silent_hunt':
            slot(args[1])
        if op == 'silent_echo' and ('echo_kills' not in r.plays[args[0]] or args[3] > r.plays[args[0]]['echo_kills']):
            raise ValueError('Unowned Echoing Slash kill history.')
        if op == 'silent_escape_block':
            flag(args[2])
    elif op == 'silent_knife':
        if args[0] not in p.deck._allocated_ids or args[0] in r.plays:
            raise ValueError('Invalid queued Shiv.')
        slot(args[1]); flag(args[2])
    elif op in ('silent_strength_loss', 'silent_damage', 'silent_strangle'):
        slot(args[0]); natural(args[1])
    elif op in ('silent_poison_begin', 'silent_poison_tick', 'silent_poison_decrement'):
        slot(args[0])
        if r.player_side or r.enemy_turn is None or not r.enemy_turn.get('poison_start'):
            raise ValueError('Poison task outside the captured enemy side start.')
    elif op == 'silent_shivs':
        natural(args[0]); flag(args[1]); flag(args[2])
    elif op in ('silent_random_poison', 'silent_area_damage'):
        natural(args[0])
    elif op == 'silent_side_start_all':
        if not r.player_side:
            raise ValueError('Side-start dispatch outside player setup.')
    elif op == 'silent_side_start':
        if args[0] not in ('blur', 'shadow_step', 'noxious_fumes') or not r.player_side:
            raise ValueError('Invalid side-start power.')
    elif op == 'silent_retain':
        if not r.turn_ending or not r.powers.get('well_laid_plans'):
            raise ValueError('Unowned late retain choice.')
    elif op == 'silent_outbreak_reset' and not r.powers.get('outbreak'):
        raise ValueError('Unowned Outbreak reset.')


def validate_selection(r, p, s, *, deferred=False):
    from game.headless.cards.silent_effects import Silent
    from game.headless.powers.silent import is_sly
    operation = s['operation']
    source = next((c for c in p.deck.in_play if c.instance_id in r.plays and c.instance_id == s['source']), None)
    if source is None:
        key = s['source']
        if key not in ('well_laid_plans', 'tools_of_the_trade') or not r.powers.get(key):
            raise ValueError('Unowned Silent power choice.')
        expected_op = 'discard' if key == 'tools_of_the_trade' else key
        count = r.powers[key]
        if key == 'well_laid_plans' and not r.turn_ending:
            raise ValueError('Retain choice outside turn end.')
    else:
        frame = r.plays[source.instance_id]
        index = frame.get('effect_index')
        if type(index) is not int or not 0 <= index < len(source.definition.effects):
            raise ValueError('Invalid Silent selection effect.')
        effect = source.definition.effects[index]
        if not isinstance(effect, Silent) or effect.operation not in CHOICES:
            raise ValueError('Unowned Silent card choice.')
        expected_op = effect.operation
        count = (effect.upgraded_amount if source.upgraded and effect.upgraded_amount is not None else effect.amount) if operation == 'discard' else 1
    cards = list(p.hand)
    if operation == 'hand_trick':
        cards = [c for c in cards if c.spec.kind in ('skill', 'block') and not is_sly(c)]
    elif operation == 'well_laid_plans':
        cards = [c for c in cards if not c.spec.retain]
    candidates = [c.instance_id for c in cards]
    if deferred:
        if s["selected"] or not set(s["candidates"]) <= p.deck._allocated_ids:
            raise ValueError("Invalid deferred live hand choice.")
        candidates = s["candidates"]
    maximum = min(count, len(candidates))
    minimum = 0 if operation == 'well_laid_plans' else maximum
    if (operation != expected_op or s['candidates'] != candidates
            or (s['minimum'], s['maximum']) != (minimum, maximum)
            or s['destination'] != 'hand' or s['free'] or 'whitelist' in s):
        raise ValueError('Silent choice differs from its source.')
