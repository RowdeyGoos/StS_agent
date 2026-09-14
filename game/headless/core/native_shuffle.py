"""Pinned List.Sort tie ordering used before native card StableShuffle."""


def sort_cards(values):
    # .NET's introsort is not stable for equal model ID/upgrade pairs. Keeping its
    # tie permutation matters when two copies carry different enchantments.
    def key(card):
        return card.definition.definition_id, card.upgrade_level

    def swap(a, b):
        values[a], values[b] = values[b], values[a]

    def ordered_pair(a, b):
        if key(values[a]) > key(values[b]):
            swap(a, b)

    def down_heap(i, n, low):
        item = values[low + i - 1]
        while i <= n // 2:
            child = 2 * i
            if child < n and key(values[low + child - 1]) < key(values[low + child]):
                child += 1
            if key(item) >= key(values[low + child - 1]):
                break
            values[low + i - 1] = values[low + child - 1]
            i = child
        values[low + i - 1] = item

    def intro(low, high, depth):
        while high > low:
            size = high - low + 1
            if size <= 16:
                if size == 2:
                    ordered_pair(low, high)
                elif size == 3:
                    ordered_pair(low, high - 1)
                    ordered_pair(low, high)
                    ordered_pair(high - 1, high)
                else:
                    for i in range(low, high):
                        item = values[i + 1]
                        j = i
                        while j >= low and key(item) < key(values[j]):
                            values[j + 1] = values[j]
                            j -= 1
                        values[j + 1] = item
                return
            if depth == 0:
                for i in range(size // 2, 0, -1):
                    down_heap(i, size, low)
                for i in range(size, 1, -1):
                    swap(low, low + i - 1)
                    down_heap(1, i - 1, low)
                return
            depth -= 1
            middle = low + (high - low) // 2
            ordered_pair(low, middle)
            ordered_pair(low, high)
            ordered_pair(middle, high)
            pivot = key(values[middle])
            swap(middle, high - 1)
            left, right = low, high - 1
            while True:
                left += 1
                while key(values[left]) < pivot:
                    left += 1
                right -= 1
                while pivot < key(values[right]):
                    right -= 1
                if left >= right:
                    break
                swap(left, right)
            swap(left, high - 1)
            intro(left + 1, high, depth)
            high = left - 1

    if values:
        intro(0, len(values) - 1, 2 * len(values).bit_length())


def stable_shuffle(values, rng):
    sort_cards(values)
    rng.shuffle(values)
