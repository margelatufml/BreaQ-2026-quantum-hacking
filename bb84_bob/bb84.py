"""BB84 Bob-side math as pure functions (numpy + scipy only).

Formulas are transcribed from the brief "Catch the Eavesdropper - BB84 Blue Track" (steps 8, 14):
  Hoeffding        Q_u = Q_hat + sqrt( ln(1/eps) / (2k) )
  Clopper-Pearson  Q_u = scipy.stats.beta.ppf(1 - eps, m + 1, k - m)
  key length       l = n - n*h(Q_u) - leak_EC - 2*log2(1/eps_PA)
  binary entropy   h(x) = -x*log2(x) - (1-x)*log2(1-x)
Bit arrays are numpy uint8 in {0,1}; on the wire they are '0'/'1' strings (b2s / s2b).
"""
import hashlib
import math

import numpy as np
from scipy.signal import fftconvolve
from scipy.stats import beta

# The brief writes "10^10"; only 10^-10 makes sense (with 10^10, ln(1/eps) < 0 and the square root fails).
EPS = 1e-10
Q_ABORT = 0.11          # step 8: abort if Q_u exceeds about 11%


def b2s(a):
    return (np.asarray(a, np.uint8) + 48).tobytes().decode()


def s2b(s):
    return np.frombuffer(s.encode(), np.uint8) - 48


# ---- step 8: bounds ; step 14: entropy and key length -----------------------------------------------------
def h2(x):
    return 0.0 if x <= 0 or x >= 1 else -x * math.log2(x) - (1 - x) * math.log2(1 - x)


def q_hoeffding(m, k, eps=EPS):
    return m / k + math.sqrt(math.log(1 / eps) / (2 * k))


def q_cp(m, k, eps=EPS):
    return 1.0 if m >= k else float(beta.ppf(1 - eps, m + 1, k - m))   # m = k would make beta.ppf return nan


BOUNDS = {"hoeffding": q_hoeffding, "cp": q_cp}


def key_length(n, q_u, leak_ec, eps_pa=EPS):
    """Real number; the key has floor(l) bits. n = sifted bits left after the k test bits were removed."""
    return n - n * h2(q_u) - leak_ec - 2 * math.log2(1 / eps_pa)


# ---- steps 9-11: Cascade ------------------------------------------------------------------------------------
def block_size(q_hat, n):
    """b ~ 0.73/Q_hat. Guard: Q_hat = 0 (no error seen in the test) would divide by zero, so Q_hat is floored at 1e-3."""
    return int(min(n, max(2, round(0.73 / max(q_hat, 1e-3)))))


def _par(bits, lo, hi):
    cs = np.concatenate(([0], np.cumsum(bits, dtype=np.int64)))
    return ((cs[hi] - cs[lo]) & 1).astype(np.uint8)


class CascadeError(RuntimeError):
    """The parity oracle is inconsistent (a truthful oracle needs at most one fix per wrong bit)."""


def cascade(xb, oracle, get_perm, block_sizes, backtrack, pass_base=0):
    """Bob-driven Cascade. Returns Bob's corrected key.
    oracle(pass_id, lo, hi) -> Alice's parities (uint8 array) of positions [lo,hi) of the key in that pass's
    permuted order; EVERY returned bit is one leaked bit, the caller counts them.
    get_perm(pass_id) -> the permutation Alice chose for that pass (step 10); pass 0 of the first run is unpermuted.
    block_sizes=[b,b,b], backtrack=False : the brief literally (steps 9-11, no back-tracking).
    backtrack=True : after a bit is fixed, earlier passes whose blocks became odd are searched again (Brassard-Salvail).
    Bisection: one parity per level (the right half is block XOR left half, so it needs no second query);
    all odd blocks of a pass are bisected level by level, so a pass needs only ~log2(b) round trips.
    Hard cap: more than n//4 fixes (the abort threshold is 11% errors) means the oracle lies -> CascadeError."""
    n = len(xb)
    fixes = 0
    x = xb.copy()
    perms, invs, sizes, status = [], [], [], []

    def search(i, idx):
        B, perm = sizes[i], perms[i]
        cs = np.concatenate(([0], np.cumsum(x[perm], dtype=np.int64)))
        lo = idx * B
        hi = np.minimum(lo + B, n)
        while True:
            act = np.flatnonzero(hi - lo > 1)
            if act.size == 0:
                return perm[lo]                                 # original indices of the bits found to be wrong
            mid = (lo[act] + hi[act]) // 2
            a = oracle(pass_base + i, lo[act], mid)
            left_bad = ((cs[mid] - cs[lo[act]]) & 1).astype(np.uint8) ^ a
            hi[act] = np.where(left_bad == 1, mid, hi[act])
            lo[act] = np.where(left_bad == 1, lo[act], mid)

    for j, B in enumerate(block_sizes):
        perm = np.arange(n) if (j == 0 and pass_base == 0) else np.asarray(get_perm(pass_base + j))
        inv = np.empty(n, np.int64)
        inv[perm] = np.arange(n)
        perms.append(perm), invs.append(inv), sizes.append(B)
        lo = np.arange(0, n, B)
        hi = np.minimum(lo + B, n)
        status.append(oracle(pass_base + j, lo, hi) ^ _par(x[perm], lo, hi))     # 1 = block parity differs
        while True:
            for i in (range(j, -1, -1) if backtrack else [j]):
                idx = np.flatnonzero(status[i])
                if idx.size:
                    break
            else:
                break
            found = search(i, idx)
            fixes += 1
            if fixes > n // 4:
                raise CascadeError(f"cascade made {fixes} fixes on {n} bits: parity answers are inconsistent")
            x[found] ^= 1
            for t in range(j + 1):                              # a flipped bit toggles its block in every pass so far
                np.bitwise_xor.at(status[t], invs[t][found] // sizes[t], 1)
    return x


# ---- step 12: verification hash -------------------------------------------------------------------------------
def verify_hash(bits, nbits=40):
    """Our own 'pre-agreed' hash: first nbits of SHA-256 over the packed key bits. TODO: use the organisers' hash."""
    d = hashlib.sha256(np.packbits(bits).tobytes() + len(bits).to_bytes(8, "big")).digest()
    return format(int.from_bytes(d, "big") >> (256 - nbits), "x")


# ---- step 14: Toeplitz privacy amplification ------------------------------------------------------------------
# T is l x n with T[i,j] = d[i-j+n-1] (constant diagonals), so it needs n+l-1 bits. The brief hands out n+l random
# bits and does not say how they fill T, so the layout is a parameter ("variant"); bob.py can auto-detect it.
VARIANTS = ("diag", "row_col", "row_col_skip", "col_row", "col_row_skip")


def toeplitz_diagonals(seed, n, l, variant="diag"):
    s = np.asarray(seed, np.uint8)
    if variant == "diag":                    # d[0..n+l-2] = seed[0..n+l-2]; the last seed bit is unused
        return s[: n + l - 1]
    if variant in ("row_col", "row_col_skip"):   # first row r = seed[:n], first column below the corner = next l-1 bits
        r, c = s[:n], s[n + (variant == "row_col_skip"): n + l - (variant == "row_col")]
    elif variant in ("col_row", "col_row_skip"):  # first column = seed[:l], first row below the corner = next n-1 bits
        c, r = s[:l], s[l + (variant == "col_row_skip"): l + n - (variant == "col_row")]
        c, r = c[1:], np.concatenate(([c[0]], r))
    else:
        raise ValueError(variant)
    return np.concatenate((r[::-1], c))      # d[n-1-j] = T[0,j] = r_j ; d[n-1+i] = T[i,0] = c_i


def toeplitz(seed, x, l, variant="diag"):
    """T x mod 2 by FFT convolution: n = 1e5, l = 5e4 in about a second; the dense matrix would have 5e9 entries."""
    x = np.asarray(x, np.uint8)
    n = len(x)
    d = toeplitz_diagonals(seed, n, l, variant).astype(np.float64)
    c = fftconvolve(d, x.astype(np.float64))                    # c[t] = sum_j d[t-j] x_j
    return (np.rint(c[n - 1: n - 1 + l]).astype(np.int64) & 1).astype(np.uint8)


def toeplitz_dense(seed, x, l, variant="diag"):
    """Slow reference with an explicit matrix (small n only), used by the tests."""
    n = len(x)
    d = toeplitz_diagonals(seed, n, l, variant).astype(np.int64)
    T = np.array([[d[i - j + n - 1] for j in range(n)] for i in range(l)], np.int64)
    return (T @ np.asarray(x, np.int64) & 1).astype(np.uint8)


# ---- step 15: one-time pad -------------------------------------------------------------------------------------
def otp(data: bytes, key_bits, bitorder="big"):
    """XOR data with the first 8*len(data) key bits; never reuses or silently truncates a key."""
    need = 8 * len(data)
    if len(key_bits) < need:
        raise ValueError(f"key too short for one-time pad: have {len(key_bits)} bits, need {need}")
    pad = np.packbits(np.asarray(key_bits[:need], np.uint8), bitorder=bitorder).tobytes()
    return bytes(a ^ b for a, b in zip(data, pad))


def autodetect(cipher: bytes, seed, x, l, want=None):
    """Brief leaves the Toeplitz seed layout and bit->byte order open. Try all combinations; return
    (variant, bitorder, plaintext) of the first that decrypts to `want` (or to printable ASCII), else None."""
    for v in VARIANTS:
        key = toeplitz(seed, x, l, v)
        for bo in ("big", "little"):
            if 8 * len(cipher) > len(key):
                continue
            p = otp(cipher, key, bo)
            if (p == want) if want is not None else all(32 <= c < 127 or c in (9, 10, 13) for c in p):
                return v, bo, p
    return None
