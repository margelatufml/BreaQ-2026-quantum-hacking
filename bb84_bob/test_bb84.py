"""Self-check with plain asserts:  python test_bb84.py   -> prints 'ALL OK' (about 5 s)."""
import math
import threading

import numpy as np
from scipy.stats import beta

import alice_sim
from alice_sim import AliceSession
from bb84 import (EPS, VARIANTS, block_size, cascade, h2, key_length, otp, q_cp, q_hoeffding, toeplitz, toeplitz_dense,
                  autodetect)
from bob import LocalTransport, SimHttpTransport, run_bob

rng = np.random.default_rng(0)


def H(x):                                   # binary entropy typed again, independently of bb84.h2
    return -x * math.log2(x) - (1 - x) * math.log2(1 - x)


def session(**kw):
    kw = {"N": 200_000, "k": 20_000, "seed": 1, **kw}
    return AliceSession(**kw)


def run(alice, seed=11, **kw):
    return run_bob(LocalTransport(alice), rng=np.random.default_rng(seed), **kw)


# 1. formulas exactly as transcribed from the brief
assert abs(h2(0.5) - 1) < 1e-12 and h2(0) == 0 and abs(h2(0.11) - H(0.11)) < 1e-12
assert abs(q_hoeffding(600, 20000) - (600 / 20000 + math.sqrt(math.log(1 / 1e-10) / (2 * 20000)))) < 1e-15
assert q_cp(600, 20000) == beta.ppf(1 - 1e-10, 600 + 1, 20000 - 600) and q_cp(600, 20000) < q_hoeffding(600, 20000)
assert not math.isnan(q_cp(20000, 20000)) and q_cp(0, 20000) > 0          # edge cases m = k and m = 0
assert abs(2 * math.log2(1 / EPS) - 66.4385619) < 1e-6
assert key_length(80000, 0.04, 20000) == 80000 - 80000 * H(0.04) - 20000 - 2 * math.log2(1 / 1e-10)
try:
    math.sqrt(math.log(1 / 1e10) / 40000)
    raise SystemExit("eps = 10^10 literally must be invalid")
except ValueError:
    pass                                     # so "10^10" in the brief can only mean 10^-10

# 2. Toeplitz: FFT equals the explicit matrix for every seed layout, is GF(2)-linear, exact at real size, and fast
for v in VARIANTS:
    n, l = 40, 17
    s, x, y = (rng.integers(0, 2, z, dtype=np.uint8) for z in (n + l, n, n))       # n + l seed bits, as the brief says
    assert (toeplitz(s, x, l, v) == toeplitz_dense(s, x, l, v)).all(), v
    assert ((toeplitz(s, x, l, v) ^ toeplitz(s, y, l, v)) == toeplitz(s, x ^ y, l, v)).all()
n, l = 100_000, 50_000
s, x = rng.integers(0, 2, n + l, dtype=np.uint8), rng.integers(0, 2, n, dtype=np.uint8)
import time
t0 = time.time()
y = toeplitz(s, x, l)
assert time.time() - t0 < 5, "Toeplitz too slow"
for i in rng.integers(0, l, 50):             # exact integer dot products on random rows: T[i,j] = s[i-j+n-1]
    assert int(s[i:i + n][::-1].astype(np.int64) @ x) & 1 == y[i]

# 3. Cascade on a plain oracle: the brief's literal version leaves errors, back-tracking removes them
n, q = 20000, 0.03
xa = rng.integers(0, 2, n, dtype=np.uint8)
xb = xa ^ (rng.random(n) < q).astype(np.uint8)
perms, asked = {}, [0]


def oracle(pid, lo, hi):
    cs = np.concatenate(([0], np.cumsum(xa[perms.get(pid, np.arange(n))], dtype=np.int64)))
    asked[0] += len(lo)
    return ((cs[hi] - cs[lo]) & 1).astype(np.uint8)


def get_perm(pid):
    perms[pid] = rng.permutation(n)
    return perms[pid]


b = block_size(q, n)
assert b == round(0.73 / q)
r_brief = (cascade(xb, oracle, get_perm, [b] * 3, False) != xa).sum()
r_bt = (cascade(xb, oracle, get_perm, [b, 3 * b, 9 * b], True, pass_base=10) != xa).sum()
assert (xb != xa).sum() > 400 and 0 < r_brief < (xb != xa).sum() / 5 and r_bt == 0, (r_brief, r_bt)
assert block_size(0.0, 80000) == 730 and block_size(0.0, 100) == 100     # Q_hat = 0 guard: no ZeroDivisionError

# 4. one-time pad
key = rng.integers(0, 2, 4000, dtype=np.uint8)
assert otp(otp(b"hello BB84", key), key) == b"hello BB84"
try:
    otp(b"x" * 600, key)
    raise SystemExit("pad longer than key must raise")
except ValueError:
    pass

# 5. end to end, typical parameters: Alice and Bob keys identical, message decrypts, l equals the formula,
#    ledger equals what Alice logged
for qber in (0.01, 0.02, 0.03, 0.04):
    for eve in (0.0, 0.01):
        for bound in ("cp", "hoeffding"):
            a = session(qber=qber, eve=eve, bound=bound, seed=int(qber * 100) + int(eve * 100))
            r = run(a, bound=bound)
            tag = (qber, eve, bound)
            assert r["abort"] is None and r["final"]["success"], (tag, r["abort"])
            assert r["plaintext"] == a.message and (r["final_key"] == a.final[:r["l"]]).all() and r["l"] == len(a.final), tag
            q_u = q_cp(r["m"], r["k"]) if bound == "cp" else q_hoeffding(r["m"], r["k"])
            leak = r["ledger"]["learned"]["parity"] + r["ledger"]["learned"]["hash"]
            assert r["l"] == math.floor(r["n"] - r["n"] * H(q_u) - leak - 2 * math.log2(1 / 1e-10)), tag   # formula
            assert r["ledger"]["learned"] == a.leak and sum(b_ for _, b_ in a.log) == sum(a.leak.values()), tag
            assert r["n"] == r["n_sift"] - r["k"] and r["attempts"] == 1, tag
# no noise at all: Q_hat = 0
a = session(qber=0.0, eve=0.0, seed=3)
r = run(a)
assert r["abort"] is None and r["m"] == 0 and r["q_hat"] == 0 and r["final"]["success"] and r["plaintext"] == a.message
assert r["block_sizes"][0] == 730

# 6. aborts
r = run(session(qber=0.12, seed=4))                      # noise above the threshold: abort at step 8, only k bits leaked
assert r["abort"].startswith("Q_u=") and r["ledger"]["learned"] == {"test": 20000, "parity": 0, "hash": 0}, r["abort"]
r = run(session(qber=0.03, eve=1.0, seed=5))             # Eve on every qubit: Q about 28%
assert r["abort"].startswith("Q_u=") and r["q_hat"] > 0.2
a = session(qber=0.095, seed=6)                          # Q_u below 11% but l < 0 once leak and Q_u are charged
r = run(a)
assert r["q_u"] < 0.11 and r["abort"].startswith("l <= 0") and r["l_formula"] < 0, (r["q_u"], r["abort"], r["l_formula"])

# 7. hash paths: literal Cascade fails the hash once and is repeated; a hash that never matches is discarded after 3
a = session(qber=0.03, seed=7)
r = run(a, cascade_mode="brief")
assert r["abort"] is None and r["attempts"] == 2 and r["ledger"]["learned"]["hash"] == 80 and r["final"]["success"]


class BadHash(LocalTransport):
    def call(self, op, **p):
        out = super().call(op, **p)
        return {"hash": "0"} if op == "verify" else out


a = session(qber=0.03, seed=8)
r = run_bob(BadHash(a), rng=np.random.default_rng(1))
assert r["abort"].startswith("verification hash failed 3x") and r["attempts"] == 3 and a.state == "aborted"
assert r["ledger"]["learned"]["hash"] == 120 and "final_key" not in r

# 8. Alice and Bob may use different bounds: Bob never uses more key than his own accounting allows
a = session(qber=0.03, seed=9, bound="hoeffding")        # Alice's l is the smaller one
r = run(a, bound="cp")
assert r["l"] == r["l_alice"] < r["l_bob"] and r["plaintext"] == a.message and (r["final_key"] == a.final).all()
a = session(qber=0.03, seed=9, bound="cp")               # Bob's l is the smaller one: his key is a prefix of Alice's
r = run(a, bound="hoeffding")
assert r["l"] == r["l_bob"] < r["l_alice"] and r["plaintext"] == a.message and (r["final_key"] == a.final[:r["l"]]).all()
a = session(qber=0.03, seed=9, count_hash_in_leak=False)  # Alice does not count the hash bits
r = run(a)
assert r["l"] == r["l_bob"] <= r["l_alice"] and (r["final_key"] == a.final[:r["l"]]).all()

# 9. API variations: repeated test positions, unknown seed layout (auto-detect), X-gate noise model
a = session(N=60000, k=6000, qber=0.03, dup_positions=True, seed=10)
r = run(a)
assert r["final"]["success"] and r["k"] < 6000 and r["ledger"]["learned"]["test"] == 6000
for v in VARIANTS:
    a = session(N=60000, k=6000, qber=0.02, seed_variant=v, seed=12)
    r = run(a, auto_detect=True)
    assert r["final"]["success"] and r["toeplitz_variant"] == (v, "big") and (r["final_key"] == a.final[:r["l"]]).all(), v
r = run(session(N=60000, k=6000, qber=0.06, flip_model="x_gate", seed=13))
bb = r["q_hat_by_basis"]
assert bb["X"] < 0.005 and 0.05 < bb["Z"] < 0.07 and abs(r["q_hat"] - 0.03) < 0.006     # pooled Q hides a 6% Z error rate

# 10. the same run over real HTTP (JSON on the wire) gives the same result as in-process
cfg = dict(N=60000, k=6000, qber=0.03, eve=0.01, seed=5)
r1 = run_bob(LocalTransport(AliceSession(**cfg)), rng=np.random.default_rng(1))
srv = alice_sim.ThreadingHTTPServer(("127.0.0.1", 0), alice_sim.Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
r2 = run_bob(SimHttpTransport(f"http://127.0.0.1:{srv.server_port}", cfg), rng=np.random.default_rng(1))
srv.shutdown()
assert r1["final"]["success"] and r2["final"]["success"] and r1["l"] == r2["l"] and r1["ledger"] == r2["ledger"]
assert (r1["final_key"] == r2["final_key"]).all()
# 11. injected hash function (the organisers' hash is unknown): both sides must use the same one
import hashlib
def other_hash(bits, nbits=40):
    return hashlib.md5(np.packbits(bits).tobytes()).hexdigest()[: nbits // 4]
a = AliceSession(N=60000, k=6000, qber=0.03, seed=14, hash_fn=other_hash)
r = run_bob(LocalTransport(a), rng=np.random.default_rng(1), hash_fn=other_hash)
assert r["abort"] is None and r["final"]["success"] and r["attempts"] == 1
a = AliceSession(N=60000, k=6000, qber=0.03, seed=14, hash_fn=other_hash)      # Bob keeps the default hash: mismatch x3
r = run_bob(LocalTransport(a), rng=np.random.default_rng(1))
assert r["abort"].startswith("verification hash failed 3x") and "final_key" not in r

# 12. a lying parity oracle cannot make Cascade loop forever
from bb84 import CascadeError
lie = np.random.default_rng(3)
try:
    cascade(rng.integers(0, 2, 5000, dtype=np.uint8), lambda pid, lo, hi: lie.integers(0, 2, len(lo), dtype=np.uint8),
            lambda pid: lie.permutation(5000), [50, 150, 450], True)
    raise SystemExit("lying oracle must raise CascadeError")
except CascadeError:
    pass
class Liar(LocalTransport):
    def call(self, op, **p):
        out = super().call(op, **p)
        return {"parities": "".join(lie.choice(["0", "1"], len(out["parities"])))} if op == "parity" else out
r = run_bob(Liar(AliceSession(N=60000, k=6000, qber=0.03, seed=15)), rng=np.random.default_rng(1))
assert r["abort"].startswith("cascade did not converge") and "final_key" not in r

# 13. warning when the error rate depends on the basis (X-gate noise); none for symmetric noise
r = run(session(N=60000, k=6000, qber=0.06, flip_model="x_gate", seed=13))
assert len(r["warnings"]) == 1 and "differs by basis" in r["warnings"][0], r["warnings"]
r = run(session(N=60000, k=6000, qber=0.03, eve=0.01, seed=13))
assert r["warnings"] == [], r["warnings"]

print("ALL OK")
