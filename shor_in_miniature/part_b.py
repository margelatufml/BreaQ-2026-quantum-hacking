"""Part B arithmetic.  Prints every number used in PART_B.md.  Standard library only.  Run: python part_b.py

Inputs marked [src] were read in the cited paper's text or abstract (arXiv tool and pdftotext on the arXiv PDFs).
Inputs marked [own] are assumptions made by this team.  Nothing else is hard-coded.
"""
import math

DAY = 86400.0
P_TH = 0.01                        # [brief p.3] threshold ~ 1 %


# ----------------------------------------------------------------------------- the toy model (formula image on brief p.3)
def p_logical(p, d):
    """Logical error per logical qubit per cycle: 0.1 * (p / p_th)^((d+1)/2)."""
    return 0.1 * (p / P_TH) ** ((d + 1) / 2)


def min_distance(L, T, p, budget=0.1):
    """Smallest odd d with L * T * p_L(d) < budget."""
    d = 3
    while L * T * p_logical(p, d) >= budget:
        d += 2
    return d


def toy(L, seconds, p, cycle_s=1e-6):
    T = seconds / cycle_s
    d = min_distance(L, T, p)
    per_logical = 2 * d * d
    return T, d, per_logical, L * per_logical


def sci(x):
    return f"{x:.3g}"


print("=" * 78)
print("1. PUBLISHED ESTIMATES (all assume surface code on a 2D grid unless noted)")
print("=" * 78)
# [src] arXiv:1905.09749 Table 2 rows '(ours) 2019 (parallel)': 20 Mq, 0.31 d, 5.9 Mqd; '(1 thread)': 19 Mq, 0.36 d; '(1 factory)': 16 Mq, 6 d
# [src] arXiv:2505.15917 Sect. 3.2: 897,864 physical qubits, 12.07 h per shot, E(shots)=9.2 (Table 5), shot success 93.3 %, 4.96 days
# [src] arXiv:2602.11457v2 Table VI (1 us cycle, p=1e-3): 94 kq (<=1 yr, <=1 month), 135 kq (<=1 week), 381 kq (<=1 day); text: 139 kq / week, 400 kq / day
# [src] arXiv:2603.28846 (Google Quantum AI): ECC-256, <1200 logical / <90 M Toffoli or <1450 / <70 M; 18 or 23 min; primed 9 or 12 min; <500 kq
ge_q, ge_days, ge_vol = 20e6, 0.31, 5.9
print("Gidney+Ekera 2019 (arXiv:1905.09749), 28-factory row: 20 M qubits, 0.31 d = %.1f h, volume 5.9 Mqubit-days" % (0.31 * 24))
print("   other rows of their Table 2: 14 factories 19 M / 0.36 d; 1 factory 16 M / 6 d  (fewer factories -> fewer qubits, slower)")
cold, hot, comp = 1280 * 430, 131 * 1352, 7 * 18 * 1352
tot25 = cold + hot + comp
print(f"Gidney 2025 (arXiv:2505.15917): hot patch 2(25+1)^2 = {2 * 26 ** 2}; cold storage 1280*430 = {cold:,}; hot 131*1352 = {hot:,};"
      f" compute region 7*18*1352 = {comp:,}")
print(f"   total = {tot25:,} (paper: 897864, reported as '<1 million' for slack)")
assert tot25 == 897_864
shot_h, E_shots, p_ok = 12.07, 9.2, 0.933
days25 = shot_h * E_shots / 24 / p_ok
print(f"   runtime = 12.07 h * 9.2 shots / 24 / 0.933 = {days25:.2f} days (paper 4.96, 'less than a week')")
vol25 = tot25 * days25 / 1e6
print(f"   volume = {tot25:,} * {days25:.2f} d = {vol25:.2f} Mqubit-days")
print("Pinnacle 2026 (arXiv:2602.11457v2, Table VI, 1 us, p=1e-3): 94 kq (<=1 month), 135 kq (<=1 week), 381 kq (<=1 day)")
print("   -> the paper DOES state runtimes (the brief says 'not stated'); needs non-local qubit connectivity; simulation, not hardware")
print("Google 2026 (arXiv:2603.28846): ECC-256 (not RSA); 18-23 min, or 9-12 min once 'primed'; <500,000 qubits; circuits withheld (zero-knowledge proof)")

print("\n--- 1b. why the estimates trade qubits against runtime")
print(f"qubit ratio 2019 -> 2025: 20e6 / {tot25:,} = {ge_q / tot25:.1f}x fewer")
print(f"runtime ratio: {days25:.2f} d / 0.31 d = {days25 / ge_days:.1f}x longer   (vs the 8 h headline: {days25 * 24 / 8:.1f}x; headline '<1 week' vs 8 h: {7 * 24 / 8:.0f}x, the brief's 'about 20x')")
print(f"volume ratio: {ge_vol} / {vol25:.2f} = {ge_vol / vol25:.2f}x   -> the 20x qubit cut is mostly time bought with qubits, true algorithmic gain ~1.3x in volume")
print(f"Pinnacle at fixed hardware: 94 kq * 30 d = {94e3 * 30 / 1e6:.2f} Mqd;  135 kq * 7 d = {135e3 * 7 / 1e6:.2f};  381 kq * 1 d = {381e3 / 1e6:.2f}"
      "  (the same machine family, runtime knob: 4x qubits buys 30x speed)")
print(f"Pinnacle vs Gidney 2025: {tot25 / 135e3:.1f}x fewer qubits at about one week")

print()
print("=" * 78)
print("2. TOY SURFACE-CODE MODEL  p_L = 0.1 (p/p_th)^((d+1)/2), p_th = 1 %, 2 d^2 physical per logical, need L*T*p_L < 0.1")
print("=" * 78)
T, d, ppl, tot = toy(1500, 5 * DAY, 1e-3)
print(f"Judges' worked example: L = 1500, 5 days at 1 us: T = 5 * 86400 / 1e-6 = {T:.3e} cycles")
print(f"   L*T = {1500 * T:.3e}; need p_L < 0.1 / (L*T) = {0.1 / (1500 * T):.3e}")
for dd in (23, 25, 27, 29, 31):
    pl = p_logical(1e-3, dd)
    v = 1500 * T * pl
    print(f"   d = {dd}: p_L = 0.1 * (0.1)^{(dd + 1) // 2} = {pl:.1e};  L*T*p_L = {v:.3g}  {'< 0.1 OK' if v < 0.1 else '>= 0.1 too large'}")
print(f"   smallest odd d = {d};  2 d^2 = {ppl:,} physical per logical;  total = 1500 * {ppl:,} = {tot:,} (about {tot / 1e6:.2f} million)")
assert d == 29 and ppl == 1682 and tot == 2_523_000 and abs(T - 4.32e11) < 1e6
print(f"   (with Gidney-Ekera's 2(d+1)^2 the same d gives {2 * 30 ** 2:,} per logical, {1500 * 2 * 30 ** 2:,} total: +{(2 * 30 ** 2 / ppl - 1) * 100:.0f} %)")
print(f"   if T is forgotten (L*p_L < 0.1 only): d = {min_distance(1500, 1, 1e-3)}, total = {1500 * 2 * min_distance(1500, 1, 1e-3) ** 2:,}  -> wrong by a factor {tot / (1500 * 2 * min_distance(1500, 1, 1e-3) ** 2):.0f}")

print("\n--- 2b. sensitivity (L = 1500, 5 days, 1 us unless varied)")
print("   p        d    2d^2   total")
for p in (5e-4, 1e-3, 2e-3, 3e-3, 5e-3):
    _, dd, pp_, tt = toy(1500, 5 * DAY, p)
    print(f"   {p * 100:.2f} %  {dd:3d}  {pp_:6d}  {sci(tt)}")
print("   runtime (p = 0.1 %):")
for name, s in (("8 hours", 8 * 3600), ("5 days", 5 * DAY), ("1 year", 365 * DAY)):
    _, dd, pp_, tt = toy(1500, s, 1e-3)
    print(f"   {name:8s} d = {dd}  total = {sci(tt)}")
print("   -> total depends on T only through d, which grows with log(L*T): 1 year costs only "
      f"{toy(1500, 365 * DAY, 1e-3)[3] / tot:.2f}x the 5-day total.  Time does NOT buy qubits in the toy model; it buys fewer factories/parallelism.")

print("\n--- 2c. toy model on Gidney 2025's own inputs")
L25 = 1399                                           # [src] Table 5, n = 2048 row: logical qubits
T25, d25, ppl25, tot25_toy = toy(L25, days25 * DAY, 1e-3)
print(f"   L = {L25} logical (Table 5), runtime {days25:.2f} d = {days25 * DAY / 1e-6:.3e} cycles at 1 us, p = 0.1 %: d = {d25}, 2d^2 = {ppl25:,}, total = {tot25_toy:,}")
print(f"   toy / paper = {tot25_toy:,} / {tot25:,} = {tot25_toy / tot25:.1f}x  (same order of magnitude, 10^6)")
print(f"   Gidney's own per-patch fit: p_L(d=25) = 1e-15; the toy gives p_L(25) = {p_logical(1e-3, 25):.0e} -> toy is 10x more pessimistic per patch")
print(f"   what the toy leaves out and Gidney exploits: cold storage {430} vs {1352} physical per logical = {1352 / 430:.1f}x denser (yoked surface codes),")
print(f"   idle qubits all hot would be (1280 + 131 + 126) * 1352 = {(1280 + 131 + 7 * 18) * 1352:,} instead of {tot25:,}")
print("   toy also ignores magic-state factories (cultivation makes them small: six 3x4 patches in Gidney 2025) and routing")
l19 = 3 * 2048 + 0.002 * 2048 * math.log2(2048)      # [src] arXiv:1905.09749 abstract: 3n + 0.002 n lg n logical qubits
print(f"   approximate residue arithmetic: {L25} logical qubits vs 3n + 0.002 n lg n = {l19:,.0f} in 2019: {l19 / L25:.1f}x fewer")

print()
print("=" * 78)
print("3. TODAY'S HARDWARE vs THE REQUIREMENT")
print("=" * 78)
# [src] arXiv:2511.05465 Helios abstract: 98 qubits; infidelity 2.5e-5 (1q), 7.9e-4 (2q), 4.8e-4 (SPAM), averaged over all zones
# [src] arXiv:2408.13687 Willow abstract: distance-7 memory on 101 qubits, Lambda = 2.14 +- 0.02, 0.143 % error per cycle, cycle time 1.1 us,
#       decoder latency 63 us (distance 5, real time)
# [own, NOT re-verified] largest announced arrays about 1,100 qubits (IBM Condor 1,121, 2023, from public announcements)
helios_q, helios_e2 = 98, 7.9e-4
willow_pl, willow_lam = 1.43e-3, 2.14
for name, need in (("Gidney 2025 (897,864)", tot25), ("Pinnacle (<100,000)", 1e5), ("toy example (2.52 M)", tot)):
    print(f"   {name:24s} / Helios 98 qubits   = {need / helios_q:9.0f}x   ;  / 1,121 qubits (unverified) = {need / 1121:7.0f}x")
# [src] arXiv:2403.12021 (Nature 647, 60-67, 2025) abstract: tweezer array with over 6,100 trapped atoms (qubit count and coherence only, no entangling-gate error at that scale)
tw_q = 6100
print(f"   largest verified array (6,100 atomic qubits, 2403.12021): Gidney 2025 {tot25 / tw_q:.0f}x ; Pinnacle 1e5 {1e5 / tw_q:.0f}x ; toy {tot / tw_q:.0f}x  (qubit count only, no gate error at that scale)")
# [own assumption] slow-clock machines (ions, atoms): illustrative 1 ms cycle instead of the assumed 1 us; arXiv:2603.28846 abstract only draws the fast-clock / slow-clock distinction
print(f"   clock: if a slow-clock machine ran a 1 ms cycle (1000x the assumed 1 us, illustrative), Gidney's 4.96 days become {4.96 * 1000 / 365.25:.1f} years")
print(f"   two-qubit error: Helios {helios_e2:.1e} vs assumed 1e-3 -> already {1e-3 / helios_e2:.2f}x better than the assumption (on 98 qubits, not 1e6)")
print(f"   so the error-rate gap is ~1x on small devices; the gap is SCALE: qubits (about 10^3 - 10^4 x), and error-correction quality at scale")
need_pl = 0.1 / (1500 * 4.32e11)
print(f"   logical error needed per qubit per cycle (toy example): {need_pl:.2e};  best measured logical memory (Willow d=7): {willow_pl:.2e}"
      f"  -> gap {willow_pl / need_pl:.1e}x")
d_w = 7
while 1500 * 4.32e11 * willow_pl / willow_lam ** ((d_w - 7) / 2) >= 0.1:
    d_w += 2
print(f"   if suppression stayed at Willow's Lambda = {willow_lam} (toy assumes p_th/p = 10): d = {d_w}, 2 d^2 = {2 * d_w ** 2:,} per logical,"
      f" total {1500 * 2 * d_w ** 2:,} = {1500 * 2 * d_w ** 2 / tot:.1f}x the toy's {tot:,}")
print(f"   logical qubits: need {L25}; Willow shows 1 logical memory qubit (one patch) -> {L25}x ; decoder: {63}/{10} = {63 / 10:.1f}x slower than the assumed 10 us reaction time (63 us at d=5)")
print("   (do NOT multiply the qubit gap by the error gap: p/p_th sets d, which sets the qubits per logical -- they are coupled)")

print()
print("=" * 78)
print("4. TIMELINE (explicit assumptions; a what-if, not a forecast)")
print("=" * 78)
# [src] arXiv:1905.09749 Table 2: Fowler et al. 2012: 1,000 Mqubits, 1.1 days at 1 us, 0.1 %
fowler_q = 1000e6
req = 94e3                                           # Pinnacle 1 month
alg_halvings = math.log2(fowler_q / req)
print(f"   Requirement history: 2012 Fowler et al. 1,000,000,000 qubits -> 2019 20,000,000 -> 2025 897,864 -> 2026 94,000 (month) / 135,000 (week)")
print(f"   2012 -> 2026: {fowler_q / req:,.0f}x fewer = {alg_halvings:.1f} halvings in 14 years: the requirement halved every {14 / alg_halvings:.2f} years, with the same 0.1 % error assumption")
H_hist = 14 / alg_halvings
target = tot25
print("   Assumptions [own]: (A1) 2D-grid hardware keeps 0.1 % error and 1 us cycle while it scales (optimistic);")
print("   (A2) physical qubit count doubles every D years; (A3) the requirement keeps halving every H years (H = inf: algorithms stop improving);")
print("   (A4) start = 98 qubits (Helios, verified) or ~1,121 qubits (largest announced array, not re-verified, no 2q error published at that scale)")
print("   years to close the gap = log2(requirement / start) / (1/D + 1/H);  calendar year = 2026 + that")
for q0 in (98, 1121):
    print(f"   start {q0} qubits: gap {target / q0:,.0f}x = {math.log2(target / q0):.1f} doublings")
print("            start 98            start 1,121")
print("   D      H=inf    H=3 y      H=inf    H=3 y")
fast = []
for D in (1, 2, 3):
    row = []
    for q0 in (98, 1121):
        for H in (math.inf, 3):
            yrs = math.log2(target / q0) / (1 / D + (0 if H == math.inf else 1 / H))
            row.append(f"{2026 + yrs:7.0f}")
            fast.append(2026 + yrs)
    print(f"   {D} y   " + "  ".join(row))
print(f"   history: the requirement halved every {H_hist:.1f} years since 2012; extrapolating that is not credible, hence H = inf or 3 y")

print("\n--- 4b. organisational consequence: harvest now, decrypt later (Mosca inequality: act if X + Y > Z)")
print("   X = years data must stay secret, Y = years to migrate, Z = years until a machine exists; [own] X = 10, Y = 7 (large organisation)")
X, Y = 10, 7
print(f"   X + Y = {X + Y} years; migration is already late if Z <= {X + Y}, i.e. if a machine arrives before {2026 + X + Y}")
print(f"   {sum(f < 2026 + X + Y for f in fast)} of the {len(fast)} scenarios above arrive before {2026 + X + Y}; earliest {min(fast):.0f}, latest {max(fast):.0f}")
print("   key exchange (ML-KEM, NIST FIPS 203) must move first, because recorded traffic can be decrypted later;")
print("   signatures (ML-DSA, FIPS 204) matter at forgery time.  Google's 2026 paper itself urges migration 'without delay' (arXiv:2603.28846 abstract).")
