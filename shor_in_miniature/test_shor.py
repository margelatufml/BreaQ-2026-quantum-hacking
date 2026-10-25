"""Self-check for shor.py.  Plain asserts.  Run:  python test_shor.py          (about 10 minutes)
                                       python test_shor.py --full   (adds every a for N=21 at Level 2 and the 6-bit semiclassical run, about 1 hour)

TEST-ONLY code lives here: the ideal distribution below uses the true order r (computed classically).  shor.py never does.

Sections
  A  QFT bit-order convention
  B  Level-2 arithmetic blocks against classical arithmetic, every input
  C  Level 1: distribution test for every 4-, 5-bit (and informationally 6-bit) odd composite N and every coprime a
  D  Level 2 distribution test for (15,7) and (21,2) (and more a for N = 9, 15)
  E  semiclassical (recycled control) qubit counts and distribution
  F  factor(N) for every odd composite N up to 63 (Level 1), Level 2 for 15 and 21
  G  static and structural checks that build_shor does not use the order
"""
import ast
import inspect
import math
import random
import sys
import time
from collections import Counter

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import QFTGate
from qiskit.quantum_info import Operator
from qiskit_aer import AerSimulator

import shor
from shor import (build_shor, build_shor_level2, build_shor_semiclassical, cmult_circ, cu_circ, factor, iqft_circuit,
                  order_from_shots, phi_add, phi_add_mod, qft_circuit, run_shots)

FULL = "--full" in sys.argv
SIM = AerSimulator(method="statevector")
T0 = time.time()


def say(msg):
    print(f"[{time.time() - T0:6.0f}s] {msg}", flush=True)


# ----------------------------------------------------------------------------- test-only helpers (they know r)

def is_prime(N):
    return N > 1 and all(N % p for p in range(2, math.isqrt(N) + 1))


def odd_composites(bits):
    return [N for N in range(2 ** (bits - 1), 2 ** bits) if N % 2 and not is_prime(N)]


def true_order(N, a):
    r, x = 1, a % N
    while x != 1:
        x, r = x * a % N, r + 1
    return r


def ideal_distribution(N, a):
    """Textbook P(y) = (1/r) sum_{s<r} | (1/2^t) sum_{x<2^t} exp(2 pi i x (s/r - y/2^t)) |^2, y = 0..2^t-1, t = 2n.
    The inner sum over x is a DFT, evaluated with numpy's FFT (checked against the literal double sum below)."""
    t = 2 * N.bit_length(); M = 2 ** t; r = true_order(N, a)
    x = np.arange(M)
    P = sum(np.abs(np.fft.fft(np.exp(2j * np.pi * x * s / r)) / M) ** 2 for s in range(r))
    return P / r


def ideal_literal(N, a, y):
    """The same formula evaluated literally for one y (slow, used only to validate ideal_distribution)."""
    t = 2 * N.bit_length(); M = 2 ** t; r = true_order(N, a)
    x = np.arange(M)
    return sum(abs(np.exp(2j * np.pi * x * (s / r - y / M)).sum() / M) ** 2 for s in range(r)) / r


def tv(p, q):
    return 0.5 * float(np.abs(np.asarray(p) - np.asarray(q)).sum())


def hist_from_ys(ys, M):
    return np.bincount(ys, minlength=M) / len(ys)


def exact_circuit_distribution(qc_nomeasure, t):
    """Exact probabilities of the counting qubits 0..t-1 from the circuit statevector (no shot noise, never uses r).
    probs[idx]: bit q of idx is counting qubit q = bit q of y, so probs[y] directly."""
    c = qc_nomeasure.copy()
    c.save_probabilities(list(range(t)), label="p")
    return np.asarray(SIM.run(c, shots=1).result().data()["p"])


def run_basis(circuits, shots=1):
    """Run many circuits (each ends with measurements); return a list of bitstring->count dicts."""
    res = SIM.run(circuits, shots=shots).result()
    return [res.get_counts(i) for i in range(len(circuits))]


def basis_circuit(nq, value_bits, body):
    """Circuit on nq qubits with qubits set by value_bits ({qubit: 0/1}), then body (a QuantumCircuit), then measure all."""
    qc = QuantumCircuit(nq, nq)
    for q, v in value_bits.items():
        if v:
            qc.x(q)
    qc.compose(body, inplace=True)
    qc.measure(range(nq), range(nq))
    return qc


def read(counts, qubits):
    """Single-shot result as {qubit: bit}: counts has exactly one key; key is MSB left."""
    (key,) = counts
    key = key[::-1]
    return [int(key[q]) for q in qubits]


def to_int(bits):
    return sum(b << i for i, b in enumerate(bits))


# ----------------------------------------------------------------------------- A: QFT convention

def test_qft():
    m = 4; M = 2 ** m
    U = Operator(qft_circuit(m)).data
    rev = lambda k: int(format(k, f"0{m}b")[::-1], 2)
    D = np.array([[np.exp(2j * np.pi * x * rev(k) / M) for x in range(M)] for k in range(M)]) / np.sqrt(M)
    assert np.allclose(U, D), "qft_circuit is not the bit-reversed DFT"
    assert np.allclose(Operator(iqft_circuit(m)).data, U.conj().T)
    # and it equals Qiskit's own QFT followed by its swap layer (QFTGate includes the swaps)
    sw = QuantumCircuit(m)
    for i in range(m // 2):
        sw.swap(i, m - 1 - i)
    assert np.allclose(Operator(QFTGate(m)).data, Operator(sw).data @ U) or np.allclose(Operator(QFTGate(m)).data, U @ Operator(sw).data)
    say("A ok: qft_circuit is the DFT with output bit reversal (equals Qiskit QFTGate up to its swap layer)")


# ----------------------------------------------------------------------------- B: Level-2 arithmetic blocks

def test_phi_add():
    """phi_add: QFT, add constant c (optionally controlled by 0, 1, 2 qubits, add or subtract), IQFT == classical (b +- c) mod 2^m."""
    m = 5; M = 2 ** m
    circuits, expect = [], []
    for nctrl in (0, 1, 2):
        for sign in (1, -1):
            for ctrl_val in range(2 ** nctrl):
                for c in range(0, M + 3):          # includes c >= 2^m (reduced mod 2^m)
                    for b in range(M):
                        body = QuantumCircuit(m + nctrl)
                        reg = list(range(m)); ctrls = list(range(m, m + nctrl))
                        body.compose(qft_circuit(m), reg, inplace=True)
                        phi_add(body, reg, c, ctrls, sign)
                        body.compose(iqft_circuit(m), reg, inplace=True)
                        vals = {q: (b >> q) & 1 for q in reg}
                        vals.update({ctrls[k]: (ctrl_val >> k) & 1 for k in range(nctrl)})
                        circuits.append(basis_circuit(m + nctrl, vals, body))
                        active = ctrl_val == 2 ** nctrl - 1
                        expect.append((b + sign * c) % M if active else b)
    for counts, want in zip(run_basis(circuits), expect):
        assert to_int(read(counts, range(m))) == want
    say(f"B1 ok: phi_add == classical (b +- c) mod 2^{m}, {len(circuits)} inputs, 0/1/2 controls")


def test_phi_add_mod(N):
    """phi_add_mod: for every a < N, b < N, both controls 0/1: b -> (a + b) mod N if both controls are 1, ancilla returns to 0."""
    n = N.bit_length(); m = n + 1
    circuits, expect = [], []
    for a in range(N):
        for b in range(N):
            for cv in range(4):
                nq = m + 1 + 2
                reg, anc, ctrls = list(range(m)), m, [m + 1, m + 2]
                body = QuantumCircuit(nq)
                body.compose(qft_circuit(m), reg, inplace=True)
                phi_add_mod(body, reg, anc, a, N, ctrls)
                body.compose(iqft_circuit(m), reg, inplace=True)
                vals = {q: (b >> q) & 1 for q in reg}
                vals.update({ctrls[0]: cv & 1, ctrls[1]: cv >> 1})
                circuits.append(basis_circuit(nq, vals, body))
                expect.append((a + b) % N if cv == 3 else b)
    for counts, want in zip(run_basis(circuits), expect):
        bits = read(counts, range(m + 3))
        assert to_int(bits[:m]) == want and bits[m] == 0
    say(f"B2 ok: phi_add_mod == classical (a+b) mod {N}, {len(circuits)} inputs, ancilla clean")


def test_cmult_and_cu(N, a_list, b_list_per_x=None):
    """cmult: (b + a x) mod N for every x < N and every b < N (a few a); cu: |c>|x>|0> -> |c>|a^c x mod N>|0> for every x < N, c, and
    EVERY a coprime to N in a_list.  All other qubits must end unchanged / clean."""
    n = N.bit_length(); nq = 2 * n + 3
    x_q, b_q = list(range(1, n + 1)), list(range(n + 1, 2 * n + 2))
    circuits, expect = [], []
    for a in a_list:
        body = cmult_circ(n, a, N)
        for x in range(N):
            for b in (range(N) if b_list_per_x is None else b_list_per_x):
                for c in (0, 1):
                    vals = {0: c}
                    vals.update({x_q[i]: (x >> i) & 1 for i in range(n)}); vals.update({b_q[i]: (b >> i) & 1 for i in range(n + 1)})
                    circuits.append(basis_circuit(nq, vals, body))
                    expect.append(("cmult", c, x, (b + a * x) % N if c else b))
    for counts, (kind, c, x, want) in zip(run_basis(circuits), expect):
        bits = read(counts, range(nq))
        assert bits[0] == c and to_int(bits[1:n + 1]) == x and to_int(bits[n + 1:2 * n + 2]) == want and bits[-1] == 0
    n1 = len(circuits)
    circuits, expect = [], []
    for a in a_list:
        body = cu_circ(n, a, N)
        for x in range(N):
            for c in (0, 1):
                vals = {0: c}; vals.update({x_q[i]: (x >> i) & 1 for i in range(n)})
                circuits.append(basis_circuit(nq, vals, body))
                expect.append((c, (a * x) % N if c else x))
    for counts, (c, want) in zip(run_basis(circuits), expect):
        bits = read(counts, range(nq))
        assert bits[0] == c and to_int(bits[1:n + 1]) == want and to_int(bits[n + 1:]) == 0, (N, c, want, bits)
    say(f"B3 ok: N={N}: CMULT {n1} inputs, controlled-U_a {len(circuits)} inputs ({len(a_list)} values of a), work/accumulator/ancilla clean")


# ----------------------------------------------------------------------------- C, D: distribution tests

def shot_tv(qc, ideal, shots=2000, seed=7):
    return tv(hist_from_ys(run_shots(qc, shots, seed=seed), len(ideal)), ideal)


def test_ideal_formula():
    for N, a in ((15, 7), (21, 2)):
        P = ideal_distribution(N, a)
        assert abs(P.sum() - 1) < 1e-12
        for y in range(0, len(P), 37):
            assert abs(P[y] - ideal_literal(N, a, y)) < 1e-12
    P = ideal_distribution(15, 7)
    assert all(abs(P[y] - 0.25) < 1e-12 for y in (0, 64, 128, 192))   # r = 4: four exact peaks at s * 256 / 4
    say("C0 ok: FFT ideal distribution == literal textbook sum; (15,7) has four peaks of 0.25 at y = 0, 64, 128, 192")


def test_level1_distribution():
    worst_exact, worst_shot, rows, fails = 0.0, 0.0, [], []
    for bits in (4, 5, 6):
        for N in odd_composites(bits):
            for a in range(1, N):
                if math.gcd(a, N) != 1:
                    continue
                t = 2 * bits
                ideal = ideal_distribution(N, a)
                qc = build_shor(N, a, measure=False)
                assert qc.num_qubits == 3 * bits
                ex = tv(exact_circuit_distribution(qc, t), ideal)
                assert ex < 1e-9, (N, a, ex)
                worst_exact = max(worst_exact, ex)
                if bits <= 5:          # judge-like 2,000-shot test (6-bit: informational below)
                    s = shot_tv(build_shor(N, a), ideal)
                    rows.append((N, a, true_order(N, a), s))
                    worst_shot = max(worst_shot, s)
                    if s >= 0.1:
                        fails.append((N, a, true_order(N, a), s))
        say(f"C ok: all {bits}-bit odd composites {odd_composites(bits)}: circuit statevector == ideal (max TV so far {worst_exact:.1e})")
    # The shot test can fail for a perfect circuit when the ideal spreads over many y (large r): see README.  Fixed seed => deterministic.
    say(f"C: {len(rows)} (N,a) cases with 2000 shots, worst shot TV {worst_shot:.3f}; cases with TV >= 0.1: {fails}")
    assert all(r <= 20 for _, _, r, _ in fails), "only large-order cases may exceed 0.1 through shot noise"
    return rows, fails


def test_noise_floor(trials=400):
    """Finite-shot noise floor: 2,000 shots drawn from the EXACT ideal distribution (a perfect circuit) have TV > 0 against it.
    For large orders the ideal spreads over many y, so a perfect circuit can fail TV < 0.1 by chance.  Informational plus sanity asserts."""
    rng = np.random.default_rng(12345)
    out = {}
    for N, a in ((15, 7), (21, 2), (25, 2), (27, 2), (35, 2), (49, 3), (63, 2)):
        P = ideal_distribution(N, a); r = true_order(N, a)
        tvs = np.array([tv(rng.multinomial(2000, P) / 2000, P) for _ in range(trials)])
        out[(N, a)] = (r, tvs.mean(), np.percentile(tvs, 99), (tvs >= 0.1).mean())
        say(f"C noise floor, perfect circuit, 2000 shots: N={N} a={a} r={r}: mean TV {tvs.mean():.3f}, p99 {np.percentile(tvs, 99):.3f}, P(TV >= 0.1) = {(tvs >= 0.1).mean():.3f}")
    assert out[(15, 7)][3] == 0 and out[(21, 2)][3] == 0      # the brief's own examples are safe
    return out


def test_negative_controls():
    """The distribution test must be able to FAIL.  The brief's classic mistakes, injected on purpose, give a large TV."""
    for N, a in ((15, 7), (21, 2)):
        t = 2 * N.bit_length(); ideal = ideal_distribution(N, a)
        ys = run_shots(build_shor(N, a), 2000, seed=3)
        good = tv(hist_from_ys(ys, len(ideal)), ideal)
        rev = [int(format(y, f"0{t}b")[::-1], 2) for y in ys]                      # counting register read in reversed bit order
        bad_rev = tv(hist_from_ys(rev, len(ideal)), ideal)
        qc = build_shor(N, a)
        qc.data = [i for k, i in enumerate(qc.data) if not (i.operation.name == "x" and k == 0)]   # work register left in |0>
        bad_init = tv(hist_from_ys(run_shots(qc, 2000, seed=3), len(ideal)), ideal)
        assert good < 0.1 and bad_rev > 0.4 and bad_init > 0.4, (N, a, good, bad_rev, bad_init)
        say(f"C negative controls N={N} a={a}: correct TV {good:.3f}; reversed bit order TV {bad_rev:.3f}; work register not set to 1 TV {bad_init:.3f}")


def test_level2_distribution(cases):
    for N, a in cases:
        qc = build_shor_level2(N, a, measure=False)
        n = N.bit_length()
        assert qc.num_qubits == 4 * n + 2
        ideal = ideal_distribution(N, a)
        ex = tv(exact_circuit_distribution(qc, 2 * n), ideal)
        assert ex < 1e-9, (N, a, ex)
        s = shot_tv(build_shor_level2(N, a), ideal)
        assert s < 0.1, (N, a, s)
        say(f"D ok: Level 2 N={N} a={a}: {qc.num_qubits} qubits, exact TV {ex:.1e}, 2000-shot TV {s:.3f}")


# ----------------------------------------------------------------------------- E: semiclassical

def test_semiclassical():
    assert build_shor_semiclassical(63, 2).num_qubits == 15 and build_shor_semiclassical(21, 2).num_qubits == 13
    assert build_shor_semiclassical(63, 2, gates=False).num_qubits == 7
    for N, a, gates in ((15, 7, False), (21, 2, False), (63, 2, False), (35, 2, False), (15, 7, True), (21, 2, True)):
        ideal = ideal_distribution(N, a)
        s = shot_tv(build_shor_semiclassical(N, a, gates), ideal)
        assert s < 0.1, (N, a, gates, s)
        say(f"E ok: semiclassical N={N} a={a} gates={gates}: {build_shor_semiclassical(N, a, gates).num_qubits} qubits, 2000-shot TV {s:.3f}")
    if FULL:   # 6-bit, 15 qubits: per-shot simulation, about 13 minutes for 2000 shots
        ideal = ideal_distribution(63, 2)
        s = shot_tv(build_shor_semiclassical(63, 2), ideal)
        assert s < 0.1, s
        say(f"E ok: 6-bit semiclassical N=63 a=2, 15 qubits, 2000-shot TV {s:.3f}")


# ----------------------------------------------------------------------------- F: factoring

class CoprimeRng(random.Random):
    """rng whose a is always coprime to N (cycles through a given list), so gcd luck cannot short-cut the quantum path."""
    def __init__(self, avals):
        super().__init__(0); self.avals = list(avals); self.k = 0
    def randrange(self, *args):
        if len(args) == 2 and args[1] > 1000:       # seeds for the simulator
            return super().randrange(*args)
        self.k += 1
        return self.avals[(self.k - 1) % len(self.avals)]


def test_factor():
    calls = Counter()
    real_run = shor.run_shots

    def counting_run(qc, *a, **k):
        calls[qc.name] += 1
        return real_run(qc, *a, **k)
    shor.run_shots = counting_run
    try:
        t0 = time.time()
        for N in [n for n in range(9, 64, 2) if not is_prime(n)]:
            p, q = factor(N, rng=random.Random(N))
            assert p * q == N and 1 < p <= q < N, (N, p, q)
        say(f"F ok: factor(N) correct for every odd composite N <= 63 (Level 1), {sum(calls.values())} order-finding circuits run, {time.time() - t0:.1f}s")
        # quantum path forced: only a coprime to N is offered, so gcd luck cannot short-cut it; every non-prime-power N must go through the circuit
        t0 = time.time(); forced = 0
        for N in [n for n in range(9, 64, 2) if not is_prime(n) and shor.perfect_power(n) is None]:
            avals = [a for a in range(2, N - 1) if math.gcd(a, N) == 1]
            random.Random(N).shuffle(avals)
            before = sum(calls.values())
            p, q = factor(N, rng=CoprimeRng(avals))
            assert p * q == N and 1 < p <= q < N and sum(calls.values()) > before, N
            forced += 1
        say(f"F ok: quantum path forced (only coprime a): {forced} non-prime-power N <= 63 factored, {sum(calls.values())} circuits in total, {time.time() - t0:.1f}s")
        # ... and fails if the circuit's samples are replaced by garbage.  All-zero samples are trivial; UNIFORM RANDOM samples are the
        # real control: the LCM of random continued-fraction denominators reaches a multiple of the order, so only the
        # SUPPORT check in order_from_shots (>= 50% of all shots must be consistent with the order) stops them.
        grng = random.Random(2024)
        shor.run_shots = lambda qc, shots, seed=None: [0] * shots
        try:
            factor(21, rng=CoprimeRng([2, 5, 4, 11]), max_attempts=8)
            raise AssertionError("factor(21) succeeded without circuit output")
        except RuntimeError:
            pass
        wins = tries = 0
        for N in [n for n in range(9, 64, 2) if not is_prime(n) and shor.perfect_power(n) is None]:
            avals = [a for a in range(2, N - 1) if math.gcd(a, N) == 1]
            shor.run_shots = lambda qc, shots, seed=None, N=N: [grng.randrange(2 ** (2 * N.bit_length())) for _ in range(shots)]
            for rep in range(10):
                tries += 1
                try:
                    factor(N, rng=CoprimeRng(avals[rep:] + avals[:rep]), max_attempts=12)
                    wins += 1
                except RuntimeError:
                    pass
        assert wins == 0, f"factor() succeeded {wins}/{tries} times on uniform random samples"
        say(f"F ok: uniform random samples instead of circuit output: factor() succeeded {wins}/{tries} times (must be 0)")
    finally:
        shor.run_shots = real_run
    say("F ok: with coprime a forced, factor() fails when the circuit samples are all zeros or uniform random")
    t0 = time.time()
    assert factor(15, level=2, rng=CoprimeRng([7, 2])) == (3, 5)
    assert factor(21, level=2, rng=CoprimeRng([2, 11])) == (3, 7)
    say(f"F ok: Level 2 factor(15) and factor(21) correct ({time.time() - t0:.0f}s)")


def test_order_recovery():
    assert order_from_shots([512], 2, 21) is None                 # 512/1024 = 1/2: denominator 2, 2^2 != 1 mod 21
    assert order_from_shots([512, 171], 2, 21) == 6               # 1/2 and 1/6 -> lcm 6, 2^6 = 64 = 1 mod 21
    assert order_from_shots([0, 0, 0], 2, 21) is None
    assert order_from_shots([64, 192], 7, 15) == 4                # 1/4, 3/4 -> 4
    assert order_from_shots([682, 54], 16, 21) == 3               # 2/3 and a noisy shot with denominator 19: lcm 57, reduced to 3
    rng = np.random.default_rng(99)                               # shots drawn from the exact ideal distribution (not the circuit)
    total = hits = 0
    for N in [n for n in range(9, 64, 2) if not is_prime(n)]:
        for a in range(2, N):
            if math.gcd(a, N) == 1:
                P = ideal_distribution(N, a); r = true_order(N, a)
                for _ in range(20):
                    got = order_from_shots(rng.choice(len(P), size=20, p=P).tolist(), a, N)
                    assert got in (None, r), (N, a, r, got)       # never a wrong order
                    total += 1; hits += got == r
    # garbage control: uniform random y must (almost) never be accepted as an order
    grng = np.random.default_rng(7); acc = gtot = 0
    for N in [n for n in range(9, 64, 2) if not is_prime(n)]:
        for a in range(2, N):
            if math.gcd(a, N) == 1:
                for _ in range(20):
                    gtot += 1; acc += order_from_shots(grng.integers(0, 2 ** (2 * N.bit_length()), size=20).tolist(), a, N) is not None
    assert acc / gtot < 0.01, (acc, gtot)
    say(f"F ok: uniform random 20-shot batches accepted as an order: {acc}/{gtot} = {acc / gtot:.4f} (the circuit's batches: {hits / total:.3f})")
    say(f"F ok: order_from_shots never returns a wrong order; found it in {hits}/{total} = {hits / total:.3f} of 20-shot batches (all N <= 63, all coprime a >= 2)")
    say("F ok: continued fractions + LCM on hand-picked shots")


# ----------------------------------------------------------------------------- G: no use of the order

def reachable(fn_names, tree_funcs):
    seen, todo = set(), list(fn_names)
    while todo:
        f = todo.pop()
        if f in seen or f not in tree_funcs:
            continue
        seen.add(f)
        for node in ast.walk(tree_funcs[f]):
            if isinstance(node, ast.Name):
                todo.append(node.id)
    return seen


def test_no_order_in_builders():
    src = inspect.getsource(shor)
    tree = ast.parse(src)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    builders = ["build_shor", "build_shor_level2", "build_shor_semiclassical"]
    for b in builders:                                    # the interface: only N, a (plus options such as measure), never r
        args = [x.arg for x in funcs[b].args.args]
        assert args[:2] == ["N", "a"] and not any("order" in x or x == "r" for x in args), (b, args)
    reach = reachable(builders, funcs)
    for banned in ("factor", "order_from_shots", "run_shots", "perfect_power"):
        assert banned not in reach, f"builders reach {banned}"
    names = {n.id for f in reach for n in ast.walk(funcs[f]) if isinstance(n, ast.Name)} | \
            {n.attr for f in reach for n in ast.walk(funcs[f]) if isinstance(n, ast.Attribute)}
    assert not {x for x in names if "order" in x.lower() or "period" in x.lower() or x == "r"}, names
    assert not any(isinstance(n, ast.While) for f in reach for n in ast.walk(funcs[f])), "no search loops in the builders"
    # the only pow() calls in the builders: a^(2^j) mod N (3 args) and the modular inverse pow(a, -1, N)
    for f in reach:
        for n in ast.walk(funcs[f]):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "pow":
                assert len(n.args) == 3
    # factor(): no while loops, no incremental order search, no gcd on powers of a other than a**(r/2)
    for f in ("factor", "order_from_shots"):
        assert not any(isinstance(n, ast.While) for n in ast.walk(funcs[f]))
    assert "run_shots" in inspect.getsource(shor.factor) and "order_from_shots" in inspect.getsource(shor.factor)
    # shor.py imports nothing from the test side
    assert not any(isinstance(n, (ast.Import, ast.ImportFrom)) and "test" in ast.dump(n) for n in tree.body)
    say(f"G ok: builders reach only {sorted(reach)}; no order/period names, no while loops, interface (N, a)")


def test_structure_independent_of_order():
    """Level 1: for one bit length, every (N, a) gives the same gate sequence on the same qubits; only the matrix entries
    (functions of a^(2^j) mod N) differ.  A circuit tailored to the order would change shape."""
    shapes = set()
    for N in odd_composites(5) + [21]:
        for a in range(1, N):
            if math.gcd(a, N) == 1:
                qc = build_shor(N, a)
                shapes.add(tuple((i.operation.name, tuple(qc.find_bit(q).index for q in i.qubits)) for i in qc.data))
    assert len(shapes) == 1, len(shapes)
    sizes = {len(build_shor(21, a).data) for a in (2, 4, 5, 8, 10, 11, 20, 1)}      # orders 6, 3, 6, 2, 6, 6, 2, 1
    assert len(sizes) == 1
    say("G ok: Level 1 circuit shape is identical for all 5-bit (N, a), orders 1..20")


# ----------------------------------------------------------------------------- main

if __name__ == "__main__":
    test_no_order_in_builders()
    test_structure_independent_of_order()
    test_qft()
    test_phi_add()
    test_phi_add_mod(15)
    test_phi_add_mod(21)
    test_cmult_and_cu(15, [a for a in range(1, 15) if math.gcd(a, 15) == 1], b_list_per_x=[0, 1, 7, 14])
    test_cmult_and_cu(9, [a for a in range(1, 9) if math.gcd(a, 9) == 1])
    test_cmult_and_cu(21, [a for a in range(1, 21) if math.gcd(a, 21) == 1], b_list_per_x=[0, 5, 20])
    test_ideal_formula()
    test_order_recovery()
    test_level1_distribution()
    test_noise_floor()
    test_negative_controls()
    test_level2_distribution([(15, 7), (21, 2)] + [(15, a) for a in (1, 2, 4, 8, 11, 13, 14)] + [(9, 2), (9, 8)]
                             + ([(21, a) for a in (1, 4, 5, 8, 10, 11, 13, 16, 17, 19, 20)] if FULL else []))
    test_semiclassical()
    test_factor()
    say("ALL TESTS PASSED")
