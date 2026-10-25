"""How often does a PERFECT circuit fail the judges' 2,000-shot test (TV < 0.1)?  Draws 2,000 shots from the exact ideal
distribution (no circuit involved) for every odd composite N <= 63 and every coprime a >= 2, 300 trials each.
Run:  python noise_table.py      (about 1 minute; writes results/noise_floor_per_N.md)"""
import math
import os

import numpy as np

from test_shor import ideal_distribution, is_prime, true_order, tv

rng = np.random.default_rng(2026)
TRIALS, SHOTS = 300, 2000
rows = ["| N | bits | coprime a >= 2 | mean P(TV >= 0.1) over a | worst a (order) | worst P(fail) | worst mean TV |", "|---|---|---|---|---|---|---|"]
for N in [n for n in range(9, 64, 2) if not is_prime(n)]:
    stats = []
    for a in range(2, N):
        if math.gcd(a, N) == 1:
            P = ideal_distribution(N, a)
            tvs = [tv(rng.multinomial(SHOTS, P) / SHOTS, P) for _ in range(TRIALS)]
            stats.append((float(np.mean([t >= 0.1 for t in tvs])), a, true_order(N, a), float(np.mean(tvs))))
    w = max(stats)
    rows.append(f"| {N} | {N.bit_length()} | {len(stats)} | {np.mean([s[0] for s in stats]):.3f} | a={w[1]} (r={w[2]}) | {w[0]:.3f} | {max(s[3] for s in stats):.3f} |")
out = "\n".join(rows)
print(out)
here = os.path.dirname(os.path.abspath(__file__))
open(os.path.join(here, "results", "noise_floor_per_N.md"), "w").write(
    f"# Failure rate of a perfect circuit at {SHOTS} shots (TV < 0.1 test), {TRIALS} trials per (N, a)\n\n" + out + "\n")
