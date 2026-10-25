"""Layer 2 - two versions of the dice service with the same interface: request(n) -> bits.

CleanService: one random generator for the whole service lifetime, so every request
continues the random stream and gets fresh bits.

RepeatedBatchService: the brief's "repeated batch" direction. MOCK SERVICE-LAYER BUG
(a classical defect, not a quantum effect): the service re-seeds the simulator with the
same fixed seed on every request, so every request replays exactly the same bits.
"""
import numpy as np

from source import sample_bits

BITS_PER_REQUEST = 1024


class CleanService:
    def __init__(self, seed: int):
        self._rng = np.random.default_rng(seed)  # created once, kept for the whole lifetime

    def request(self, n: int = BITS_PER_REQUEST) -> np.ndarray:
        return sample_bits(n, self._rng)  # continues the same random stream


class RepeatedBatchService:
    def __init__(self, seed: int):
        self._seed = seed

    def request(self, n: int = BITS_PER_REQUEST) -> np.ndarray:
        return sample_bits(n, self._seed)  # BUG: restarts from the same seed on every request


if __name__ == "__main__":
    clean, faulty = CleanService(seed=2026), RepeatedBatchService(seed=1234)
    c1, c2 = clean.request(), clean.request()
    f1, f2 = faulty.request(), faulty.request()
    assert not np.array_equal(c1, c2), "clean service must return fresh bits"
    assert np.array_equal(f1, f2), "faulty service replays the same batch"
    for name, a, b in (("clean", c1, c2), ("faulty", f1, f2)):
        print(f"{name:6} request 1: {''.join(map(str, a[:16]))}... ones={a.mean():.3f} | "
              f"request 2: {''.join(map(str, b[:16]))}... ones={b.mean():.3f} | identical={np.array_equal(a, b)}")
