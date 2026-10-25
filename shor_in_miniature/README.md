# Shor in Miniature (BreaQ 2026, Challenge 2)

Order-finding circuits for any odd composite N up to 6 bits, a classical driver `factor(N)`, tests, results for N = 15 and 21, and the Part B RSA-2048 estimate.

**Status (run on 2026-10-25, Qiskit 2.6.1, Aer 0.18.0):** `python test_shor.py` prints `ALL TESTS PASSED` (log in `results/test_output.txt`). What passes, what does not, and the known noise limit are listed under "Limitations".

## How to grade Level 2 and the bonus (read this first)

The brief does not say how Level 2 or the bonus is selected, so the default `build_shor(N, a)` is the safe, fast **Level 1** circuit. Exact calls:

| What to grade | Call | Qubits | Time for 2,000 shots |
|---|---|---|---|
| Level 1 (40 pts) | `build_shor(N, a)` | 15 for N=21 | seconds |
| Level 2 (+30 pts) | `build_shor_level2(N, a)` | 22 for N=21 | about 1 min for (21, 2) (56 s in the last test run) |
| Bonus, 6-bit N | `build_shor_semiclassical(N, a)` | 15 for N=63 | about 15 min (Aer runs it shot by shot) |
| Bonus, fewer qubits | `build_shor_semiclassical(N, a, gates=False)` | 7 for N=63 | about 2 s |
| Factoring | `factor(N)` (Level 1), `factor(N, level=2)` | | under 4 s |

If the harness uses another function name, that is a one-line alias in `shor.py`.

## How the judges call it

```python
from shor import build_shor, factor
qc = build_shor(21, 2)            # Level 1 circuit, 15 qubits, ends with measurements (classical register "c")
counts = AerSimulator().run(qc, shots=2000).result().get_counts()   # also works after transpile(), and with SamplerV2
p, q = factor(21)                 # (3, 7)
```

- **The circuit is already measured.** It ends with measurements of the counting register into the classical register `c`. Do **not** call `qc.measure_all()` on it: that adds a second register and the count keys become `"<12 bits> <8 bits>"`, so `int(key, 2)` is wrong. For an unmeasured circuit use `build_shor(N, a, measure=False)` (counting qubits are qubits 0 to 2n-1, register `count`) and add your own measurements.
- `build_shor(N, a)` receives only N and a (numpy integers are accepted). It raises `ValueError` if gcd(a, N) != 1.
- **Measured register:** only the counting register (qubits 0 to 2n-1). Qubit q is measured into bit q of one classical register `c`. Qiskit prints count keys with the most significant bit on the left, so `int(key, 2)` is exactly the phase-estimation integer y, and the peaks sit at y close to s * 2^(2n) / r. No swap gates are involved. Example: (15, 7) peaks at y = 0, 64, 128, 192 (keys `00000000`, `01000000`, `10000000`, `11000000`).
- `factor(N)` returns `(p, q)` with `p <= q` and `p * q == N`, both between 1 and N exclusive. It returns one non-trivial split, not the prime factorisation (`factor(45)` may return `(3, 15)` or `(5, 9)`, `factor(27)` returns `(3, 9)`). Prime N raises `RuntimeError`.
- Other entry points: see the table above.

## Levels, qubit counts, size

| Entry point | What it is | Qubits N=15 | N=21 | 6-bit (N=63) |
|---|---|---|---|---|
| `build_shor` (Level 1) | controlled multiplication by a^(2^j) mod N as permutation matrices (`UnitaryGate`), 2n counting + n work | 12 | **15** | 18 |
| `build_shor_level2` (Level 2) | multiplication from gates: Beauregard 2003 QFT adders, 2n counting + n work + (n+1) accumulator + 1 ancilla | 18 | **22** | 26 |
| `build_shor_semiclassical(N, a)` (bonus) | Level 2 arithmetic, ONE recycled control qubit (measure, reset, classically controlled phase) | 11 | 13 | **15** |
| `build_shor_semiclassical(N, a, gates=False)` | same recycled control, permutation-matrix multiplier | 5 | 6 | **7** |

Instruction counts are in `results/qubits_and_gates.txt` (N=63, a=2: Level 1 115 instructions, Level 2 22,183, semiclassical Level 2 22,194, semiclassical permutation 126; a `UnitaryGate` counts as one instruction). The semiclassical circuits use mid-circuit measurement and `if_test`, so they need Aer (dynamic circuits) and Aer simulates them shot by shot, which is much slower (see Limitations). They are not what the judges' default call returns.

## The algorithm in plain words

Factoring N reduces to finding the order r of a random a, the smallest r > 0 with a^r = 1 mod N. If r is even and a^(r/2) is not -1 mod N, then gcd(a^(r/2) - 1, N) is a factor. A quantum computer finds r by phase estimation: the operation U that maps x to a*x mod N has eigenvalues exp(2 pi i s/r) for s = 0..r-1, and the starting state |1> is an equal mix of all of those eigenstates. So measuring the counting register gives an integer y with y / 2^t close to s/r for a random s. Continued fractions turn y / 2^t into a fraction with a small denominator, which is r or a divisor of r. Several shots are combined with the least common multiple. The circuit is: Hadamards on 2n counting qubits, work register set to 1, counting qubit j controls multiplication by a^(2^j) mod N, inverse QFT, measure the counting qubits. The constants a^(2^j) mod N are computed classically (allowed and expected). 2n counting qubits give 2^(2n) >= N^2, which is what continued fractions need.

## How each forbidden practice is avoided

| Forbidden | What the code does | Where it is checked |
|---|---|---|
| Receiving or computing r in `build_shor` | the builders take (N, a) only; they call `mult_constants` (a^(2^j) mod N) and, at Level 2 only, `pow(a, -1, N)` (modular inverse, needed by Beauregard's cleanup) | `test_shor.py` section G parses `shor.py`: functions reachable from the builders do not reach `factor`, `order_from_shots`, `run_shots` or `perfect_power`, contain no name with "order"/"period", no `while` loop, and only 3-argument `pow` |
| Hard-coding which work-register states occur / circuit tailored to r | no identity blocks are skipped; every (N, a) of the same bit length gives the same gate sequence on the same qubits, only matrix entries change | section G: one single circuit shape for all 5-bit (N, a), orders 1 to 20 |
| Choosing a or the circuit by looking N up | `factor` draws `a` with `random.randrange`; no table indexed by N exists | read `factor` (about 30 lines) |
| Classical order finding in `factor` | `factor` runs the circuit, applies continued fractions (denominator < N), LCM over shots, and checks a^r = 1 mod N. Two guards make sure the order really comes from the circuit: (1) a **support check**: the recovered r must be consistent with at least 50% of ALL shots (the continued-fraction denominator of the shot divides r; y = 0 counts), which real circuit output satisfies (at least 75% in 32,800 simulated 20-shot batches) and random numbers do not; (2) `_strip` divides out primes p while a^(r/p) = 1 still holds on an already verified multiple (at most log2(r) modular powers, no search for r) | section F: with only coprime a offered, every non-prime-power N up to 63 needs the circuit; **with the circuit's samples replaced by uniform random numbers `factor` succeeded 0 times in 100 forced-coprime runs (10 values of N, 10 runs each)** (and with all-zero samples it fails); random 20-shot batches were accepted as an order in 6 of 6,560 cases (0.09%), the circuit's batches in 100% |
| Classical shortcuts that are allowed | even N, perfect powers, gcd(a, N) > 1 are handled classically (standard Shor steps; for N = p^k the quantum reduction can never succeed) | `factor` |

## Tests and results

Run `python test_shor.py` (about 5 to 9 minutes, 8-core laptop; `--full` adds all a for N=21 at Level 2 and the 6-bit semiclassical run, about 1 hour). Real output: `results/test_output.txt`. All of these passed in the final run:

- A: the QFT is the DFT with bit reversal, consistent with Qiskit's `QFTGate` up to its swap layer.
- B: Level-2 blocks against classical arithmetic for every input: `phi_add` (15,680 inputs, 0/1/2 controls, add and subtract), `phi_add_mod` (N=15, 21, all a, b, controls, ancilla returns to 0), CMULT and controlled-U_a (N=9, 15, 21, every x < N, all coprime a, control 0 and 1, work/accumulator/ancilla clean).
- C: **Level 1, every 4-bit (9, 15), 5-bit (21, 25, 27) and also 6-bit odd composite N and every coprime a (including a = 1): the circuit's exact statevector distribution equals the independent textbook ideal P(y) = (1/r) sum_s |2^-t sum_x exp(2 pi i x (s/r - y/2^t))|^2 with TV <= 2.3e-13.** The ideal is computed in the test with the true r (the test may, the builder may not) and cross-checked against the literal double sum. The judge-style 2,000-shot test (seeded) gives TV < 0.1 for 63 of 64 4- and 5-bit (N, a) cases; the exception is N=27, a=23 (r=18) with TV 0.1008, a noise effect explained below. Negative controls: reversed bit order gives TV 0.755 for (15,7) and 0.542 for (21,2); work register not set to 1 gives 0.750 and 0.833, so the test can fail.
- D: **Level 2, (15,7) and (21,2): exact TV 5e-15 and 6e-14; 2,000-shot TV 0.012 and 0.045**; also all other a for N=15 and N=9 (shot TV below 0.05).
- E: semiclassical: (15,7), (21,2), (35,2), (63,2) with the permutation multiplier and (15,7), (21,2) with Beauregard, 2,000 shots, TV <= 0.063. The 6-bit, 15-qubit case is reported separately below.
- F: `factor(N)` correct for every odd composite N up to 63 at Level 1 (also with the quantum path forced), and Level 2 `factor(15)`, `factor(21)`. Anti-cheat controls: with circuit samples replaced by all zeros or by uniform random numbers, `factor` never succeeds (0 of 100 runs for random numbers); uniform random 20-shot batches are accepted as an order in 6 of 6,560 cases, the circuit's batches in 6,560 of 6,560.

Results table for N = 15 and N = 21 with every coprime a (true order, recovered order, TV, top outcomes, factors) and the histograms: `results/results.md`, `results/hist_L1_N15.png`, `hist_L1_N21.png`, `hist_L2_N15.png`, `hist_L2_N21.png` (script: `make_results.py`). Summary: the recovered order equals the true order for every a at both levels (7/7 for N=15, 11/11 for N=21, both levels); a gives factors for 6/7 (N=15) resp. 6/11 (N=21) of the coprime a >= 2, the rest fail for the classical reasons Shor predicts (odd r, or a^(r/2) = -1 mod N), and 6 resp. 8 values of a share a factor with N. The measured TV values (N=15: at most 0.019; N=21: at most 0.073) are shot noise: the exact TV of the same circuits is 1e-13.

## Limitations (honest list)

- **Shot-noise floor of the distribution test.** With 2,000 shots even a perfect circuit has TV > 0 against the ideal, and for large orders the ideal is spread over many y values. We drew 2,000 shots from the exact ideal distribution (no circuit involved) for every odd composite N <= 63 and every coprime a >= 2, 300 trials each (`python noise_table.py`, full table in `results/noise_floor_per_N.md`). N = 9, 15, 21, 33, 35, 39, 45, 51 and 63 never fail. The risky ones:

  | N | bits | mean P(a perfect circuit fails TV < 0.1) over all a | worst a | worst P(fail) |
  |---|---|---|---|---|
  | 25 | 5 | 2.5% | a=22 (r=20) | 8.7% |
  | 27 | 5 | 0.8% | a=2 (r=18) | 4.0% |
  | 55 | 6 | 2.7% | a=2 (r=20) | 8.3% |
  | 57 | 6 | 0.9% | a=52 (r=18) | 3.0% |
  | 49 | 6 | 32.3% | a=47 (r=42) | 100% |

  So a correct circuit can fail the judges' test by chance on some 5-bit cases, and a hidden 6-bit case with order 42 (N=49: the 12 of 41 values of a with order 42 fail more than half the time) cannot pass with 2,000 shots. The seeded run in this repo has one such case: N=27, a=23 (r=18), TV 0.1008 with exact TV 1e-14. We did not "fix" this; it is not a circuit error.
- **Level 2 is slow.** N=21 has 22 qubits and 12,286 instructions; in the last test run the (21,2) distribution check (one exact and one 2,000-shot run) took 56 s and the two Level 2 `factor` calls (N=15 and N=21) 30 s together. 6-bit Level 2 needs 26 qubits (1 GB statevector) and was not run end to end; its building blocks are tested for N <= 21 only.
- **Semiclassical circuits** need dynamic circuits and are simulated per shot. Timing and the 6-bit result are in the next section (922 s for 2,000 shots at 15 qubits).
- `factor` returns one non-trivial split `(p, q)`, not prime factors, and raises `RuntimeError` for prime N (not in scope).
- Ideal simulator only. No hardware noise was tried. `UnitaryGate` permutation matrices are an oracle-style Level 1 answer, as the brief defines it; we ran them on Aer directly and after `transpile(qc, AerSimulator())`, but did not decompose them into basis gates.
- The brief says nothing about how Level 2 is selected by the judges, so we expose `build_shor_level2(N, a)` and `factor(N, level=2)`; if the judges call a different name, that is a one-line alias.

## Bonus: 15 qubits for a 6-bit N

`build_shor_semiclassical(63, 2)` has **15 qubits** (one recycled control, 14 for the Beauregard arithmetic). Run with 2,000 shots on Aer (`python -c "import test_shor as t; t.FULL=True; t.test_semiclassical()"`, log `results/semiclassical_6bit_output.txt`): **TV 0.051 against the ideal distribution, 922 s** for the 2,000 shots (about 15 minutes, shot by shot; the same machine took about 1 s for the 18-qubit Level 1 circuit). The permutation-matrix variant `gates=False` has 7 qubits for 6-bit N and takes about 2 s for 2,000 shots (TV 0.051 for (63,2)). The brief's bonus is stated as 15 qubits; we have not checked how the judges score fewer.

## Part B

`PART_B.md` (also as `PART_B.pdf`: A4, 11 pt, 2 pages) and `part_b.py` (prints every number used; `python part_b.py`, standard library only; output in `results/part_b_output.txt`). Sources were checked with the arXiv API and by reading the paper texts: Gidney 2025 (arXiv:2505.15917), Gidney and Ekera 2019 (1905.09749), Pinnacle v2 Table VI (2602.11457), Google Quantum AI (2603.28846), Helios (2511.05465), Willow (2408.13687), 6,100-atom tweezer array (2403.12021, abstract only). It reproduces the judges' example (d = 29, 1,682 physical per logical, 2.52 M total). The hardware comparison uses the lowest verified two-qubit error on about 100 qubits (Helios, 98 qubits), the largest verified array (6,100 atoms, qubit count only, gap 147x for Gidney's 897,864) and a clock-speed note for slow-clock machines (an illustrative 1 ms cycle, not a measured number). The IBM Condor 1,121-qubit figure and the NIST standards are quoted from knowledge, not fetched.

## Files

| File | Purpose |
|---|---|
| `shor.py` | `build_shor`, `build_shor_level2`, `build_shor_semiclassical`, `factor` (one file, no test helpers) |
| `test_shor.py` | all tests (uses the true order only for the ideal distribution) |
| `make_results.py` | results tables and histograms for N=15, 21 |
| `results/` | `results.md`, histograms, `test_output.txt`, `qubits_and_gates.txt`, semiclassical logs |
| `PART_B.md`, `PART_B.pdf`, `part_b.py` | Part B estimate (PDF: A4, 11 pt, 2 pages, made with the command under "How to run") and its arithmetic |
| `noise_table.py` | failure rate of a perfect circuit at 2,000 shots, per N (`results/noise_floor_per_N.md`) |
| `requirements.txt` | pinned versions that were used |

## How to run

```
python -m venv .venv && .venv/bin/pip install -r requirements.txt     # do NOT create the venv inside an iCloud-synced folder
python test_shor.py          # about 5-9 min
python make_results.py 1     # Level 1 table and histograms, seconds
python make_results.py 2     # Level 2, about 15 min
python part_b.py
python noise_table.py     # about 40 s
# Part B PDF: pandoc PART_B.md -f gfm -t html5 -s --metadata title="Part B" -c results/part_b.css -o part_b.html && weasyprint part_b.html PART_B.pdf
```

## AI assistance

The code and text were drafted with an AI assistant (Claude) and verified by running them: every claim above has a command and an observed output in `results/` or in the commands listed here. The team must be able to explain every step orally; the plain-words section and the comments in `shor.py` are written for that. Ideas reused: Shor 1994, Beauregard 2003 (arXiv:quant-ph/0205095), Griffiths and Niu 1996 (quant-ph/9511007), Draper 2000 (quant-ph/0008033); no code was copied from other teams.
