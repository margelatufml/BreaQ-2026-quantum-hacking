"""Numbers quoted in the README strategy section:  python bounds_check.py"""
import math

from scipy.optimize import brentq

from bb84 import EPS, h2, q_cp, q_hoeffding

print(f"root of 1-2h(Q): {brentq(lambda q: 1 - 2 * h2(q), 0.05, 0.2):.8f}")
print(f"2*log2(1/eps_PA): {2 * math.log2(1 / EPS):.5f}")
for k in (10_000, 20_000, 30_000):
    hoeff = math.sqrt(math.log(1 / EPS) / (2 * k))
    cp3 = q_cp(round(0.03 * k), k) - 0.03
    abort_h = brentq(lambda q: q_hoeffding(q * k, k) - 0.11, 0, 0.11)
    abort_c = brentq(lambda q: q_cp(q * k, k) - 0.11, 0, 0.11)
    print(f"k={k}: Hoeffding slack {hoeff:.5f} | CP slack at Q=3% {cp3:.4f} | CP bound at m=0 {q_cp(0, k):.5f} | "
          f"step-8 abort at Q_hat > {abort_h:.4f} (Hoeffding), {abort_c:.4f} (CP)")
