# Quantum Dice: Random or Rigged? (minimal version, direction: the repeated batch)

All results are **local simulation**. Qiskit samples with a pseudorandom generator: we model a quantum-bit source, we do not produce physical quantum entropy, and these bits must not be used for passwords or keys.

## How to run

Tested on Python 3.12.13:

```bash
pip install qiskit==2.6.1 scipy==1.18.1 numpy==2.5.4
python dice.py
```

`dice.py` runs its self-checks, then prints the two tables below (about 3 seconds). All randomness comes from the documented seeds, so the numbers reproduce exactly.

## Research question and threat model

We will investigate whether **re-seeding the simulator with the same seed on every request** can cause **identical "random" batches across requests**, and whether **a cross-request replay check** can detect it.

| Item | Our answer |
|---|---|
| Protected property | Freshness: every request returns new bits |
| Fault (one bounded capability) | The service re-seeds the simulator with its fixed seed on every request (`Faulty.request`). A mock classical service bug, not a physical quantum effect |
| Trusted components | The one-qubit model (H on \|0>), Qiskit's `Statevector`, our auditor code |
| Auditor access | Bits only, in order, with request boundaries. No seeds, configuration or source code |
| Exclusions | Real hardware, physical entropy, device-independent certification, cryptographic security |

**Prediction:** this fault should break freshness across requests, while the fraction of ones should still look normal.

## The model

- **Clean quantum baseline:** one qubit starts in \|0>; a Hadamard gate prepares (\|0> + \|1>)/√2; measuring gives 0 or 1, each with probability \|1/√2\|² = 1/2 (Born rule). `Statevector.sample_memory(1024)` repeats the prepare-and-measure 1,024 times and keeps the order. A fair batch is not exactly half ones: 95% of batches land in 0.5 ± 0.031.
- **Clean service (`Clean`):** creates one random generator at start-up and keeps it, so each request continues the stream.
- **Faulty service (`Faulty`):** the same sampling code, but it re-seeds on every request, so requests 2, 3, ... replay request 1.
- **Control (self-check in `dice.py`):** with the same seed, the first batch of both services is identical, so the only difference is when the generator is created.

## The auditor

| Check | Question it answers | Assumption | Alarm rule | What it can miss |
|---|---|---|---|---|
| Frequency | Is the share of ones plausible for P(1) = 1/2? | Independent fair bits | Exact two-sided binomial test, p < 0.01: alarm if a batch has ≤ 470 or ≥ 554 ones (exact false-alarm rate 0.946%) | Anything that keeps the balance, including replays |
| Replay | Is this batch an exact copy of an earlier batch from the same service? | Two fresh 1,024-bit batches are equal with probability 2⁻¹⁰²⁴ | Any exact repeat | The first faulty request, partial or shifted replays, unique-but-predictable output |

## Evaluation on fresh data

Each seed is one service instance serving 50 requests of 1,024 bits, so each set is 1,000 batches per service. Inside one faulty instance all 50 requests are the same bits, so the faulty side has only **20 independent cases** per set. **Tuning set:** seeds 0-19. **Evaluation set:** seeds 1000-1019, fresh data not looked at before. Both thresholds were fixed a priori (the conventional 1% level; the exact-match rule has no parameter); the tuning set only checked their false-alarm rates, and nothing was changed after seeing results.

Evaluation set (actual output of `python dice.py`):

| Check | Clean batches: false alarms | Faulty batches: detections |
|---|---|---|
| Frequency | 13 / 1000 (1.3%) | 0 / 1000 (0%) |
| **Replay** | **0 / 1000 (0%)** | **980 / 1000 (98%)** |

Per faulty instance: replay flagged 20 / 20 instances from request 2 onward; frequency flagged 0 / 20. The clean false alarms (13 here, 8 in the tuning set) match the exact rate of 0.946%, about 9 expected per 1,000.

Tuning set: frequency 8 / 1000 false alarms, 0 / 1000 detections; replay 0 / 1000 false alarms, 980 / 1000 detections.

**Missed faulty batches:** all 20 replay misses are request 1 of each faulty instance (`replay misses by request position: {0: 20}`). A replay can only be recognized after the original has been seen once.

**Conclusion:** the prediction held. This fault passed our frequency check but failed the replay check: a balanced histogram did not reveal it.

## Recommended response

1. **Fix the root cause:** seed the generator once per service lifetime from OS entropy, never per request, and add a regression test that two requests must differ.
2. **Monitor:** run the replay check inside the service and stop serving bits when it fires.
3. **Detection is not repair:** every batch served since the bug appeared is compromised; notify consumers and regenerate anything derived from those bits.

## Limitations

- Simulation only; distinct seeds do not prove physical independence.
- One fault, one batch size, 20 instances × 50 requests per set: the faulty results rest on 20 distinct batches, so they are small-sample evidence.
- The replay check misses the first faulty request, partial or shifted replays, and output that is unique but predictable (for example seed = base seed + request number): nothing repeats, so it never fires.
- An alarm means "investigate", not "an attacker is present". **We do not claim** that passing our checks proves the output is quantum, random or cryptographically secure.

## Sources

1. IBM Quantum, `qiskit.quantum_info.Statevector` (`sample_memory`, `seed`): https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.quantum_info.Statevector
2. NIST SP 800-22 Rev. 1a, *A Statistical Test Suite for Random and Pseudorandom Number Generators* (statistical tests cannot certify cryptographic suitability): https://csrc.nist.gov/pubs/sp/800/22/r1/upd1/final
3. NIST SP 800-90B, *Recommendation for the Entropy Sources Used for Random Bit Generation* (health tests for entropy sources): https://csrc.nist.gov/pubs/sp/800/90/b/final

## Own work and assistance

- Reused: Qiskit `Statevector.sample_memory` and `seed` for sampling, SciPy `binomtest` for the frequency test.
- The code and this report were drafted with an AI assistant (Claude) and verified by running `dice.py`; the research question, fault choice and conclusions were reviewed by the team.
- **Team contributions (fill in before submitting):** who built the source and fault, who built the auditor and evaluation, who checked the sources and limitations.
