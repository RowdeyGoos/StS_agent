"""Native all-unlocked solo startup after relic bags, before entering Act 1.

Future room sets are plain initialization data. They advance the shared UpFront
stream without pretending to implement later-act combat or event behavior.
"""

from game.headless.generation.room_pools import campaign_pools, SHARED_EVENTS, SHARED_ANCIENTS, ENCOUNTER_TAGS

PROFILE = "native_overgrowth_hive_glory_all_unlocked_v1"


def compatible(previous, candidate):
    return candidate != previous and not set(ENCOUNTER_TAGS.get(previous, ())).intersection(
        ENCOUNTER_TAGS.get(candidate, ())
    )


def extend_queue(rng, queue, pool, count):
    bag = []
    for _ in range(count):
        if not bag:
            bag = list(pool)
        previous = queue[-1] if queue else None
        restricted = any(compatible(previous, name) for name in bag)
        # Native GrabBag retries the full weighted bag. Rejections consume draws,
        # and the zero-eligible fallback draws once from the unfiltered bag.
        while True:
            index = int(rng.double("up_front") * len(bag))
            chosen = bag[index]
            if not restricted or compatible(previous, chosen):
                break
        bag.pop(index)
        queue.append(chosen)


def generate(rng, *, act="overgrowth", ascension=0):
    pools_by_act = campaign_pools(act)
    if not getattr(rng, "native", False):
        raise ValueError("Native initialization requires a native RNG owner.")
    remaining = list(SHARED_ANCIENTS)
    rng.shuffle("up_front", remaining)
    subsets = []
    for _ in pools_by_act[1:]:
        count = rng.randint("up_front", 0, len(remaining))
        subsets.append(remaining[:count])
        remaining = remaining[count:]
    acts = []
    for index, (name, rooms, weak_count, events, ancients, pools) in enumerate(pools_by_act):
        event_queue = list((*events, *SHARED_EVENTS))
        rng.shuffle("up_front", event_queue)
        normal, elites = [], []
        extend_queue(rng, normal, pools[0], weak_count)
        extend_queue(rng, normal, pools[1], rooms - weak_count)
        extend_queue(rng, elites, pools[2], 15)
        boss = rng.choice("up_front", pools[3])
        ancient = rng.choice("up_front", (*ancients, *(subsets[index - 1] if index else ())))
        acts.append(
            dict(
                act=name,
                events=event_queue,
                normal=normal,
                elites=elites,
                boss=boss,
                ancient=ancient,
                counter=rng.request_count("up_front"),
            )
        )
        if index == len(pools_by_act) - 1 and ascension >= 10:
            acts[-1]["second_boss"] = rng.choice("up_front", [n for n in pools[3] if n != boss])
            acts[-1]["counter"] = rng.request_count("up_front")
    return dict(profile=f"native_{act}_hive_glory_all_unlocked_v1", subsets=subsets, acts=acts)


def validate(state):
    from game.headless.core.native_service import NativeRandomService
    from game.headless.generation.relics import populate

    if state.initialization is None:
        return
    if not getattr(state.rng, "native", False):
        raise ValueError("Fixture run cannot own native initialization.")
    rng = NativeRandomService(state.seed)
    populate(rng)
    if state.config is None:
        raise ValueError("Native initialization requires declared act settings.")
    expected = generate(rng, act=state.config.first_act, ascension=state.config.ascension)
    if state.initialization != expected:
        raise ValueError("Native initialization differs from its seed and declared inputs.")
    if state.rng.request_count("up_front") < rng.request_count("up_front"):
        raise ValueError("Native UpFront state precedes initialization.")
    progression = state.encounter_progression
    if progression is None:
        raise ValueError("Native initialization requires encounter progression.")
    from game.headless.encounters.progression import native_ids
    owners = [(a.act, a.encounter_progression, a.event_progression) for a in state.completed_acts]
    owners.append((state.config.act, progression, state.event_progression))
    for index, (name, encounters, events) in enumerate(owners):
        ids = native_ids(name)
        act = expected['acts'][index]
        if (name != act['act'] or encounters.normal_queue != [ids[n] for n in act['normal']]
                or encounters.elite_queue != [ids[n] for n in act['elites']]
                or encounters.boss != ids[act['boss']]
                or encounters.second_boss != (ids[act['second_boss']] if act.get('second_boss') else None)):
            raise ValueError('Encounter queues differ from native initialization.')
        if events is not None and events.queue != act['events']:
            raise ValueError('Event queue differs from native initialization.')
