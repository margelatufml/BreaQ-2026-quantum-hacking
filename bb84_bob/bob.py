"""Bob's full BB84 run (steps 1-15) against a small transport interface.

    python bob.py --mode local --qber 0.03 --eve 0.01          # simulated Alice in the same process
    python alice_sim.py --port 8484 &  python bob.py --mode http --url http://127.0.0.1:8484   # simulated Alice over HTTP

run_bob() never touches HTTP: it only calls transport.call(op, **payload) -> dict. The ops are defined by alice_sim.py
(OUR invention). At the event, fill in OrganiserTransport (bottom of this file); run_bob() should not change.
"""
import argparse
import json
import math
import time
import urllib.error
import urllib.request

import numpy as np

from bb84 import (BOUNDS, CascadeError, EPS, Q_ABORT, VARIANTS, b2s, autodetect, block_size, cascade, key_length, otp, s2b, toeplitz,
                  verify_hash)

# Cascade variants: name -> (block sizes from b, back-tracking). "brief" is steps 9-11 literally.
CASCADE = {"brief": (lambda b: [b, b, b], False), "backtrack": (lambda b: [b, 3 * b, 9 * b], True),
           "backtrack_2x": (lambda b: [b, 2 * b, 4 * b], True)}   # 3 passes; b, 3b, 9b leaked about 2-4% less than b, 2b, 4b


# ============================ transports ==============================================================================
class LocalTransport:
    """In-process simulated Alice (alice_sim.AliceSession)."""

    def __init__(self, session):
        self.s, self.n_calls = session, 0

    def call(self, op, **p):
        self.n_calls += 1
        return self.s.handle(op, p)


class SimHttpTransport:
    """HTTP client for alice_sim.py's own server (routes are the simulator's, not the organisers')."""

    def __init__(self, base, config=None):
        self.base, self.sid, self.config, self.n_calls = base.rstrip("/"), None, config or {}, 0

    def call(self, op, **p):
        self.n_calls += 1
        path = "/start" if op == "start" else f"/{self.sid}/{op}"
        req = urllib.request.Request(self.base + path, json.dumps(self.config if op == "start" else p).encode(),
                                     {"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                out = json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{op}: HTTP {e.code} {e.read()[:200]}") from None
        if op == "start":
            self.sid = out["sid"]
        return out


class OrganiserTransport:
    """TODO at the event: the organisers' API is NOT published yet, so nothing here is known. Nothing is guessed.
    Fill in, then run test_bb84.py and bob.py --mode organiser:
      1. BASE_URL and authentication (token header? team id? session id?)       -> TODO
      2. ROUTES: for each op below, (HTTP method, path) and the JSON field names -> TODO
      3. Encoding of bits (string '0101', list of ints, base64, hex) and of positions/permutations -> TODO
      4. Quantum step: does the server take Bob's bases and return his results (as in the sim), or hand over qubit
         states that Bob measures himself? If the latter, add a local measurement in run_bob step 2.         -> TODO
      5. How Alice learns Bob's kept positions (step 4), the Toeplitz seed layout (step 14; run_bob(auto_detect=True)
         tries all layouts), bit->byte order of the pad (step 15)                                              -> TODO
      5b. The pre-agreed HASH (step 12). bb84.verify_hash is OUR OWN SHA-256 prefix and will NOT match the organisers'
         unless they use the same. Write the organisers' hash as a function (bits, nbits) -> str in the format the
         server returns and pass it: run_bob(t, hash_fn=their_hash). If it is wrong, step 12 fails 3 times and the
         key is discarded after 3 full Cascade runs.                                                          -> TODO
      6. Rate limits and per-request size limits (run_bob has max_batch for parity requests)                 -> TODO
    Ops run_bob uses: start, quantum, alice_bases, test, test_reply, permutation, parity, verify, verify_result,
    privacy, message, finish (see alice_sim.py for the request/response keys each one needs)."""
    BASE_URL = None          # TODO
    ROUTES = {op: None for op in ("start", "quantum", "alice_bases", "test", "test_reply", "permutation", "parity",
                                  "verify", "verify_result", "privacy", "message", "finish")}   # TODO: (method, path)

    def __init__(self):
        self.n_calls = 0

    def to_wire(self, op, payload):          # TODO: our payload -> organisers' request body
        raise NotImplementedError

    def from_wire(self, op, response):       # TODO: organisers' response -> the dict alice_sim.py returns for this op
        raise NotImplementedError

    def call(self, op, **p):
        raise NotImplementedError("OrganiserTransport is a skeleton: fill in after the organisers publish the API")


# ============================ Bob =====================================================================================
def run_bob(t, *, rng=None, cascade_mode="backtrack", bound="cp", eps=EPS, eps_pa=EPS, q_abort=Q_ABORT, t_hash=40,
            max_attempts=3, count_hash_in_leak=True, max_batch=None, toeplitz_variant="diag", auto_detect=False,
            hash_fn=verify_hash, log=lambda *a: None):
    """Returns a dict. res['abort'] is None on success, otherwise the reason (key discarded).
    res['ledger'] itemises every bit Bob learned from Alice and every bit Bob revealed."""
    rng = rng or np.random.default_rng()
    learned = {"test": 0, "parity": 0, "hash": 0}               # key-dependent bits Alice -> Bob (counts toward leak)
    revealed = {"bases": 0, "test": 0, "parity_queries": 0, "hash_verdicts": 0}   # Bob -> Alice (not key bits)
    res = {"abort": None, "bound": bound, "ledger": {"learned": learned, "revealed": revealed}}
    t0 = time.time()
    info = t.call("start")
    N = info["N"]
    res["N"] = N

    # steps 1-4: measure in random bases, receive Alice's bases, sift
    bb = rng.integers(0, 2, N, dtype=np.uint8)
    bob_bits = s2b(t.call("quantum", bob_bases=b2s(bb))["bob_bits"])
    revealed["bases"] = N
    ab = s2b(t.call("alice_bases")["alice_bases"])
    same = ab == bb
    xb, bases = bob_bits[same], bb[same]
    res["n_sift"] = len(xb)

    # steps 5-8: noise estimation on k test positions, Q_hat and the upper bound Q_u
    r = t.call("test")
    pos, abits = np.asarray(r["positions"], np.int64), s2b(r["alice_bits"])
    if len(pos) != len(abits) or pos.min() < 0 or pos.max() >= len(xb):
        raise ValueError("bad test positions")
    u, first = np.unique(pos, return_index=True)               # 'k random integers' may repeat: count each position once
    wrong = abits[first] != xb[u]
    m, k = int(wrong.sum()), len(u)
    t.call("test_reply", bob_bits=b2s(xb[pos]))
    learned["test"], revealed["test"] = len(pos), len(pos)
    q_hat, q_u = m / k, BOUNDS[bound](m, k, eps)
    res.update(m=m, k=k, q_hat=q_hat, q_u=q_u)
    z = bases[u] == 0                                          # diagnostic only: error rate per basis
    res["q_hat_by_basis"] = {"Z": float(wrong[z].mean()) if z.any() else None, "X": float(wrong[~z].mean()) if (~z).any() else None}
    res["warnings"] = []
    if z.any() and (~z).any() and 0 < m < k:                   # Z and X rates differ by > 5 sigma: noise is not basis-symmetric
        nz, nx = int(z.sum()), int((~z).sum())
        diff = abs(res["q_hat_by_basis"]["Z"] - res["q_hat_by_basis"]["X"])
        if diff > 5 * math.sqrt(q_hat * (1 - q_hat) * (1 / nz + 1 / nx)):
            res["warnings"].append(f"error rate differs by basis (Z {res['q_hat_by_basis']['Z']:.4f}, X {res['q_hat_by_basis']['X']:.4f}): "
                                   "the pooled Q_hat understates the worse basis; Q_u is NOT adjusted")
            log("WARNING: " + res["warnings"][0])
    if q_u > q_abort:
        res["abort"] = f"Q_u={q_u:.4f} > {q_abort}"
        return res
    keep = np.ones(len(xb), bool)
    keep[u] = False
    xb = xb[keep]
    n = len(xb)
    res["n"] = n

    # steps 9-13: Cascade, hash check, retry (max 3 attempts). Every parity Alice sends is counted.
    b = block_size(q_hat, n)
    sizes_fn, back = CASCADE[cascade_mode]
    sizes = sizes_fn(b)

    def oracle(pid, lo, hi):
        learned["parity"] += len(lo)
        revealed["parity_queries"] += len(lo)
        step = max_batch or len(lo)
        return np.concatenate([s2b(t.call("parity", pass_id=int(pid), lo=lo[i:i + step].tolist(),
                                          hi=hi[i:i + step].tolist())["parities"]) for i in range(0, len(lo), step)])

    def get_perm(pid):
        return np.asarray(t.call("permutation", pass_id=int(pid))["perm"], np.int64)

    res.update(block_sizes=sizes, cascade_mode=cascade_mode)
    attempts, ok = 0, False
    while attempts < max_attempts and not ok:
        try:
            xb = cascade(xb, oracle, get_perm, sizes, back, pass_base=attempts * 10)
        except CascadeError as e:
            res["abort"] = f"cascade did not converge: {e}"
            return res
        h = t.call("verify", nbits=t_hash)["hash"]
        learned["hash"] += t_hash
        attempts += 1
        ok = h == hash_fn(xb, t_hash)
        revealed["hash_verdicts"] += 1
        discard = t.call("verify_result", ok=bool(ok)).get("discard")
        log(f"attempt {attempts}: parities so far {learned['parity']}, hash {'OK' if ok else 'MISMATCH'}")
        if discard:
            break
    res["attempts"] = attempts
    if not ok:
        res["abort"] = f"verification hash failed {attempts}x -> key discarded"
        return res

    # step 14: key length from the transcribed formula, Toeplitz privacy amplification
    leak_ec = learned["parity"] + (learned["hash"] if count_hash_in_leak else 0)
    l_real = key_length(n, q_u, leak_ec, eps_pa)
    l_bob = math.floor(l_real)
    res.update(leak_ec=leak_ec, l_formula=l_real, l_bob=l_bob)
    pa = t.call("privacy")
    if pa.get("abort") or l_bob <= 0:
        res["abort"] = f"l <= 0 (Alice l={pa.get('l')}, Bob l={l_bob}) -> assume Eve, discard"
        return res
    l_alice, seed = pa["l"], s2b(pa["seed"])
    l = min(l_alice, l_bob)                  # never use more key than Bob's own accounting justifies
    res.update(l_alice=l_alice, l=l)
    try:
        ct = bytes.fromhex(t.call("message")["ciphertext"])
    except Exception as e:                   # e.g. final key shorter than the message: no pad possible
        res["abort"] = f"message step failed (l={l}): {e}"
        return res
    if auto_detect:
        found = autodetect(ct, seed, xb, l_alice)
        res["toeplitz_variant"] = found[:2] if found else None
        plain = found[2] if found else b""
        key = toeplitz(seed, xb, l_alice, found[0] if found else toeplitz_variant)[:l]
    else:
        key = toeplitz(seed, xb, l_alice, toeplitz_variant)[:l]   # same rows as Alice's T; truncating is safe
        plain = otp(ct, key)
    res.update(final_key=key, plaintext=plain, secs=time.time() - t0, calls=t.n_calls)
    res["final"] = t.call("finish", plaintext=plain.hex())
    return res


def summary(res):
    s = {k: v for k, v in res.items() if k not in ("final_key", "plaintext", "final")}
    return {**s, "plaintext": res.get("plaintext", b"")[:48], "alice_report": res.get("final")}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["local", "http", "organiser"], default="local")
    ap.add_argument("--url", default="http://127.0.0.1:8484")
    ap.add_argument("--N", type=int, default=200_000, help="simulator only")
    ap.add_argument("--k", type=int, default=20_000, help="simulator only")
    ap.add_argument("--qber", type=float, default=0.03, help="simulator only")
    ap.add_argument("--eve", type=float, default=0.0, help="simulator only")
    ap.add_argument("--sim-seed", type=int, default=1, help="seed of the SIMULATED Alice and channel")
    ap.add_argument("--seed", type=int, default=None,
                    help="seed Bob's random generator (reproducible simulation only). Default: OS entropy. Refused in organiser mode.")
    ap.add_argument("--cascade", choices=list(CASCADE), default="backtrack")
    ap.add_argument("--bound", choices=list(BOUNDS), default="cp")
    ap.add_argument("--eps", type=float, default=EPS, help="epsilon of the Q_u bound (1e-10)")
    ap.add_argument("--eps-pa", type=float, default=EPS, help="epsilon of privacy amplification (1e-10)")
    ap.add_argument("--q-abort", type=float, default=Q_ABORT, help="step 8 abort threshold (0.11)")
    ap.add_argument("--no-hash-leak", action="store_true", help="do not count hash bits in leak_EC (match an Alice that counts parity bits only)")
    ap.add_argument("--sim-no-hash-leak", action="store_true", help="simulated Alice does not count hash bits in her l")
    ap.add_argument("--auto-detect", action="store_true", help="try all Toeplitz seed layouts and pad bit orders")
    ap.add_argument("--toeplitz-variant", choices=VARIANTS, default="diag")
    a = ap.parse_args()
    if a.mode == "organiser" and a.seed is not None:
        ap.error("--seed is for simulation only; a real session must use OS entropy")
    cfg = dict(N=a.N, k=a.k, qber=a.qber, eve=a.eve, seed=a.sim_seed, eps=a.eps, eps_pa=a.eps_pa, q_abort=a.q_abort,
               bound=a.bound, count_hash_in_leak=not a.sim_no_hash_leak)
    if a.mode == "local":
        from alice_sim import AliceSession
        t = LocalTransport(AliceSession(**cfg))
    elif a.mode == "http":
        t = SimHttpTransport(a.url, cfg)
    else:
        t = OrganiserTransport()
    rng = None if a.seed is None else np.random.default_rng(a.seed + 1000)
    for k, v in summary(run_bob(t, rng=rng, cascade_mode=a.cascade, bound=a.bound, eps=a.eps, eps_pa=a.eps_pa,
                                q_abort=a.q_abort, count_hash_in_leak=not a.no_hash_leak, auto_detect=a.auto_detect,
                                toeplitz_variant=a.toeplitz_variant, log=print)).items():
        print(f"{k:16s} {v}")
