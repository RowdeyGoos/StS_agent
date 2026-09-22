"""Validate owned pet state, Necrobinder history and suspended commands."""

from game.headless.cards.necrobinder_effects import CHOICE_OPS

CHOICES = frozenset('nec_' + op for op in CHOICE_OPS)
TASK_ARITIES = {'osty_hit': 5, 'osty_after': 2, 'nec_souls': 3, 'nec_intangible': 0,
    'nec_blight': 3, 'nec_spread': 2, 'nec_copy_debuff': 3, 'nec_enemy_loss': 4, 'nec_summon': 3,
    'nec_kill_osty': 0, 'nec_doom_kill': 2, 'nec_doom_after': 2, 'nec_player_doom': 0,
    'nec_side_start': 1, 'nec_start': 0, 'nec_before_draw': 1}


def natural(value):
    if type(value) is not int or value < 0:
        raise ValueError('Invalid Necrobinder amount.')


def validate_state(r, p):
    if r.osty is not None:
        if not isinstance(r.osty, dict) or set(r.osty) != {'hp', 'max_hp'}:
            raise ValueError('Invalid Osty fields.')
        natural(r.osty['hp']); natural(r.osty['max_hp'])
        if not 0 <= r.osty['hp'] <= r.osty['max_hp'] or not r.osty['max_hp']:
            raise ValueError('Invalid Osty HP.')
    if not p.is_alive and r.osty is not None and r.osty['hp']:
        raise ValueError('Dead player cannot own a living Osty.')
    for key in ('osty_attacks_turn', 'ethereal_plays', 'drawn_turn'):
        natural(getattr(r, key))
    if type(r.doom_applied_turn) is not bool:
        raise ValueError('Invalid Doom application history.')
    if not isinstance(r.fetch_plays, list) or any(not isinstance(i, str) or i not in p.deck._allocated_ids for i in r.fetch_plays) or len(r.fetch_plays) != len(set(r.fetch_plays)):
        raise ValueError('Invalid Fetch history.')
    if not isinstance(r.scythe_gains, dict) or any(not isinstance(k, str) or k not in p.deck._allocated_ids or type(v) is not int or v < 0 for k,v in r.scythe_gains.items()):
        raise ValueError('Invalid persistent Scythe gains.')
    for identity, gain in r.scythe_gains.items():
        card = next((c for c in p.deck.all_cards() if c.instance_id == identity), None)
        if card is not None and (card.definition.definition_id != 'the_scythe' or card.permanent_damage < gain):
            raise ValueError('Scythe gain differs from its physical card.')
    if 'summon_next_turn' in r.powers and r.auxiliaries.get('summon_next_turn') not in (0, 1):
        raise ValueError('Invalid delayed summon eligibility.')


def validate_frame(frame, p):
    listeners = frame['nec_banshees']
    if not isinstance(listeners, list) or any(not isinstance(i, str) or i not in p.deck._allocated_ids for i in listeners) or len(listeners) != len(set(listeners)):
        raise ValueError('Invalid captured Banshees Cry listeners.')
    captured = frame['nec_before']
    if not isinstance(captured, dict) or any(not isinstance(k, str) or not k.isdigit() or str(int(k)) != k or int(k) >= len(p.combat_enemies) or type(v) is not int or v <= 0 for k,v in captured.items()):
        raise ValueError('Invalid captured Oblivion.')
    if type(frame['nec_first_attack']) is not bool:
        raise ValueError('Invalid first attack history.')
    if 'nec_misery' in frame:
        from game.headless.powers.necrobinder import copied_debuffs
        from game.headless.powers.status import SUPPORTED_STATUS_NAMES
        values = frame['nec_misery']
        if not isinstance(values, dict) or any(k not in (*SUPPORTED_STATUS_NAMES, 'strength') or type(v) is not int or (v >= 0 if k == 'strength' else v <= 0) for k, v in values.items()):
            raise ValueError('Invalid captured debuffs.')


def validate_task(task, r, p, context):
    from game.headless.cards.osty_effects import OstyAttack
    op, *args = task
    def slot(n):
        natural(n)
        if n >= len(p.combat_enemies):
            raise ValueError('Invalid Necrobinder target slot.')
    def owner(identity):
        if identity not in r.plays or r.plays[identity]['context'] != context:
            raise ValueError('Necrobinder command has no owning play.')
        return next(c for c in p.deck.in_play if c.instance_id in r.plays and c.instance_id == identity)
    if op in ('osty_hit', 'osty_after'):
        c = owner(args[0])
        if not any(isinstance(e, OstyAttack) for e in c.definition.effects):
            raise ValueError('Pet attack differs from card source.')
        if op == 'osty_hit':
            if args[1] is not None: slot(args[1])
            if any(type(v) is not bool for v in args[2:4]):
                raise ValueError('Invalid pet attack targeting.')
            natural(args[4])
        elif args[1] not in ('', 'bone_shards', 'fetch', 'high_five') or (args[1] and args[1] != c.definition.definition_id):
            raise ValueError('Invalid pet after-attack effect.')
    elif op in ('nec_blight', 'nec_spread'):
        c = owner(args[0]); slot(args[1])
        if c.definition.definition_id != ('blight_strike' if op == 'nec_blight' else 'misery'):
            raise ValueError('Captured attack differs from source.')
        if op == 'nec_blight': natural(args[2])
        elif 'nec_misery' not in r.plays[args[0]]:
            raise ValueError('Missing captured Misery debuffs.')
    elif op == 'nec_souls':
        c = owner(args[0]); natural(args[1])
        if c.definition.definition_id not in ('capture_spirit', 'dirge') or type(args[2]) is not bool:
            raise ValueError('Unowned Soul generation.')
        count = (4 if c.upgraded else 3) if c.definition.definition_id == 'capture_spirit' else r.plays[args[0]]['x']
        if args[1] != count or args[2] != (c.upgraded and c.definition.definition_id == 'dirge'):
            raise ValueError('Soul count differs from source.')
    elif op == 'nec_copy_debuff':
        from game.headless.powers.status import SUPPORTED_STATUS_NAMES
        slot(args[0]); natural(args[2])
        if args[1] not in SUPPORTED_STATUS_NAMES:
            raise ValueError('Unknown copied debuff.')
        if not any(c.definition.definition_id == 'misery' and r.plays.get(c.instance_id, {}).get('context') == context for c in p.deck.in_play):
            raise ValueError('Copied debuff has no owning Misery.')
    elif op == 'nec_enemy_loss':
        slot(args[0]); natural(args[1])
        if type(args[2]) is not bool: raise ValueError('Invalid damage properties.')
        source = args[3]
        if source in ('haunt', 'sleight_of_flesh', 'necro_mastery'):
            amount = r.powers.get(source, 0)
            if not amount or args[2] != (source != 'sleight_of_flesh'):
                raise ValueError('Damage has no producing power.')
            if source == 'necro_mastery':
                if r.osty is None or args[1] % amount or not 0 < args[1] // amount <= r.osty['max_hp']:
                    raise ValueError('Invalid captured Osty HP loss.')
            elif args[1] != amount:
                raise ValueError('Damage differs from producing power.')
        else:
            c = owner(source)
            if c.definition.definition_id != 'capture_spirit' or args[1] != c.spec.base_damage or not args[2] or r.plays[source]['target'] != args[0]:
                raise ValueError('Damage differs from Capture Spirit.')
    elif op == 'nec_summon':
        natural(args[0]); c = owner(args[1])
        if args[2] is None:
            if c.definition.definition_id != 'dirge' or args[0] != (4 if c.upgraded else 3):
                raise ValueError('Summon differs from Dirge.')
        else:
            slot(args[2])
            if not any(isinstance(e, OstyAttack) for e in c.definition.effects) or args[0] != p.combat_enemies[args[2]].statuses.get('sic_em') or not args[0]:
                raise ValueError('Summon has no producing Osty/Sic Em hit.')
    elif op in ('nec_doom_kill', 'nec_doom_after'):
        if op == 'nec_doom_after':
            from game.headless.relics.combat import has
            if not has(p, 'book_repair_knife') or not isinstance(args[0], list) or not args[0]:
                raise ValueError('Unowned Doom batch completion.')
            for index in args[0]: slot(index)
            if len(set(args[0])) != len(args[0]):
                raise ValueError('Repeated Doom batch target.')
        else:
            slot(args[0])
        if args[1] == 'enemy_end':
            if r.player_side or r.enemy_turn is None or not r.enemy_turn.get('doom_end'):
                raise ValueError('Doom kill outside enemy end.')
        elif owner(args[1]).definition.definition_id != 'end_of_days':
            raise ValueError('Doom kill has no End of Days source.')
        # Both tasks have emitted receipts: a prior death callback may have
        # killed or changed a later captured victim before this task resumes.
    elif op == 'nec_player_doom':
        if not r.turn_ending: raise ValueError('Player Doom outside turn end.')
    elif op in ('nec_start', 'nec_before_draw', 'nec_side_start'):
        if not r.player_side: raise ValueError('Necrobinder setup outside player side.')
        if args and args[0] not in (('call_of_the_void', 'sentry_mode') if op == 'nec_before_draw' else ('countdown', 'neurosurge')):
            raise ValueError('Unknown Necrobinder setup power.')
    elif op == 'nec_intangible':
        if not any(c.definition.definition_id == 'eidolon' for c in p.deck.in_play):
            raise ValueError('Unowned Eidolon continuation.')
    elif op == 'nec_kill_osty':
        if not any(c.definition.definition_id == 'bone_shards' for c in p.deck.in_play):
            raise ValueError('Unowned pet sacrifice.')


def validate_selection(r, p, s, *, deferred=False):
    from game.headless.cards.necrobinder_effects import Necro, choice_settings
    source = next((c for c in p.deck.in_play if c.instance_id in r.plays and c.instance_id == s['source']), None)
    if source is None:
        raise ValueError('Necrobinder selection has no source.')
    frame = r.plays.get(source.instance_id)
    index = frame.get('effect_index') if frame else None
    if type(index) is not int or not 0 <= index < len(source.definition.effects):
        raise ValueError('Invalid selection effect.')
    effect = source.definition.effects[index]
    operation = s['operation'].removeprefix('nec_')
    if not isinstance(effect, Necro) or effect.operation != operation:
        raise ValueError('Selection differs from its owning effect.')
    cards, count = choice_settings(p, operation)
    ids = [c.instance_id for c in cards]
    if deferred:
        if s['selected'] or not set(s['candidates']) <= p.deck._allocated_ids:
            raise ValueError('Invalid deferred Necrobinder choice.')
        ids = s['candidates']
    if s['candidates'] != ids or s['minimum'] != min(count,len(ids)) or s['maximum'] != min(count,len(ids)) or s['destination'] != 'hand' or s['free'] or 'whitelist' in s:
        raise ValueError('Invalid Necrobinder choice candidates or bounds.')
