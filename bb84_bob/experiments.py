"""Monte-Carlo experiments against the SIMULATED Alice.  python experiments.py [--trials 30]
Writes results/results.md (the tables below) and results/runs.csv (every single run)."""
import argparse
import csv
import math
import os
import time

import numpy as np

from alice_sim import AliceSession
from bb84 import BOUNDS, EPS, Q_ABORT, h2
from bob import LocalTransport, run_bob

ap = argparse.ArgumentParser()
ap.add_argument("--trials", type=int, default=30)
T = ap.parse_args().trials
N = 200_000
HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = []


def one(qber, eve, k, bound="cp", cascade="backtrack", seed=0, table=""):
    a = AliceSession(N=N, k=k, qber=qber, eve=eve, bound=bound, seed=seed)
    r = run_bob(LocalTransport(a), rng=np.random.default_rng(seed + 10_000), bound=bound, cascade_mode=cascade)
    row = dict(table=table, qber=qber, eve=eve, k=k, bound=bound, cascade=cascade, seed=seed, abort=r["abort"] or "",
               l=r.get("l", 0) if r["abort"] is None else 0, q_hat=r["q_hat"], q_u=r["q_u"], n=r.get("n", 0),
               leak_parity=r["ledger"]["learned"]["parity"], leak_hash=r["ledger"]["learned"]["hash"],
               attempts=r.get("attempts", 0), ok=bool(r.get("final", {}).get("success", False)))
    RUNS.append(row)
    return row


def agg(rows):
    ok = [r for r in rows if not r["abort"]]
    return dict(l=np.mean([r["l"] for r in ok]) if ok else float("nan"), sd=np.std([r["l"] for r in ok]) if ok else float("nan"),
                aborts=sum(1 for r in rows if r["abort"]) / len(rows), leak=np.mean([r["leak_parity"] for r in ok]) if ok else float("nan"),
                att=np.mean([r["attempts"] for r in ok]) if ok else float("nan"), fails=sum(1 for r in ok if not r["ok"]),
                q_u=np.mean([r["q_u"] for r in rows]), n=np.mean([r["n"] for r in ok]) if ok else float("nan"),
                q_hat=np.mean([r["q_hat"] for r in rows]))


out = [f"# Results (simulated Alice, N = {N}, {T} trials per cell, eps = eps_PA = 1e-10, Cascade 'backtrack' unless noted)\n"]
t0 = time.time()

# ---- Table 1: final key length and abort rate vs noise, Eve, k, bound ------------------------------------------------
out.append("## 1. Final key length l (bits, mean over non-aborted runs) and abort rate\n")
out.append("Cell = mean l / abort rate. Same random seeds for both bounds. 'noise' = qber of the channel, 'Eve' = intercept-resend fraction.\n")
out.append("| noise | Eve | bound | k=10000 | k=20000 | k=30000 |\n|---|---|---|---|---|---|")
for qber in (0.01, 0.02, 0.03, 0.04):
    for eve in (0.0, 0.01):
        for bound in ("cp", "hoeffding"):
            cells = []
            for k in (10_000, 20_000, 30_000):
                g = agg([one(qber, eve, k, bound, seed=s, table="1") for s in range(T)])
                cells.append(f"{g['l']:.0f} (sd {g['sd']:.0f}) / {g['aborts']:.0%}")
            out.append(f"| {qber:.0%} | {eve:.0%} | {bound} | " + " | ".join(cells) + " |")

# ---- Table 2: where the protocol aborts ----------------------------------------------------------------------------
out.append("\n## 2. Abort rate versus noise (k = 20000, Eve 0)\n")
out.append("'Step 8' = Q_u > 11%; 'l<=0' = Q_u below 11% but the key length formula gives no key; 'key < msg' = 0 < l but the key is shorter than the 8*len(message) bits the one-time pad needs (abort at step 15). The three reasons add up to the abort rate.\n")
out.append("| noise | bound | abort rate | of which step 8 | of which l<=0 | of which key < msg | mean Q_hat | mean l (non-aborted) |\n|---|---|---|---|---|---|---|---|")
for qber in (0.05, 0.06, 0.07, 0.08, 0.09, 0.095, 0.10, 0.11):
    for bound in ("cp", "hoeffding"):
        rows = [one(qber, 0.0, 20_000, bound, seed=s, table="2") for s in range(T)]
        g = agg(rows)
        s8 = sum(r["abort"].startswith("Q_u=") for r in rows) / T
        l0 = sum(r["abort"].startswith("l <= 0") for r in rows) / T
        km = sum(r["abort"].startswith("message step failed") for r in rows) / T
        out.append(f"| {qber:.1%} | {bound} | {g['aborts']:.0%} | {s8:.0%} | {l0:.0%} | {km:.0%} | {g['q_hat']:.4f} | {g['l']:.0f} |")

# ---- Table 3: Cascade variants ---------------------------------------------------------------------------------------
out.append("\n## 3. Cascade variants (k = 20000, Eve 0.5%, CP)\n")
out.append("'brief' = steps 9-11 literally (3 passes, equal blocks b = 0.73/Q_hat, no back-tracking); 'backtrack' = 3 passes, blocks b, 3b, 9b with back-tracking (default); 'backtrack_2x' = b, 2b, 4b. Leak = parity bits of the successful run set (all attempts).\n")
out.append("| noise | Cascade | mean attempts | mean parity bits | mean l | leak / (n h(Q_hat)) |\n|---|---|---|---|---|---|")
for qber in (0.01, 0.02, 0.03, 0.04):
    for casc in ("brief", "backtrack_2x", "backtrack"):
        g = agg([one(qber, 0.005, 20_000, "cp", casc, seed=s, table="3") for s in range(T)])
        out.append(f"| {qber:.0%} | {casc} | {g['att']:.2f} | {g['leak']:.0f} | {g['l']:.0f} | {g['leak'] / (g['n'] * h2(g['q_hat'])):.2f} |")

# ---- Table 4: best k -------------------------------------------------------------------------------------------------
out.append("\n## 4. Which k maximises the final key? (Eve 0.5%)\n")
out.append("Empirical = mean l over trials (sd of the mean about 1/sqrt(trials) of the sd in table 1). Analytic = expected l with m = Q k, f_EC measured in the runs of table 1 (CP f_EC, Hoeffding f_EC).\n")
KS = (3000, 5000, 7500, 10_000, 15_000, 20_000, 30_000)
out.append("| noise | bound | " + " | ".join(f"k={k}" for k in KS) + " | best empirical k | best empirical k in 10000-30000 | best analytic k |\n|---|---|" + "---|" * (len(KS) + 3))
for qber in (0.01, 0.02, 0.03, 0.04):
    for bound in ("cp", "hoeffding"):
        means = {k: agg([one(qber, 0.005, k, bound, seed=s, table="4") for s in range(T)])["l"] for k in KS}
        ref = agg([r for r in RUNS if r["table"] == "1" and r["qber"] == qber and r["bound"] == bound and r["k"] == 20_000])
        fec = ref["leak"] / (ref["n"] * h2(ref["q_hat"]))
        ns, q_true = N // 2, ref["q_hat"]

        def ana(k):
            n = ns - k
            qu = BOUNDS[bound](round(q_true * k), k, EPS)
            return -math.inf if qu > Q_ABORT else n - n * h2(qu) - fec * n * h2(q_true) - 40 - 2 * math.log2(1 / EPS)
        best_ana = max(range(500, 40_000, 250), key=ana)
        best = max(KS, key=means.get)
        best_in = max((k for k in KS if k >= 10_000), key=means.get)
        out.append(f"| {qber:.0%} | {bound} | " + " | ".join(f"{means[k]:.0f}" for k in KS) + f" | {best} | {best_in} | {best_ana} (l = {ana(best_ana):.0f}) |")

bad = [r for r in RUNS if not r["abort"] and not r["ok"]]
out.append(f"\nRuns: {len(RUNS)}; runs that finished without abort but whose message did not decrypt correctly: {len(bad)}. Wall time {time.time() - t0:.0f} s.")
os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
text = "\n".join(out)
open(os.path.join(HERE, "results", "results.md"), "w").write(text + "\n")
with open(os.path.join(HERE, "results", "runs.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(RUNS[0]))
    w.writeheader()
    w.writerows(RUNS)
print(text)
