"""Results table and histograms for N = 15 and N = 21 (every a coprime to N).
Run:  python make_results.py 1      Level 1 (about 10 s)
      python make_results.py 2      Level 2, Beauregard gates (about 15 minutes)
Writes results/results_L<level>.md, results/hist_L<level>_N<N>.png and results/results.md (concatenation of what exists).
2,000 shots per (N, a), fixed seeds.  'recovered r' = order_from_shots on the first 20 of those shots (what factor() does).
'true r' and 'ideal' come from test_shor.py (they use the true order; shor.py never does)."""
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import shor
from test_shor import hist_from_ys, ideal_distribution, true_order, tv

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")
SHOTS = 2000


def outcome(a, N, r):
    """What the classical post-processing does with the recovered order."""
    if r is None:
        return "no order found in 20 shots"
    if r % 2:
        return f"r = {r} odd, retry with another a"
    x = pow(a, r // 2, N)
    if x == N - 1:
        return f"a^(r/2) = -1 mod N, retry with another a"
    p = math.gcd(x - 1, N)
    return f"{p} x {N // p}"


def run(level):
    build = {1: shor.build_shor, 2: shor.build_shor_level2}[level]
    lines = [f"## Level {level} ({'permutation matrices' if level == 1 else 'Beauregard QFT adders'}), {SHOTS} shots per row\n"]
    os.makedirs(OUT, exist_ok=True)
    for N in (15, 21):
        n = N.bit_length()
        coprime = [a for a in range(2, N) if math.gcd(a, N) == 1]
        fig, axes = plt.subplots(math.ceil(len(coprime) / 3), 3, figsize=(13, 2.6 * math.ceil(len(coprime) / 3)), squeeze=False)
        qubits = build(N, coprime[0]).num_qubits
        lines += [f"### N = {N} ({qubits} qubits, t = {2 * n} counting qubits)\n",
                  "| a | true r | recovered r | shots TV vs ideal | top outcomes y (count) | factors from this a |", "|---|---|---|---|---|---|"]
        for k, a in enumerate(coprime):
            qc = build(N, a)
            ys = shor.run_shots(qc, SHOTS, seed=1000 * N + a)
            M = 2 ** (2 * n)
            ideal = ideal_distribution(N, a)
            dist = hist_from_ys(ys, M)
            d = tv(dist, ideal)
            r_true, r_rec = true_order(N, a), shor.order_from_shots(ys[:20], a, N)
            top = ", ".join(f"{y} ({c})" for y, c in sorted(((y, int(c)) for y, c in enumerate(np.bincount(ys, minlength=M)) if c), key=lambda t: -t[1])[:4])
            lines.append(f"| {a} | {r_true} | {r_rec} | {d:.3f} | {top} | {outcome(a, N, r_rec)} |")
            ax = axes[k // 3][k % 3]
            nz = np.nonzero(dist)[0]
            ax.bar(nz, dist[nz], width=M / 200, color="#3b6ea5", label="measured")
            ni = np.nonzero(ideal > 1e-4)[0]
            ax.plot(ni, ideal[ni], "o", ms=3, color="#d1603d", label="ideal")
            ax.set_title(f"N={N} a={a}  r={r_true}  TV={d:.3f}", fontsize=9)
            ax.set_xlim(-M * 0.01, M)
            ax.set_xlabel("y = int(count key, 2)", fontsize=8)
            ax.tick_params(labelsize=7)
            if k == 0:
                ax.legend(fontsize=7)
        for k in range(len(coprime), axes.size):
            axes[k // 3][k % 3].axis("off")
        fig.suptitle(f"Level {level}, N = {N}: counting-register histogram, {SHOTS} shots", fontsize=11)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, f"hist_L{level}_N{N}.png"), dpi=110)
        plt.close(fig)
        sh = [a for a in range(2, N) if math.gcd(a, N) > 1]
        lines += ["", f"a with gcd(a, {N}) > 1 (no circuit needed, the classical gcd step gives a factor): " +
                  ", ".join(f"{a} (gcd {math.gcd(a, N)})" for a in sh), ""]
    path = os.path.join(OUT, f"results_L{level}.md")
    open(path, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    for lv in (sys.argv[1:] or ["1"]):
        run(int(lv))
    parts = [open(os.path.join(OUT, f)).read() for f in ("results_L1.md", "results_L2.md") if os.path.exists(os.path.join(OUT, f))]
    open(os.path.join(OUT, "results.md"), "w").write("# Results: N = 15 and N = 21\n\nHistograms: `hist_L<level>_N<N>.png` in this folder.\n\n" + "\n".join(parts))
