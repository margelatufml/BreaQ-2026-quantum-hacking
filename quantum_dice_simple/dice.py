"""Quantum Dice, minimal version (direction: the repeated batch). Does each request return fresh bits?

Run: python dice.py  -> self-checks, then the tuning and evaluation tables.
Simulation only: Qiskit samples with a pseudorandom generator, so these bits model a quantum
source and must not be used for passwords or keys.
"""
from collections import Counter

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
from scipy.stats import binomtest

BITS, REQUESTS = 1024, 50                                   # bits per request, requests per service instance
TUNING_SEEDS, EVAL_SEEDS = range(0, 20), range(1000, 1020)  # one service instance per seed

COIN = QuantumCircuit(1)
COIN.h(0)  # |0> -> (|0> + |1>)/sqrt(2): each measurement gives 0 or 1 with probability 1/2


def sample(n, rng):
    """n prepare-and-measure runs of the coin, in order, as a '0'/'1' string."""
    sv = Statevector(COIN)
    sv.seed(rng)  # a Generator continues its stream; the same int restarts it from the beginning
    return "".join(sv.sample_memory(n))


class Clean:
    def __init__(self, seed):
        self.rng = np.random.default_rng(seed)  # created once, kept for the whole service lifetime

    def request(self):
        return sample(BITS, self.rng)


class Faulty:
    def __init__(self, seed):
        self.seed = seed

    def request(self):
        return sample(BITS, self.seed)  # BUG: re-seeds with the same seed on every request


def frequency_alarm(bits):
    """Is the share of ones implausible for a fair coin? Exact two-sided binomial test, p < 0.01."""
    return binomtest(bits.count("1"), len(bits)).pvalue < 0.01


def replay_alarms(batches):
    """For each batch of one service, in order: is it an exact copy of an earlier batch?"""
    seen, alarms = set(), []
    for bits in batches:
        alarms.append(bits in seen)
        seen.add(bits)
    return alarms


def evaluate(seeds):
    """(frequency alarms, replay alarms) per service, and the request positions where replay missed a faulty batch."""
    table, missed = {}, Counter()
    for Service in (Clean, Faulty):
        freq = replay = 0
        for seed in seeds:
            service = Service(seed)
            batches = [service.request() for _ in range(REQUESTS)]
            alarms = replay_alarms(batches)
            freq += sum(map(frequency_alarm, batches))
            replay += sum(alarms)
            if Service is Faulty:
                missed.update(i for i, alarm in enumerate(alarms) if not alarm)
        table[Service.__name__] = (freq, replay)
    return table, missed


if __name__ == "__main__":
    clean, faulty = Clean(7), Faulty(7)
    first = clean.request()
    assert first == faulty.request()            # control: same seed, same first batch; only the seed lifecycle differs
    assert clean.request() != first             # clean: the next request is fresh
    assert faulty.request() == first            # faulty: the next request is a replay

    for name, seeds in (("Tuning", TUNING_SEEDS), ("Evaluation", EVAL_SEEDS)):
        table, missed = evaluate(seeds)
        n = len(seeds) * REQUESTS
        print(f"\n{name} set: seeds {seeds.start}-{seeds.stop - 1}, {n} batches of {BITS} bits per service")
        print("| Check | Clean: false alarms | Faulty: detections |\n|---|---|---|")
        for i, check in enumerate(("Frequency", "Replay")):
            print(f"| {check} | {table['Clean'][i]} / {n} | {table['Faulty'][i]} / {n} |")
        print("replay misses by request position:", dict(missed))
        assert table["Clean"][1] == 0 and table["Faulty"][1] == n - len(seeds) and missed == {0: len(seeds)}
