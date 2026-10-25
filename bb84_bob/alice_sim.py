"""SIMULATION ONLY. A local stand-in for the organisers' Alice + quantum channel + public channel.

This is NOT the organisers' server and its ops/field names are OUR invention (the real API is unpublished).
bob.py talks to it through ops like "quantum", "test", "parity"; at the event only the transport in bob.py changes.

AliceSession(N, k, qber, eve, ...) is one session. Channel model:
  eve  = fraction of qubits intercepted and re-sent by Eve (intercept-resend in a random basis, adds f/4 errors)
  qber = noise: flip_model "measured_bit" flips Bob's measured bit with probability qber (same in both bases);
         flip_model "x_gate" applies a physical bit flip to the qubit (invisible in the X basis, so the pooled error
         rate is only qber/2) -- kept to show that the 'noise = Eve' lesson depends on the noise model.
Everything Alice tells Bob that depends on her key is counted in self.leak and itemised in self.log.
Run an HTTP wrapper with:  python alice_sim.py --port 8484
"""
import argparse
import json
import math
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

from bb84 import BOUNDS, EPS, Q_ABORT, b2s, key_length, otp, s2b, toeplitz, verify_hash


class ProtocolError(Exception):
    pass


class AliceSession:
    def __init__(self, N=200_000, k=20_000, qber=0.03, eve=0.0, bound="cp", eps=EPS, eps_pa=EPS, q_abort=Q_ABORT,
                 seed=None, message=None, count_hash_in_leak=True, dup_positions=False, seed_variant="diag",
                 flip_model="measured_bit", max_verify_fail=3, hash_fn=verify_hash):
        self.rng = np.random.default_rng(seed)
        self.N, self.k, self.qber, self.eve = N, k, qber, eve
        self.bound, self.eps, self.eps_pa, self.q_abort = bound, eps, eps_pa, q_abort
        self.count_hash, self.dup, self.seed_variant, self.flip_model = count_hash_in_leak, dup_positions, seed_variant, flip_model
        self.max_verify_fail, self.fails, self.hash_fn = max_verify_fail, 0, hash_fn
        self.message = message if message is not None else b"BreaQ-2026 BB84 OK: " + self.rng.bytes(12).hex().encode()
        self.leak = {"test": 0, "parity": 0, "hash": 0}      # key-dependent bits Bob learned from Alice
        self.log = []                                        # (op, bits) for every such disclosure
        self.state, self.perms, self.report = "new", {}, None

    def _leak(self, kind, bits, op):
        self.leak[kind] += bits
        self.log.append((op, bits))

    # ---- steps 1-4: quantum channel and sifting ----------------------------------------------------------------
    def op_start(self, **_):
        self.a_bases = self.rng.integers(0, 2, self.N, dtype=np.uint8)
        self.a_bits = self.rng.integers(0, 2, self.N, dtype=np.uint8)
        self.state = "started"
        return {"N": self.N, "k": self.k, "eps": self.eps, "message_len": len(self.message)}

    def op_quantum(self, bob_bases):
        """Sim shortcut: Bob hands over his bases and gets his measurement results (simulates the qubit transfer)."""
        self._need("started")
        r, N = self.rng, self.N
        bb = s2b(bob_bases)
        if len(bb) != N:
            raise ProtocolError("need N bases")
        eve = r.random(N) < self.eve
        e_bases = r.integers(0, 2, N, dtype=np.uint8)
        e_bits = np.where(e_bases == self.a_bases, self.a_bits, r.integers(0, 2, N, dtype=np.uint8))
        s_bases = np.where(eve, e_bases, self.a_bases)               # what really travels to Bob
        s_bits = np.where(eve, e_bits, self.a_bits)
        out = np.where(bb == s_bases, s_bits, r.integers(0, 2, N, dtype=np.uint8)).astype(np.uint8)
        if self.flip_model == "measured_bit":
            out ^= (r.random(N) < self.qber).astype(np.uint8)
        elif self.flip_model == "x_gate":
            out ^= ((r.random(N) < self.qber) & (bb == 0)).astype(np.uint8)
        else:
            raise ValueError(self.flip_model)
        match = self.a_bases == bb
        self.key = self.a_bits[match].copy()                         # Alice's sifted key
        self.bob_raw = out[match]                                    # analysis only: Bob's sifted key before correction
        self.state = "measured"
        return {"bob_bits": b2s(out)}

    def op_alice_bases(self):
        self._need("measured")                                       # only after Bob has measured
        self.state = "sifted"
        return {"alice_bases": b2s(self.a_bases)}

    # ---- steps 5-8: noise estimation ----------------------------------------------------------------------------
    def op_test(self):
        self._need("sifted")
        n = len(self.key)
        self.pos = self.rng.integers(0, n, self.k) if self.dup else self.rng.choice(n, self.k, replace=False)
        self._leak("test", self.k, "test")
        self.state = "tested"
        return {"positions": self.pos.tolist(), "alice_bits": b2s(self.key[self.pos])}

    def op_test_reply(self, bob_bits):
        self._need("tested")
        bb = s2b(bob_bits)
        if len(bb) != len(self.pos):
            raise ProtocolError("need one bit per position")
        u, first = np.unique(self.pos, return_index=True)
        m = int((bb[first] != self.key[u]).sum())
        self.q_hat, self.q_u = m / len(u), BOUNDS[self.bound](m, len(u), self.eps)
        if self.q_u > self.q_abort:
            self.state = "aborted"
            return {"abort": True, "q_hat": self.q_hat, "q_u": self.q_u}
        keep = np.ones(len(self.key), bool)
        keep[u] = False
        self.key, self.bob_raw = self.key[keep], self.bob_raw[keep]  # both sides discard the test positions
        self.state = "estimated"
        return {"abort": False, "q_hat": self.q_hat, "q_u": self.q_u, "n_key": len(self.key)}

    # ---- steps 9-13: Cascade and verification hash --------------------------------------------------------------
    def op_permutation(self, pass_id):
        self._need("estimated")
        self.perms[pass_id] = self.rng.permutation(len(self.key))
        return {"perm": self.perms[pass_id].tolist()}

    def op_parity(self, pass_id, lo, hi):
        self._need("estimated")
        lo, hi = np.asarray(lo, np.int64), np.asarray(hi, np.int64)
        if (lo < 0).any() or (hi > len(self.key)).any() or (hi <= lo).any():
            raise ProtocolError("bad range")
        order = self.perms.get(pass_id, np.arange(len(self.key)))    # a pass without a permutation = natural order
        cs = np.concatenate(([0], np.cumsum(self.key[order], dtype=np.int64)))
        self._leak("parity", len(lo), "parity")
        return {"parities": b2s((cs[hi] - cs[lo]) & 1)}

    def op_verify(self, nbits):
        self._need("estimated")
        self._leak("hash", nbits, "hash")
        return {"hash": self.hash_fn(self.key, nbits)}

    def op_verify_result(self, ok):
        self._need("estimated")
        if ok:
            self.state = "verified"
            return {"discard": False}
        self.fails += 1
        if self.fails >= self.max_verify_fail:                       # step 13: third mismatch -> discard
            self.state = "aborted"
            return {"discard": True}
        return {"discard": False}

    # ---- steps 14-15: privacy amplification, one-time pad -------------------------------------------------------
    def op_privacy(self):
        self._need("verified")
        n = len(self.key)
        leak_ec = self.leak["parity"] + (self.leak["hash"] if self.count_hash else 0)
        self.l = math.floor(key_length(n, self.q_u, leak_ec, self.eps_pa))
        if self.l <= 0:
            self.state = "aborted"
            return {"abort": True, "l": self.l}
        seed = self.rng.integers(0, 2, n + self.l, dtype=np.uint8)   # the brief: "n random bits and l random bits"
        self.final = toeplitz(seed, self.key, self.l, self.seed_variant)
        self.state = "amplified"
        return {"abort": False, "l": self.l, "n": n, "seed": b2s(seed)}

    def op_message(self):
        self._need("amplified")
        if 8 * len(self.message) > self.l:
            raise ProtocolError("final key shorter than message")
        return {"ciphertext": otp(self.message, self.final).hex()}

    def op_finish(self, plaintext):
        ok = bytes.fromhex(plaintext) == self.message if plaintext else False
        self.report = {"success": ok, "l": getattr(self, "l", 0), "leak": dict(self.leak),
                       "leak_total": sum(self.leak.values()), "state": self.state}
        return self.report

    # ---- plumbing -----------------------------------------------------------------------------------------------
    def _need(self, st):
        order = ["new", "started", "measured", "sifted", "tested", "estimated", "verified", "amplified"]
        if self.state == "aborted":
            raise ProtocolError("session aborted")
        if order.index(self.state) < order.index(st):
            raise ProtocolError(f"op not allowed in state {self.state}; need {st}")

    def handle(self, op, payload):
        fn = getattr(self, "op_" + op, None)
        if fn is None:
            raise ProtocolError("unknown op " + op)
        return fn(**payload)


# ---- local HTTP wrapper (SIMULATION; routes are ours): POST /start {config}, POST /<sid>/<op> {payload} -----------
SESSIONS = {}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        parts = self.path.strip("/").split("/")
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        try:
            if parts == ["start"]:
                s = AliceSession(**body)
                sid = uuid.uuid4().hex[:8]
                SESSIONS[sid] = s
                self._send(200, {"sid": sid, **s.op_start()})
            else:
                sid, op = parts
                self._send(200, SESSIONS[sid].handle(op, body))
        except (ProtocolError, KeyError, TypeError, ValueError) as e:
            self._send(400, {"error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8484)
    a = ap.parse_args()
    print(f"SIMULATED Alice on http://127.0.0.1:{a.port}  (not the organisers' server)")
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()
