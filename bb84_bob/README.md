# BB84 Blue Track: Bob's side ("Catch the Eavesdropper")

Bob's half of BB84: turn a noisy, possibly eavesdropped transmission into a shared secret key with a stated security
margin, or abort. Everything here runs against a **simulated** Alice (`alice_sim.py`). The organisers' API is not
published yet, so `bob.py` is written against a tiny transport interface and the real transport is a skeleton with TODOs.

Code was drafted with an AI assistant (Claude) and verified by running it: every number below comes from a command in
"How to run". The team must be able to defend it; section "Plain-words guide" is written for that.

## How to run

Python 3.12 with `numpy` and `scipy` (`pip install -r requirements.txt`). Run from this folder.

| What | Command | Time | Observed |
|---|---|---|---|
| Tests (plain asserts) | `python test_bb84.py` | 5 s | prints `ALL OK` |
| One Bob run, simulated Alice in-process | `python bob.py --qber 0.03 --eve 0.01 --seed 1` | 1 s | `abort None`, `leak_ec 18110`, `l 42856`, plaintext decrypts |
| Same over HTTP | `python alice_sim.py --port 8497 &` then `python bob.py --mode http --url http://127.0.0.1:8497 --qber 0.02 --eve 0.01 --seed 1` | 2 s | `abort None`, `l 51695`, `alice_report` success |
| Numbers quoted in "Strategy" | `python bounds_check.py` | 1 s | bound slacks and abort points |
| Experiments, 3960 runs | `python experiments.py --trials 30` | 6-8 min | writes `results/results.md`, `results/runs.csv` |

`--seed 1` makes Bob's random generator reproducible, for simulation only. **Without `--seed`, Bob draws his bases from OS entropy**
(`np.random.default_rng()`), so `l` varies by run (three runs gave 41691, 41731, 41280). `--mode organiser --seed ...` is refused,
so a real session can never run with a fixed seed. `--sim-seed` seeds only the simulated Alice and channel.

CLI flags beyond the basics: `--eps`, `--eps-pa`, `--q-abort`, `--bound`, `--cascade`, `--no-hash-leak` (Bob does not count hash
bits in `leak_EC`), `--sim-no-hash-leak` (simulated Alice does not either), `--auto-detect`, `--toeplitz-variant`.

## Formulas, transcribed from the brief (the formulas in the PDF are images; read from the rendered pages)

- Step 8, Hoeffding: `Q_u = Q_hat + sqrt( ln(1/eps) / (2k) )`
- Step 8, Clopper-Pearson: `scipy.stats.beta.ppf(1-eps, m+1, k-m)`
- Step 8: abort if `Q_u` exceeds about 11%. Code: `Q_ABORT = 0.11`.
- Step 14, key length: `l = n - n*h(Q_u) - leak_EC - 2*log2(1/eps_PA)`
- Step 14, binary entropy: `h(x) = -x*log2(x) - (1-x)*log2(1-x)`
- `Q_hat = m/k`; Cascade block length `b ~ 0.73/Q_hat`; `eps = eps_PA = "10^10"` in the brief.

**The brief's "10^10" can only mean 10^-10.** With 10^10, `ln(1/eps)` is negative (square root fails) and `beta.ppf(1-1e10, ...)` is
undefined; `test_bb84.py` asserts this. `2*log2(1/eps_PA) = 66.4386` bits.

## Step 1-15 to code map

| Brief step | Where | Notes |
|---|---|---|
| 1 Alice prepares and sends N qubits | `alice_sim.AliceSession.op_start`, `op_quantum` | simulation; the real quantum channel is an API TODO |
| 2 Bob picks random bases, measures | `bob.run_bob` ("steps 1-4") | in the sim Bob sends his bases and gets results back |
| 3 Alice sends her bases | op `alice_bases` | released only after Bob measured |
| 4 Bob sifts | `run_bob` | keeps positions where bases agree |
| 5-6 k test positions and bits exchanged both ways | ops `test`, `test_reply` | repeated random positions are counted once (`np.unique`) |
| 7 count mismatches, `Q_hat = m/k`, drop test bits | `run_bob` | `n = n_sift - k` bits go on |
| 8 bounds and abort | `bb84.q_hoeffding`, `q_cp`, `BOUNDS`; `run_bob` | abort leaks only the k test bits |
| 9 Cascade blocks, parity, bisection | `bb84.cascade`, `block_size` | Bob asks Alice for parities; every answer is counted |
| 10 random permutation between passes | op `permutation`, `cascade(get_perm=...)` | |
| 11 three passes, `leak_EC` | `run_bob`: `ledger["learned"]["parity"]` | |
| 12-13 hash check, at most 3 attempts | `bb84.verify_hash`, ops `verify`, `verify_result` | whole Cascade is repeated on a mismatch; 3rd mismatch discards the key |
| 14 key length `l`, abort if `l < 0` | `bb84.key_length`, `run_bob` | Bob also computes `l` himself and uses `min(l_Alice, l_Bob)` |
| 14 Toeplitz privacy amplification | `bb84.toeplitz` (FFT) | see "Toeplitz seed mapping" below |
| 15 one-time-pad the message | `bb84.otp` | pad shorter than the message raises, never reused |

## Toeplitz seed mapping (the brief says n and l random bits; a Toeplitz matrix needs n + l - 1)

`T` is an `l x n` matrix with `T[i,j] = d[i - j + n - 1]`, constant along diagonals, so it has `n + l - 1` free bits `d`. Final key = `T x mod 2`
for Bob's corrected key `x`. The default layout `diag` (`toeplitz_variant="diag"`) takes `d = seed[0 : n+l-1]`; **the last of the
`n+l` seed bits is unused**. The pad uses bit order `big` (first key bit is the top bit of byte 0). The brief does not say which
layout the organisers use, so there are 5 (`bb84.VARIANTS`): `diag`; `row_col` (first row = `seed[:n]`, first column below the corner =
the next `l-1` bits); `row_col_skip` (same, skipping one bit after the row); `col_row`, `col_row_skip` (column first, then row).
`run_bob(auto_detect=True)` tries all 5 layouts x 2 bit orders (`big`, `little`) and keeps the first that decrypts the ciphertext to
printable ASCII. FFT result equals an explicit dense matrix for all 5 layouts in the tests.

## Plain-words guide

1. Alice sends random bits in random "bases" (a basis is a way of measuring). Bob measures in random bases. Where the bases match
   (about half), Alice and Bob should hold the same bit; this is the *sifted key*.
2. Noise or an eavesdropper (Eve) makes some bits differ. They compare k random bits to estimate the error rate `Q_hat`, then
   convert it to a pessimistic bound `Q_u` that holds except with probability `eps = 1e-10`. Those k bits are thrown away.
3. Cascade finds and fixes the differing bits using only parities (XOR of a block of bits) sent in the open. Each parity bit
   tells Eve one bit about the key, so every parity is counted as leaked (`leak_EC`).
4. A short hash confirms both now hold the same key. If not, Cascade is repeated; the third failure discards the key.
5. Privacy amplification multiplies the key by a random Toeplitz matrix (a matrix constant along diagonals) and keeps `l` bits.
   `l` is what is left after charging for the errors (`n*h(Q_u)`), the parities, and a safety term. Eve's possible knowledge is
   squeezed out.
6. The final key one-time-pads the message.

Central lesson: noise and Eve look the same to Bob, so every error is charged as if Eve caused it. A negative `l` is therefore
not proof of Eve, only "no key can be certified".

## Plugging in the real API at the event

`bob.run_bob(transport)` only calls `transport.call(op, **payload) -> dict`. Ops and their keys are defined by `alice_sim.py`
(our invention): `start, quantum, alice_bases, test, test_reply, permutation, parity, verify, verify_result, privacy, message, finish`.
At the event, fill in `bob.OrganiserTransport` (all TODO, nothing guessed):

1. base URL, authentication, session handling;
2. route and JSON field name for each op (`to_wire` / `from_wire` translate to our dicts);
3. bit encoding (string, list, base64, hex) for bits, positions and permutations;
4. quantum step: if the server returns qubit states and not measurement results, Bob must measure locally (change `run_bob` step 2);
5. how Alice learns Bob's kept positions (the brief's step 4 does not say), the Toeplitz seed layout, the bit-to-byte order of the pad. Use `run_bob(..., auto_detect=True)`: it tries all 5 seed layouts x 2
   bit orders and keeps the one that decrypts to printable text;
5b. **the "pre-agreed" hash (step 12)**: `bb84.verify_hash` (first 40 bits of SHA-256) is our own invention. Write the organisers' hash as
   a function `(bits, nbits) -> str` in the format the server returns and call `run_bob(t, hash_fn=their_hash)`. If the hash is wrong,
   step 12 mismatches 3 times and the key is discarded after three full Cascade runs (test 11 shows this);
6. request size or rate limits (`max_batch` splits parity requests); there is no retry or resume after an HTTP error (a re-sent parity
   request would have to be idempotent on the server, which is unknown), so a transport error aborts the run;
7. if Alice's own `l` does not count the hash bits, Bob's `l` will be a few bits smaller. This is handled: Bob uses `min(l_Alice, l_Bob)`
   and truncates; Alice's key is then a longer prefix-compatible key (tested). Set `count_hash_in_leak=False` to match her exactly.

8. **Event-day check on the hash bits:** the brief says `leak_EC` is the parity bits exchanged. Bob counts the 40 hash bits per attempt as
   well. Run the first session both ways (default and `--no-hash-leak` / `count_hash_in_leak=False`), compare Bob's `l` with the `l` the
   server reports, and keep the setting where they are equal. A scorer that compares key lengths would fail Bob by 40 bits otherwise.
9. **Restart after an abort:** the brief says to discard the key and start over (`l < 0`, third hash mismatch). `run_bob` only returns
   the abort reason; starting a new session is the caller's decision. Check at the event whether a restart is allowed and scored.

Run `python test_bb84.py` again after plugging in (it uses the simulator, so it checks the logic, not the new transport).

## Leakage accounting (what is counted)

`run_bob` returns `res["ledger"]`; `alice_sim` keeps its own count; `test_bb84.py` asserts they are equal for every run.

- **Bob learns from Alice (counts toward leakage):** the k test bits (removed from `n`, not subtracted again), every Cascade parity
  (`leak_EC`), the hash bits (40 per attempt; counted in `leak_EC` by default).
- **Not counted, independent of the key:** Alice's bases, the permutations, the Toeplitz seed.
- **Bob reveals:** his N bases, the k test bits, the parity ranges he asks about (these locate errors, which are independent of the
  key bits), one hash verdict per attempt. Listed in `ledger["revealed"]`.
- Cascade is Bob-driven: Bob asks for the parity of a range and receives one bit. One parity per bisection level (the other half is
  block parity XOR first half), which is cheaper than the literal "parity of both halves" reading of step 9.3.

## Strategy

- **Bound:** Clopper-Pearson (default). Hoeffding adds a fixed 0.024 at k=20000 (0.034 at k=10000), CP only 0.007-0.012 at Q=3% (numbers in "Where the numbers come from"). CP gives about 3-12k more key bits
  (table 1 of `results/results.md`). Hoeffding also aborts at lower noise.
  If Alice computes `l` herself with her own bound, Bob's choice only matters when Bob's `l` is smaller.
- **Cascade:** block `b = round(0.73/Q_hat)` with `Q_hat` floored at 1e-3 (a test with no error would divide by zero), three passes.
  The brief's literal version (equal blocks, no back-tracking) fails the hash on attempt 1 in almost every run (mean 1.97-2.00 attempts) and is repeated: leak about 2.0 x
  Shannon with one parity per bisection level (about 2.6-2.8x if both halves get a parity, per the earlier verified analysis), `l` 28k at 3% noise. Default `backtrack` (blocks b, 3b, 9b, fixing a bit re-checks earlier passes) leaks about 1.09 x Shannon
  with a hash failure (and so a second full Cascade, costing key bits) only rarely: 0 of the 1440 runs of table 1, 1 of 600 extra runs at the worst setting (2% noise, Eve 1%, k=30000, Hoeffding): `l` 43k. Table 3 in `results/results.md`.
- **k:** if the server fixes k (step 5 says Alice generates it), nothing to choose. If it is a free parameter in 10000-30000, take 10000
  with CP (15000 only for Hoeffding at 4% noise). The unconstrained optimum is lower (5000-8000 for CP, 10000-14000 for Hoeffding).
- **Leakage score:** every parity Bob requests is logged, so efficient Cascade is both more key and a smaller logged leak.

## Results (simulated Alice; full tables in `results/results.md`; 30 trials per cell)

Final key length l (bits), mean over runs, CP, Eve 1%:

| noise | k=10000 | k=20000 | k=30000 |
|---|---|---|---|
| 1% | 67195 | 60967 | 53789 |
| 2% | 55731 | 50812 | 44962 |
| 3% | 45559 | 41864 | 37167 |
| 4% | 36420 | 33789 | 30123 |

- Abort rate was 0% in every cell of the typical range (1-4% noise, Eve 0-1%, k 10000-30000, both bounds).
- Abort starts near 9% noise (k=20000): Hoeffding 100% at 9%, CP 0% at 9%, 97% at 9.5% (23% via step 8, 70% via `l <= 0`, 3% because 0 < l is shorter than the 352-bit message and step 15 fails), 100% at 10%+.
- Eve at 1% costs about 2k key bits at 3% noise (43859 vs 41864 at k=20000, CP).
- Best k: table 4 of `results/results.md`.
- 3960 runs, 0 runs finished without abort but with a wrong decryption.

## Limitations (honest)

- **API unknown:** the real transport, hash, seed layout, byte order, and how Alice learns Bob's bases or kept positions are unverified guesses in the sim.
- **Noise and Eve are indistinguishable:** after sifting, intercept-resend on a fraction f is an extra bit-flip rate f/4. Bob cannot tell
  them apart and does not try; `l < 0` means "no certifiable key", not "Eve detected".
- **Noise model:** `Q` mixes both bases. If the server's "flip" is a physical X gate, X-basis qubits do not flip and the pooled
  error rate is half the Z-basis rate (tested: Z 6%, X about 0, pooled 3%). The formula then understates the error that matters. Bob
  stores `q_hat_by_basis` in the result and, if Z and X differ by more than 5 sigma, adds a line to `res["warnings"]` and prints it
  (`WARNING: error rate differs by basis ...`); it does not change `Q_u` (test 13).
- **Public channel authentication is assumed.** Without it, a man in the middle defeats everything; the brief does not cover it.
- **Statistics are not a full finite-key proof:** CP and Hoeffding bound an i.i.d. channel parameter, while the key bits are sampled
  without replacement (a Serfling-type correction would be needed, not in the brief). The brief's formula is followed as given.
- **Cascade is capped:** more than `n//4` fixes raises `CascadeError` and Bob aborts (a lying parity server cannot make him loop forever; test 12).
- **The hash is not a security feature:** 40-bit hash, false accept about 2^-40 per attempt, bits disclosed.
- **Toeplitz via floating-point FFT:** exact for n about 1e5 (checked against exact integer dot products on 50 random rows in the tests), not a proof for far larger n.
- Experiments use our simulator, whose channel and Cascade behaviour are our model of the organisers' server.

## Where the numbers come from

- Strategy numbers: `python bounds_check.py` (saved in this folder):
  Hoeffding slack 0.03393 / 0.02399 / 0.01959 for k = 10000 / 20000 / 30000; step-8 abort at `Q_hat` > 7.61 / 8.60 / 9.04% (Hoeffding)
  and 9.06 / 9.62 / 9.87% (CP); `1 - 2h(Q) = 0` at Q = 0.110028.
- Citations for the 0.73/Q block size and original Cascade: arXiv:1407.3257 (Martinez-Mateo et al., Demystifying Cascade) and
  arXiv:1307.7829 (Pedersen and Toyran, High Performance Information Reconciliation for QKD with CASCADE), both checked to exist with the arXiv tool.
