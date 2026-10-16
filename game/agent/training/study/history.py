"""Episode-local history derived only from accepted public transitions/reveals.

Enemy records describe the displayed profile before an observed enemy phase.
They do not claim that every displayed effect executed, or expose a move ID.
"""
from dataclasses import replace
from game.agent.contracts import full as f
from .spec import INTENTS

COUNTERS = ('plays', 'attacks', 'skills', 'zero_cost_attacks', 'energy_spent', 'status_draws')


def current_combat_context(public):
    """Keep native facts; omit the attachment's detached played-card log.

    Active creature powers are separate ``powers`` nodes and remain intact.
    Historical card descriptions have no current physical-card association.
    """
    historical = tuple(n for n in public.context.children
        if n.kind == 'pile' and n.definition_id == 'powers'
        and n.get('coverage') == 'observed_plays')
    context = replace(public.context, children=tuple(n for n in public.context.children
                                                   if n not in historical))
    old_refs = {n.ref for pile in historical for n in f.walk(pile) if n.ref}
    detached = old_refs - {n.ref for n in f.walk(context) if n.ref}
    if (any(a.subject in detached or a.target in detached for a in public.candidates)
            or any(ref in detached for n in f.walk(context) if n.kind == 'selection'
                   for link in n.links for ref in link.targets)):
        raise ValueError('Historical played-card description cannot own a current operand')
    return context


def _prefix_endpoint(public):
    """Fresh adapters lack attachment history; all current facts still match.

    Verified prefix transitions own the supplement's counters and profiles.
    The adapter's duplicate descriptive action log is not part of the study
    projection and is not native snapshot state. Compact supplements below
    remain bound to the complete actual public observation, without this view.
    """
    from game.agent.input_views import planning_view
    from game.agent.search.public_keys import public_key
    public=planning_view(public)
    children=tuple(n for n in public.run.children
                   if not (n.kind=='history' and n.get('coverage')=='attachment'))
    return public_key(replace(public,run=replace(public.run,children=children),
                              context=current_combat_context(public)))


def enemies(public):
    return [n for n in f.walk(public.context) if n.kind == 'enemy']


def intent(enemy):
    icons = [n for n in enemy.children if n.kind == 'intent']
    attacks = [n for n in icons if n.definition_id == 'attack']
    known = (bool(icons) and all(n.definition_id in INTENTS and n.definition_id != 'unknown' for n in icons)
             and all(type(n.get('damage')) is int and type(n.get('hits')) is int for n in attacks))
    return dict(icons=tuple(sorted({n.definition_id if n.definition_id in INTENTS else 'unknown'
                                   for n in icons})),
                damage=sum(n.get('damage') * n.get('hits') for n in attacks) if known else None,
                hits=sum(n.get('hits') for n in attacks) if known else None,
                present=bool(icons))


class PublicHistory:
    def __init__(self, card_types=None, catalog=None):
        self.card_types = card_types or {}
        self.catalog = catalog or {}
        self.reset()

    def reset(self, public=None, *, opening=False, reveals=None):
        self.round = public.context.get('round') if public is not None else None
        self.counts = dict.fromkeys(COUNTERS, 0 if opening else None)
        self.profiles = {}
        self.complete = bool(opening)
        self.current = public
        if opening:
            self._draws(reveals)
            if public is not None and self._automatic(public):
                for key in COUNTERS[:-1]:
                    self.counts[key] = None

    def restore(self, anchor, public):
        if anchor is None:
            self.reset(public)
            return
        from .spec import HISTORY, digest
        from game.agent.search.public_keys import public_key
        from game.agent.input_views import planning_view
        if anchor.get('schema') == HISTORY:
            if anchor['public_sha256'] != digest(public_key(planning_view(public))):
                raise ValueError('Public history supplement endpoint changed')
            if set(anchor['counts']) != set(COUNTERS):
                raise ValueError('Public history counter schema changed')
            self.counts = dict(anchor['counts'])
            self.profiles = {int(k): [dict(p) for p in rows] for k, rows in anchor['profiles'].items()}
            self.round, self.complete, self.current = anchor['round'], anchor['complete'], public
            return
        opening = f.from_dict(anchor['opening'])
        self.reset(opening, opening=True, reveals=anchor.get('opening_reveals'))
        before = opening
        for transition in anchor['transitions']:
            action = next(a for a in before.candidates if a.ref == transition['action_ref'])
            after = f.from_dict(transition['successor'])
            self.observe(before, action, after, transition.get('reveals'))
            before = after
        # Native continuation restoration can allocate different opaque refs.
        # The source importer verifies exact native and public equivalence;
        # only stable enemy slots, round and semantic values survive here.
        if _prefix_endpoint(before) != _prefix_endpoint(public):
            raise ValueError('History prefix does not end at this public start')
        self.current = public

    def export(self, public):
        from .spec import HISTORY, digest
        from game.agent.search.public_keys import public_key
        from game.agent.input_views import planning_view
        self.require_current(public)
        return dict(schema=HISTORY, public_sha256=digest(public_key(planning_view(public))),
            counts=dict(self.counts), profiles={k: [dict(p) for p in rows] for k, rows in self.profiles.items()},
            round=self.round, complete=self.complete)

    def _add(self, key, value):
        if self.counts[key] is not None:
            self.counts[key] = None if value is None else self.counts[key] + value

    def _draws(self, reveals):
        if reveals is None:
            self.counts['status_draws'] = None
            return
        for event in reveals:
            if event['kind'] == 'draw':
                kind = self.card_types.get(event['value'][0])
                self._add('status_draws', None if kind is None else int(kind == 'status'))
            elif event['kind'] == 'autoplay_top':
                # Auto-play count/payment is not fully specified by this receipt.
                for key in COUNTERS[:-1]:
                    self.counts[key] = None

    def _automatic(self, public):
        # These are public content descriptions, never hidden trigger flags.
        # A possible repeat/auto-play is enough to stop claiming complete counts.
        for node in (*f.walk(current_combat_context(public)), *f.walk(public.run)):
            if node.kind == 'power' and node.definition_id in (
                'one_two_punch', 'burst', 'duplication', 'echo_form', 'hellraiser', 'signal_boost', 'mayhem'):
                return True
            if node.kind == 'enchantment':
                # Some enchantments have public conditional replays whose
                # activation is not reconstructible from the accepted action.
                return True
            if node.kind == 'relic' and self._rule(node, ('extra_play', 'autoplay_legal_hand_cards', 'autoplay')):
                return True
        return False

    def _rule(self, node, kinds):
        entry = self.catalog.get((node.kind, node.definition_id))
        return bool(entry and any(v.key.endswith('.kind') and v.value in kinds for v in entry.fields))

    def observe(self, before, action, after, reveals=None):
        if not isinstance(after, f.PublicDecision):
            self.current = None
            return
        if self.current is not before:
            self.reset(before)
        previous, current = before.context.get('round'), after.context.get('round')
        if type(previous) is not int or type(current) is not int or current < previous:
            self.reset(after)
            return
        if current != previous:
            if current == previous + 1 and action.kind == 'end_turn':
                extra_turn_possible = any(n.kind == 'relic' and
                    self._rule(n, ('exhaust_hand_and_take_extra_turn',)) for n in f.walk(before.run))
                for enemy in enemies(before):
                    if enemy.get('alive'):
                        rows = self.profiles.setdefault(enemy.get('slot'), [])
                        rows.insert(0, dict(intent(enemy), round=previous,
                                            phase_observed=None if extra_turn_possible else True))
                        del rows[3:]
                self.counts = dict.fromkeys(COUNTERS, 0)
                # This receipt spans end-of-old-turn effects and new-turn draw.
                # It has no phase markers, so assigning every draw to the new
                # turn would be false precision (e.g. ethereal/Dark Embrace).
                self.counts['status_draws'] = None
                if self._automatic(after):
                    for key in COUNTERS[:-1]:
                        self.counts[key] = None
            else:
                self.profiles.clear()
                self.complete = False
                self.counts = dict.fromkeys(COUNTERS, None)
        elif action.kind == 'play_card':
            card = next((n for n in f.walk(before.context) if n.ref == action.subject), None)
            spec = next((n for n in card.children if n.kind == 'spec'), None) if card else None
            kind = spec.get('kind') if spec else None
            cost = card.get('energy') if card else None
            if type(cost) is not int or cost < 0:
                cost = None
            self._add('plays', 1)
            self._add('attacks', None if kind is None else int(kind == 'attack'))
            self._add('skills', None if kind is None else int(kind in ('skill', 'block')))
            self._add('zero_cost_attacks', None if kind is None or cost is None else int(kind == 'attack' and cost == 0))
            # Printed payable cost, never a net-energy difference after refunds.
            self._add('energy_spent', cost)
            replay = card.get('replay_count', 0) if card else None
            automatic = replay is None or replay > 0 or self._automatic(before)
            if automatic:
                for key in ('plays', 'attacks', 'skills', 'zero_cost_attacks'):
                    self.counts[key] = None
        self._draws(reveals)
        self.round, self.current = current, after

    def require_current(self, public):
        if self.current is not public:
            # Playback without transition receipts remains valid but unknown.
            self.reset(public)
