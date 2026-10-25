# BreaQ 2026 Quantum Hacking Track: our solutions

This repository is a copy of the official challenge repository ([RoQTeam/BreaQ-2026-challenges](https://github.com/RoQTeam/BreaQ-2026-challenges), Apache 2.0) with our solutions added. The original README follows below.

| Challenge | Where | Run | Result |
|---|---|---|---|
| Trust No Input (CH1) | `BreaQ 2026 CH1/01_trust_no_input.ipynb`, `submission.json` | open the notebook | completed notebook and exported submission |
| The Treacherous Transpiler (CH2) | `BreaQ 2026 CH2/02_treacherous_transpiler_completed.ipynb`, `guide/` | open the notebook | completed notebook |
| Quantum Dice: Random or Rigged? | `quantum_dice_simple/` (submitted version), `quantum_dice/` (earlier, larger version) | `python dice.py` | the replay check caught all 20 faulty services (980 / 1,000 batches) with 0 / 1,000 false alarms |
| Shor in Miniature | `shor_in_miniature/` | `python test_shor.py` | `factor(N)` correct for every odd composite N up to 63; Level 1, Level 2 and bonus circuits; Part B in `PART_B.md` and `PART_B.pdf` |
| Catch the Eavesdropper (BB84, Bob's side) | `bb84_bob/` | `python bob.py --qber 0.03 --eve 0.01 --seed 1` | a 42,856-bit key from 200,000 qubits, against a local simulated Alice |
| Explanations | `diagrams/` | open `diagrams/index.html` | one explained page per challenge |

Each solution folder has its own README with setup, results and limitations. Tested with Python 3.12 and Qiskit 2.6.1 (see each `requirements.txt`).

**AI assistance:** the code and documentation were developed with an AI assistant (Claude) and verified by running them; every number in the READMEs comes from a command in this repository. Every prompt given to the assistant during the hackathon is in [`BreaQ_my_prompts_2026-10-25.txt`](BreaQ_my_prompts_2026-10-25.txt).

---

# BreaQ 2026 — Quantum Hacking Track

**Explore. Question. Experiment.**

Welcome to the Quantum Hacking Track! Investigate suspicious quantum
workflows, explore quantum algorithms, and build experiments that test
security assumptions.

**24 hours · Teams of up to 3 · Beginners welcome**

## The Challenges

### Trust No Input
A quantum application returns suspicious reports. Trace the journey from
circuit to result, identify what went wrong, and propose a safer approach.

### The Treacherous Transpiler
Compilation should preserve a program’s meaning—but does it?
Investigate a mock compiler, design revealing experiments, and test
whether its output can be trusted.

### Quantum Dice — Random or Rigged?
An independent, open-ended mini-project. Build a simulated quantum
random-bit generator, investigate one possible weakness, and create
a small experiment or auditing tool.

**You can start here without completing either of the first two challenges.**

### Catch the Eavesdropper — BB84
Explore quantum key distribution and investigate how eavesdropping
can leave evidence. Build your conclusions from experiments.

### Shor in Miniature
Explore a small-scale version of Shor’s algorithm. Connect the quantum
computation to the classical reasoning and explain what your results mean.

### The Hardware Surprise
Something beyond the simulator awaits! Details and equipment instructions
will be revealed during the hackathon.

## Getting Started

- Read each challenge’s brief and setup instructions.
- Install its dependencies in a separate virtual environment when needed.
- Run the introductory examples before changing the code.
- Record your hypotheses, experiments, and observations.
- Ask a mentor when you need clarification or help getting unstuck.

## What Matters Most

**Understanding beats a perfect demo.**

- Support claims with reproducible evidence.
- Explain your assumptions and security model.
- Test your approach beyond a single successful example.
- Discuss failures and limitations honestly.
- Collaborate so everyone understands the team’s work.

At the end, present your results in a short oral presentation alongside
your notebooks or code. Be ready to explain your choices and answer questions.

**Partial progress with clear reasoning matters.**

## Keep It Safe

Experiment only with the provided local environments and explicitly
authorized equipment. Follow mentor instructions for hardware activities.
Do not test attacks against external services or other participants’ systems.

---

Stay curious. Challenge assumptions. Show your evidence.
