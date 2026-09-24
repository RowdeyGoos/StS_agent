"""Episode-local public names, independent of private allocator values."""
from collections import defaultdict


class Identities:
    def __init__(self):
        self.refs = {}
        self.counts = defaultdict(int)
        self.draw_groups = ()
        self.active_powers = set()

    def ref(self, kind, key):
        key = (kind, key)
        if key not in self.refs:
            self.fresh(*key)
        return self.refs[key]

    def fresh(self, kind, key):
        self.refs[kind, key] = f'{kind}:{self.counts[kind]}'
        self.counts[kind] += 1
        return self.refs[kind, key]

    def reconcile_draw(self, visible, draw, signature):
        """An unordered pile cannot establish identity between equal copies.

        Rebind the previous indistinguishable group in public destination order,
        then retain its remaining names in the draw multiset. Exact identities
        of cards already distinguishable in hand/selection never change here.
        Keys are private dispatch identities, not ordering tie breakers.
        """
        current = {key for key, _ in (*visible, *draw)}
        for keys in self.draw_groups:
            names = sorted((self.refs['card', k] for k in keys), key=number)
            destinations = [k for k, _ in (*visible, *draw) if k in keys]
            # A disappeared card could have been consumed by an unobserved
            # automatic effect. It does not establish a private association.
            for key, name in zip(destinations, names):
                self.refs['card', key] = name
            for key in set(keys) - current:
                self.refs.pop(('card', key), None)
        groups = defaultdict(list)
        for key, card in draw:
            groups[signature(card)].append(key)
        self.draw_groups = tuple(tuple(keys) for keys in groups.values() if len(keys) > 1)


def number(ref):
    return int(ref.split(':')[1])
