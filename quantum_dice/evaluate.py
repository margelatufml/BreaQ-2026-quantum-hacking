"""Layer 4 - evaluation on fresh data, plus the evidence files for the report (layer 5).

Seed schedule (documented, so every number can be reproduced):
  tuning set     : seeds 0-19      -> only used to confirm each check's false-alarm rate before evaluating
  evaluation set : seeds 1000-1019 -> fresh data, not looked at while choosing the thresholds
Each seed is one service instance that serves REQUESTS requests of BITS_PER_REQUEST bits.
Output: printed table, results/evaluation.csv, results/figure.png (all labelled "local simulation").
"""
import csv
from collections import Counter
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from auditor import audit_stream  # noqa: E402
from service import BITS_PER_REQUEST, CleanService, RepeatedBatchService  # noqa: E402
from source import sample_bits  # noqa: E402

REQUESTS = 50
TUNING_SEEDS = range(0, 20)
EVALUATION_SEEDS = range(1000, 1020)
CHECKS = ("frequency", "repetition", "replay")
OUT = Path(__file__).with_name("results")


class PredictableSeedService:
    """Extension only, not our chosen fault: a NEW seed on every request, but a guessable one
    (base seed + request number). Every batch is fresh, yet anyone who knows the scheme can recompute it."""

    def __init__(self, seed: int):
        self._seed, self._count = seed, 0

    def request(self, n: int = BITS_PER_REQUEST) -> np.ndarray:
        self._count += 1
        return sample_bits(n, self._seed + self._count)


def run(service_cls, seeds):
    """Every request of every instance, with the auditor's per-request alarms."""
    batches, alarms = [], []
    for seed in seeds:
        service = service_cls(seed)
        stream = [service.request() for _ in range(REQUESTS)]
        batches += stream
        alarms += audit_stream(stream)
    return batches, alarms


def main():
    OUT.mkdir(exist_ok=True)
    rows, evaluation = [], {}
    for phase, seeds in (("tuning", TUNING_SEEDS), ("evaluation", EVALUATION_SEEDS)):
        for label, cls in (("clean", CleanService), ("faulty", RepeatedBatchService)):
            batches, alarms = run(cls, seeds)
            if phase == "evaluation":
                evaluation[label] = (batches, alarms)
            for check in CHECKS:
                hits = sum(a[check] for a in alarms)
                rows.append({"phase": phase, "service": label, "check": check, "batches": len(alarms),
                             "alarms": hits, "rate": round(hits / len(alarms), 4)})

    with open(OUT / "evaluation.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print("LOCAL SIMULATION - alarms per check (batches of", BITS_PER_REQUEST, "bits)")
    print(f"{'phase':11}{'service':8}{'check':12}{'alarms':>14}")
    for r in rows:
        print(f"{r['phase']:11}{r['service']:8}{r['check']:12}{r['alarms']:>6} / {r['batches']:<5} ({r['rate']:.1%})")

    _, faulty_alarms = evaluation["faulty"]
    missed = Counter(i % REQUESTS for i, a in enumerate(faulty_alarms) if not a["replay"])
    print("replay misses on faulty data, by request position inside an instance:", dict(missed))

    # Extension: predictable but never repeated (someone who knows the seed scheme).
    seed = EVALUATION_SEEDS[0]
    service = PredictableSeedService(seed)
    stream = [service.request() for _ in range(REQUESTS)]
    ext_alarms = audit_stream(stream)
    predicted = sum(np.array_equal(b, sample_bits(BITS_PER_REQUEST, seed + k + 1)) for k, b in enumerate(stream))
    print(f"extension (predictable seeds): alarms {[sum(a[c] for a in ext_alarms) for c in CHECKS]} "
          f"for {CHECKS} over {REQUESTS} requests; an attacker who knows the scheme predicts "
          f"{predicted}/{REQUESTS} batches exactly")

    clean_b, clean_a = evaluation["clean"]
    faulty_b, _ = evaluation["faulty"]
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4))
    bins = np.linspace(0.44, 0.56, 25)
    left.hist([b.mean() for b in clean_b], bins=bins, alpha=0.6, label="clean")
    left.hist([b.mean() for b in faulty_b], bins=bins, alpha=0.6, label="faulty (repeated batch)")
    left.set(title="Fraction of ones per request (evaluation set)", xlabel="fraction of ones", ylabel="requests")
    left.legend()
    x = np.arange(len(CHECKS))
    for offset, (label, alarms) in ((-0.2, ("clean", clean_a)), (0.2, ("faulty", faulty_alarms))):
        right.bar(x + offset, [np.mean([a[c] for a in alarms]) for c in CHECKS], width=0.4, label=label)
    right.set(title="Alarm rate per check (evaluation set)", xticks=x, xticklabels=CHECKS, ylim=(0, 1.05),
              ylabel="share of requests with an alarm")
    right.legend()
    fig.suptitle("Quantum Dice audit - local simulation")
    fig.tight_layout()
    fig.savefig(OUT / "figure.png", dpi=120)
    print("wrote", OUT / "evaluation.csv", "and", OUT / "figure.png")


if __name__ == "__main__":
    main()
