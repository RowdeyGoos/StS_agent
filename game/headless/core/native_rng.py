"""Pinned 0.107.1 MegaRandom and Rng arithmetic, with owned private state.

The engine uses xoshiro256** seeded by SplitMix64, not System.Random. Public
Rng float draws round the double result to binary32. No process-global state.
"""

from math import log, pi, sin, sqrt
from struct import pack, unpack

MASK = (1 << 64) - 1
SCHEMA = "sts2_megarandom_v1"


def single(value):
    return unpack("<f", pack("<f", value))[0]


def deterministic_hash(value):
    """StringHelper's unchecked UTF-16 hash, returned as uint32."""
    if not isinstance(value, str):
        raise ValueError("Native seed text must be a string.")
    raw = value.encode("utf-16-le", errors="surrogatepass")
    chars = [int.from_bytes(raw[i : i + 2], "little") for i in range(0, len(raw), 2)]
    a = b = 352654597
    for i in range(0, len(chars), 2):
        a = ((a * 33) ^ chars[i]) & 0xFFFFFFFF
        if i + 1 < len(chars):
            b = ((b * 33) ^ chars[i + 1]) & 0xFFFFFFFF
    return (a + b * 1566083941) & 0xFFFFFFFF


def rotate(value, count):
    return ((value << count) | (value >> (64 - count))) & MASK


class NativeRng:
    def __init__(self, seed=0):
        if type(seed) is not int or not 0 <= seed <= 0xFFFFFFFF:
            raise ValueError("Rng seed must be uint32.")
        self.seed = seed
        self.counter = 0
        self.draws = 0
        self.words = []
        value = seed
        for _ in range(4):
            value = (value + 0x9E3779B97F4A7C15) & MASK
            word = value
            word = ((word ^ (word >> 30)) * 0xBF58476D1CE4E5B9) & MASK
            word = ((word ^ (word >> 27)) * 0x94D049BB133111EB) & MASK
            self.words.append(word ^ (word >> 31))

    def _next(self):
        a, b, c, d = self.words
        result = (rotate((b * 5) & MASK, 7) * 9) & MASK
        t = (b << 17) & MASK
        c ^= a
        d ^= b
        b ^= c
        a ^= d
        c ^= t
        d = rotate(d, 45)
        self.words = [a, b, c, d]
        self.draws += 1
        return result

    def _double(self):
        return (self._next() >> 11) * (1.0 / (1 << 53))

    def next_double(self, low=0.0, high=1.0):
        if low > high:
            raise ValueError("Invalid double range.")
        self.counter += 1
        return self._double() * (high - low) + low

    def next_float(self, low=0.0, high=1.0):
        low, high = single(low), single(high)
        if low > high:
            raise ValueError("Invalid float range.")
        self.counter += 1
        return single(self._double() * single(high - low) + low)

    def random(self):
        return self.next_float()

    def randrange(self, start, stop=None):
        if stop is None:
            start, stop = 0, start
        if type(start) is not int or type(stop) is not int or start >= stop:
            raise ValueError("Invalid integer range.")
        self.counter += 1
        return start + int(self._double() * (stop - start))

    def randint(self, low, high):
        return self.randrange(low, high + 1)

    def next_bool(self):
        return self.randrange(2) == 0

    def choice(self, values):
        if not values:
            raise ValueError("No eligible random choices.")
        return values[self.randrange(len(values))]

    def shuffle(self, values):
        for i in range(len(values) - 1, 0, -1):
            j = self.randrange(i + 1)
            values[i], values[j] = values[j], values[i]

    def sample(self, values, count):
        if type(count) is not int or not 0 <= count <= len(values):
            raise ValueError("Invalid sample count.")
        result = list(values)
        self.shuffle(result)
        return result[:count]

    def uniform(self, low, high):
        return self.next_float(low, high)

    def gaussian_int(self, mean, stddev, low, high):
        # Each Gaussian attempt consumes two counted native double draws.
        while True:
            x, y = 1 - self.next_double(), 1 - self.next_double()
            value = round(mean + stddev * sqrt(-2 * log(x)) * sin(2 * pi * y))
            if low <= value <= high:
                return value

    def getstate(self):
        return {
            "schema": SCHEMA,
            "seed": self.seed,
            "counter": self.counter,
            "draws": self.draws,
            "words": list(self.words),
        }

    def setstate(self, data):
        if (
            not isinstance(data, dict)
            or set(data) != {"schema", "seed", "counter", "draws", "words"}
            or data["schema"] != SCHEMA
        ):
            raise ValueError("Invalid native RNG snapshot.")
        if type(data["seed"]) is not int or not 0 <= data["seed"] <= 0xFFFFFFFF:
            raise ValueError("Invalid native RNG seed.")
        if (
            any(type(data[k]) is not int or data[k] < 0 for k in ("counter", "draws"))
            or data["counter"] != data["draws"]
        ):
            raise ValueError("Invalid native RNG counters.")
        words = data["words"]
        if (
            not isinstance(words, list)
            or len(words) != 4
            or any(type(w) is not int or not 0 <= w <= MASK for w in words)
            or not any(words)
        ):
            raise ValueError("Invalid xoshiro state.")
        self.seed, self.counter, self.draws, self.words = (
            data["seed"],
            data["counter"],
            data["draws"],
            list(words),
        )
