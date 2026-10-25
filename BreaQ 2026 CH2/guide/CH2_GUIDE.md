# CH2 "The Treacherous Transpiler" — guided walkthrough

**Completed notebook:** `02_treacherous_transpiler_completed.ipynb` has every cell filled. Open it and use Kernel → Restart Kernel and Run All Cells. The `%load` steps below are only for filling the original notebook yourself; read each block for what to expect and what to say.

**What it is.** A vendor compiler promises shorter circuits but changes the meaning of some programs. You prove it, find the trigger, shrink it to a reproducer, and build a gate that refuses bad output.
**Root cause (one sentence).** Pass `03:vendor-echo-balance` negates the angle of an `rz` (`rz(t)` becomes `rz(-t)`) that sits alone on the target wire between two identical `cx`, only when the angle is in a window 0.5 rad wide (seed 2026: [0.325, 0.825], from `0.25 + 0.025*(seed % 7)`).
**Why it hides.** The change is a relative phase: Z-basis counts, gate counts and depth look normal. Only a full-matrix comparison, or a trusted `|+i>` preparation plus an `h` after compiling, shows it.
**Level 1 (triage).** Compare source and compiled output on counts, state and full matrix; write the threat model.
**Level 2 (locate).** Snapshot each stage, find the first stage where the matrix changes (03), then find by experiment what triggers it. Then a 3-gate reproducer `cx; rz(t); cx` plus a witness.
**Level 3 (defend).** `verify_compilation` (matrix equal up to global phase, tolerance 1e-8) and `guarded_compile` (compile, verify, refuse). 208 labelled cases: 101 of 101 changes refused, 107 of 107 legitimate accepted.
**Extensions + submission.** Fine angle sweep, "gate count proves nothing", witness table; CSV/PNG evidence, claim sheet, `submission.json`.
**Time plan (about 4.5 h).** Setup 10 min. Level 1: 40. Level 2: 75. Reproducer: 40. Level 3: 60. Extensions + evidence: 30. Claims + submit: 20. Oral defense: rehearse 30. Pasting is about 30 min of this; the rest is reading and answering the "Think first" question.
**Rule.** Answer each "Think first" out loud before you run. Every member must be able to explain every block's jury line.

## Setup (once)
1. The cell files are already in `guide/` next to `02_treacherous_transpiler.ipynb`.
2. Open the notebook, select the `.venv` kernel, run the scaffold cells down to the "Warm-up" and `compiled = ...` cell as they are. The first Qiskit import can take a minute.
3. For each block below, in notebook order: put the cursor in the cell of that section, type the `%load` line, run once (it replaces the cell with the file), run again to execute. Cells depend on earlier ones: do not skip.
4. `team_instance.json` prints `DEMO-TEAM`: that is the file given to us. Keep it unchanged.

## Proof that it runs
Whole guided notebook (all 13 cells swapped in, Restart and Run All): seed 2026 executes with no errors in 67.7 s wall (31.4 s CPU) on a loaded Mac; seed 7 (a different instance, window [0.25, 0.75]) also executes with no errors in 78.0 s wall (32.0 s CPU). Nothing is hard-coded to a seed: values are measured.

---

## Level 1

### Level 1 — Incident triage — does the histogram move more than shot noise?
**Goal:** For each of the 8 workloads, compare source and compiled output by sampled and exact counts, and record what we saw as a hypothesis, not a conclusion.
**Think first:** Which workloads do you expect to differ, and is a different histogram enough to call the compiler dishonest?
**Paste:** `%load guide/triage.py` (then run the cell).
**You should see:**
```
{'case_id': 'CAL-BELL', 'sampled_tv': 0.014, 'noise_floor_p99': 0.08, 'exact_tv': 0.0}
{'case_id': 'SCAN-A', 'sampled_tv': 0.014, 'noise_floor_p99': 0.092, 'exact_tv': 0.0}
{'case_id': 'SCAN-B', 'sampled_tv': 0.533, 'noise_floor_p99': 0.092, 'exact_tv': 0.543835}
{'case_id': 'SCAN-D', 'sampled_tv': 0.043, 'noise_floor_p99': 0.094, 'exact_tv': 0.0}
{'case_id': 'SCAN-F', 'sampled_tv': 0.0, 'noise_floor_p99': 0.0, 'exact_tv': 0.0}
```
**What it means:**
- TV (total variation distance) is half the sum of |p - q| over outcomes: 0 means the same histogram, 1 means disjoint.
- `noise_floor_p99` is how far two 512-shot samples of the SAME distribution drift apart (99th percentile). Only SCAN-B (0.533) is far above it; the exact TV 0.543835 confirms it.
- The other seven look fine, but a histogram from one input and one basis is only an observation. Next cell: compare the full matrices.

**Jury line:** "Only SCAN-B moves beyond the shot-noise floor, but a matching histogram is an observation, not proof, so I compare unitaries next."

### Level 1 — Core investigation — a table for every workload, builds side by side
**Goal:** For each workload and for both builds, record gate count, depth, exact TV, fidelity from all-zero and full-unitary equivalence.
**Think first:** Which metrics will disagree? Predict one workload where the TV is 0 but the unitaries differ.
**Paste:** `%load guide/inspect.py` (then run the cell). The `baseline` rows are the control.
**You should see:**
```
{'case_id': 'SCAN-B', 'build': 'suspect', ..., 'exact_tv': 0.543835, 'fidelity_000': 0.704244, 'unitary_equiv': False}
{'case_id': 'SCAN-B', 'build': 'baseline', ..., 'exact_tv': 0.0, 'fidelity_000': 1.0, 'unitary_equiv': True}
{'case_id': 'SCAN-D', 'build': 'suspect', ..., 'exact_tv': 0.0, 'fidelity_000': 0.704244, 'unitary_equiv': False}
{'case_id': 'SCAN-F', 'build': 'suspect', ..., 'exact_tv': 0.0, 'fidelity_000': 1.0, 'unitary_equiv': False}
{'case_id': 'SCAN-F', 'build': 'baseline', ..., 'exact_tv': 0.0, 'fidelity_000': 1.0, 'unitary_equiv': True}
Histogram looks fine but unitary differs: ['SCAN-D', 'SCAN-F']
```
**What it means:**
- Three suspect outputs are wrong operators (SCAN-B, SCAN-D, SCAN-F). The baseline build is right on all 8, so the fault is in the suspect build.
- SCAN-D keeps TV 0 but fidelity 0.704; SCAN-F keeps TV 0 and fidelity 1.0 and is still a different unitary. So the Z histogram and the all-zero output state both miss it.
- Gate counts do not predict it: LEGACY-REDUNDANCY goes 6 to 0 gates and is correct; SCAN-F goes 4 to 4 and is wrong. (Fidelity: overlap between two states, 1.0 = same state.)

**Jury line:** "Full-unitary equivalence is the only metric that never missed: histogram and all-zero fidelity both pass SCAN-F, which is not equivalent."

### Level 1 — Threat-model worksheet — what we protect and whom we trust
**Goal:** State the asset, attacker, trust boundary and the property we verify.
**Think first:** Which claim is stronger, "same observed distribution" or "same standalone unitary", and which does the service contract require?
**Paste:** `%load guide/threat.py` (then run the cell).
**You should see:**
```
Stronger claim: 'same standalone unitary' (implies the same histogram for EVERY input and basis).
The contract requires the unitary claim; 'same observed distribution' is weaker.
```
**What it means:**
- Protected: the meaning of the program (compiled matrix = source matrix up to global phase). Attacker: one third-party plugin pass inside the compiler.
- Untrusted: compiler output, trace, stage names, stats. Trusted: our source circuit, local Qiskit math, local simulator, our notebook.
- Out of scope: more than 6 qubits, controlled use (global phase becomes visible), layout/ancillas, an attacker who controls our verifier.

**Jury line:** "We trust our source and local Qiskit math, we trust nothing the compiler reports, and we verify the strongest property: the same unitary up to global phase."

---


## Level 2

### Level 2 — Locate the first violation — take a snapshot after every stage
**Goal:** Get SCAN-B after each compiler stage, then look at the `rz` angle at stages 02 and 03.
**Think first:** The compiler has 4 stages (normalization, phase convention, vendor plugin, basis lowering). Which one do you suspect, and what would you compare to be sure (gate counts, or something else)?
**Paste:** `%load guide/trace.py` (then run the cell).
**You should see:**
```
00:input depth= 6 ops= {'h': 3, 'cx': 2, 'rz': 1, 'x': 1, 'sdg': 1}
01:normalization depth= 6 ops= {'h': 3, 'cx': 2, 'rz': 1, 'sdg': 1, 'x': 1}
02:phase-convention depth= 6 ops= {'h': 3, 'cx': 2, 'rz': 1, 'sdg': 1, 'x': 1}
03:vendor-echo-balance depth= 6 ops= {'h': 3, 'cx': 2, 'rz': 1, 'sdg': 1, 'x': 1}
04:basis-lowering depth= 8 ops= {'rz': 6, 'sx': 3, 'cx': 2, 'x': 1}
02:phase-convention
global phase: π/7
q_1: ┤ H ├┤ X ├┤ Rz(0.575) ├┤ X ├┤ Sdg ├┤ H ├
03:vendor-echo-balance
global phase: π/7
q_1: ┤ H ├┤ X ├┤ Rz(-0.575) ├┤ X ├┤ Sdg ├┤ H ├
```
**What it means:**
- Stages 00 to 03 have the same depth (6) and the same gate counts, so these self-reported numbers show nothing.
- The drawings differ in one number: the `rz` is 0.575 at stage 02 and -0.575 at stage 03. That is a lead, not a proof.
- The next cell checks it with operators (the full matrix of the circuit), not with drawings.

**Jury line:** "Depth and gate counts are identical up to stage 03, so they prove nothing; the drawings show one rz changing sign, and I then confirm it with operator comparisons."

### Level 2 — Locate the first violation — find the first transition that changes the unitary
**Goal:** Compare every snapshot with the previous one and with the source using `Operator.equiv` (same unitary up to a global phase), and name the first stage that breaks it.
**Think first:** Stage 02 adds a global phase and stage 04 rewrites every gate. Should either count as the violation? Re-read the contract in the notebook before you answer.
**Paste:** `%load guide/stage.py` (then run the cell).
**You should see:**
```
build    stage                   depth  equiv_prev  overlap_prev  phase_shift  equiv_source
suspect  02:phase-convention         6        True           1.0     0.448799          True
suspect  03:vendor-echo-balance      6       False      0.839192         None         False
suspect  04:basis-lowering           8        True           1.0          0.0         False
baseline 02:phase-convention         6        True           1.0     0.448799          True
baseline 04:basis-lowering           8        True           1.0          0.0          True
first bad snapshot index per workload: {'CAL-BELL': None, 'LEGACY-REDUNDANCY': None, 'SCAN-A': None, 'SCAN-B': 3, 'SCAN-C': None, 'SCAN-D': 3, 'SCAN-E': None, 'SCAN-F': 3}
rz (angle, wire) in each source: {... 'SCAN-A': [(0.1625, 1)], 'SCAN-B': [(0.575, 1)], 'SCAN-C': [(0.575, 0)], ... 'SCAN-E': [(1.075, 1)], ...}
gate count source -> compiled: {'CAL-BELL': (2, 4), 'LEGACY-REDUNDANCY': (6, 0), ... 'SCAN-F': (4, 4)}
rz (angle, wire) before [(0.575, 1)] after [(-0.575, 1)]; final output equivalent to source: False; last snapshot matches compile(): True
```
**What it means:**
- Stage 02 only shifts the global phase (0.448799 rad, which is π/7), and the contract allows that. Stage 04 rewrites the gates (depth 6 to 8) but keeps the operator. Stage 03 is the first transition where `equiv` is False: overlap 0.839192, which is cos(0.575) (1.0 would mean the same operator), and the `rz` goes 0.575 to -0.575.
- Controls: the baseline build has no stage 03 and equals the source at every stage. Only SCAN-B, SCAN-D and SCAN-F break. SCAN-A and SCAN-E have the `rz` angle outside the window found in the trigger cell, SCAN-C has it on wire 0, the control. Size does not predict it: LEGACY-REDUNDANCY goes 6 to 0 gates and is clean, SCAN-F goes 4 to 4 and is bad.
- Trust: where the break happens relies on the trace, which is service output and no attestation. Independent anchors: snapshot 00 equals our source, and the output of `service.compile` is not equivalent to the source. `equiv` uses atol 1e-8 and rtol 1e-5 by default, so it misses errors below about 1e-5 rad; a 0.575 rad flip is far above that.

**Jury line:** "Stage 02 only adds a global phase, which the contract allows, and stage 04 only rewrites gates; the first operator change is stage 03, where one rz flips from 0.575 to -0.575, and although the location trusts the trace, I show without it that the final output is not equivalent to the source."

### Trigger discovery — find what activates the plugin by black-box experiments
**Goal:** Build our own small circuits, compile them with the suspect build, compare each with its source, change one feature per row, and record prediction versus observation.
**Think first:** Which of these will break the output: `rz` on the control qubit, a gate between the cx and the `rz`, `p` instead of `rz`, or no H at the start? Write your guesses before you run.
**Paste:** `%load guide/trigger.py` (then run the cell; 5 to 30 s depending on machine load). The cell is long: read it in 5 parts (helpers, window search, feature table, several patterns, second instance).
**You should see:**
```
activation interval ~ [0.325000, 0.825000] rad, width 0.499999; grid step 0.01, edges bisected to 1e-6
seed 2029: interval ~ [0.400000, 0.900000], width 0.499999  (shift of lower edge +0.075000)
True | 2026 | rz on the control wire | pred False obs False
True | 2026 | x on target between cx and rz | pred False obs False
True | 2026 | x on control between (target wire untouched) | pred True obs True
True | 2026 | barrier inside the pattern | pred True obs True
True | 2026 | no input prep (no h) | pred True obs True
True | 2026 | rz split in two halves | pred False obs False
True | 2026 | two patterns, target 2 written first: the lower wire (1) is negated, not the earlier gate | pred True obs True
True | 2026 | measured edges equal the source rule | pred True obs True
all predictions matched: True (29 rows, 26.9s)
```
**What it means:**
- Window: the plugin acts only for an `rz` angle in [0.325000, 0.825000]. We swept [-2π, 2π) in steps of 0.01 and bisected both edges to 1e-6, so a window narrower than 0.01 could hide between grid points. With seed 2029 the window moves to [0.400000, 0.900000], same width.
- Shape: it needs `cx(a,b)`, `rz`, `cx(a,b)` with the `rz` on the target `b` and nothing else on that wire between them. Spectators, barriers (stage 01 removes them), the control wire and the input state do not matter. A gate in between, `p`, a split `rz`, `cz`, `-mid` and `mid+2π` do not trigger, so the same rotation written differently escapes it. Only one `rz` is flipped per compile: the lowest target wire.
- Source check (`breaq_ch2/service.py`): in `_EchoBalance.run` (lines 75-89), line 76 loops over wires, 79 needs cx-rz-cx, 81 the same qubits, 83 the wire is the cx target, 86 `lower <= angle <= upper`, 87 negates, 88 stops at the first match; `_profile` (lines 52-56) sets the window from `seed % 7`. All 29 rows agree. The three angle rows on the second instance use its measured window, so they only show that it is one sharp window; the check against the source rule is the independent one.

**Jury line:** "By changing one feature at a time we found that the plugin negates an rz only when its angle is in a window about 0.5 rad wide and it is the only gate on the target wire between two matching cx; the source code says the same, and the same search finds the shifted window on another seed."

### Minimal reproducer and observable witness — shrink SCAN-B to 3 gates, then make the fault visible
**Goal:** Delete instructions from SCAN-B one at a time until the smallest circuit that still triggers the fault remains, then show the fault with a preparation and analysis that the tester adds after compilation.
**Think first:** If you run the tiny circuit from the all-zero input and read the normal 0/1 counts, will the suspect and baseline builds differ?
**Paste:** `%load guide/repro.py` (then run the cell; a few seconds). Run the trigger cell first: this cell reads its `low` and `high`. The cell is long: read it in 3 parts (greedy deletion, shrink check, witness).
**You should see:**
```
pass 1 #0: delete h q[0]           suspect_equiv=False baseline_equiv=True  -> KEPT
pass 1 #0: delete cx q[0, 1]       suspect_equiv=True  baseline_equiv=True  -> rejected
pass 1 #1: delete rz(0.575) q[1]   suspect_equiv=True  baseline_equiv=True  -> rejected
pass 1 #2: delete x q[2]           suspect_equiv=False baseline_equiv=True  -> KEPT
minimal_source: ['cx q[0, 1]', 'rz(0.575) q[1]', 'cx q[0, 1]'] theta=0.575000 suspect_equiv=False baseline_equiv=True
all 3 single deletions fail the property; 0 of 156 circuits with 1-2 instructions (12-gate library) satisfy it
bare minimal_source from |00>: TV(baseline, suspect) = 0.0e+00  (no difference)
witness P(q0=0): source 0.2281, baseline 0.2281, suspect 0.7719; formula (1-sin t)/2 = 0.2281
witness exact TV = 0.543835, |sin theta| = 0.543835; sampled TV (4096 shots) = 0.5378
counts baseline: {'01': 3119, '00': 977} | suspect: {'01': 916, '00': 3180}
```
(The full log has 11 deletion attempts: 5 kept, 6 rejected. Only some lines are shown.)
**What it means:**
- Keep a deletion only if the suspect output is no longer equivalent to the source (`Operator.equiv`: same matrix up to a global phase) while the baseline output still is. Both `cx` and the `rz` must stay; `h`, `x` and `sdg` can go. Theta is the middle of the interval you measured, so no constant is hard-coded.
- From all-zero input the fault is invisible: TV is 0.0 (TV, total variation distance, is half the sum of |p - q| over outcomes; 0 means identical histograms). The fault turns `rz(theta)` into `rz(-theta)`, which shifts the phase between "qubits agree" and "qubits differ" by 2 theta. `|00>` is one "agree" state, so it only gets a global phase.
- The tester puts the control in `|+i>` (`h`, `s`: both outcomes equally likely, with a quarter-turn phase) and applies `h` after the candidate. P(q0=0) is 0.2281 (correct) against 0.7719 (suspect), and TV = |sin theta| = 0.543835. The compiler never sees these gates and `minimal_source` stays 3 gates. The sampled TV (0.5378) differs from the exact one only by finite-shot noise.

**Jury line:** "I deleted instructions one by one and kept a deletion only if the suspect still breaks equivalence while the baseline does not, which left `cx; rz(theta); cx` on 2 qubits; it is invisible from all-zero input, but a trusted `|+i>` preparation and an `h` after compilation give a total variation distance of |sin theta| = 0.544."


---

## Level 3

### Level 3 — Verification gate — the verifier and the guarded wrapper
**Goal:** write `verify_compilation(source, candidate)`: True only when the candidate is the same quantum operation as the source, up to a global phase. Then `guarded_compile`: compile, verify, and either return the candidate or refuse.
**Think first:** the compiler can fake its gate count, names, stats and trace. What can you still compute from the two circuits alone that it cannot fake?
**Paste:** `%load guide/verifier.py` (then run the cell).
**You should see:** nothing printed. The cell only defines the two functions. The next cell tests them.
**What it means:**
- Step 1, structure: same width 1 to 6, no classical bits, free parameters, layout or ancilla. Candidate gates only `rz sx x cx` (plus do-nothing `id`, `barrier`); `h`, `delay`, `measure` are refused even if equivalent. Each gate is rebuilt from its name and angle, so a fake gate with a hidden matrix is refused. Any error returns False (fail closed: when unsure, say no).
- Step 2, meaning: build the matrices U and V (`Operator`), take the global phase from `tr(U†V)`, accept only if `||V - phase*U||` (spectral norm: the largest stretch of the difference) is at most 1e-8. One rotation wrong by d moves it by about d/2, so errors below about 2e-8 rad pass. `Operator.equiv` defaults accept an `rz` error of 1e-5 rad (not 2e-5), so we set our own tolerance.
- Wrapper: the compiler gets a copy of the source. We verify against our untouched copy and return a frozen copy of the candidate.

**Jury line:** "We compare the full unitaries of source and candidate, align the global phase, and accept only if the matrix distance is at most 1e-8; anything outside the contract is refused."

### Level 3 — Verification gate — negative tests, false positives and the submission file
**Goal:** measure the verifier on labelled cases (legitimate rewrites, semantic changes, invalid inputs), test the wrapper, and write `submission_artifacts/student_api.py`.
**Think first:** if you flip the sign of one `rz` angle in a correct circuit, is the result always a different operation?
**Paste:** `%load guide/tests.py` (then run the cell; it takes a few seconds). The cell is long. Read it in 6 parts, each starts with a `# ----` line: case builders, oracle, case list and invalid inputs, score, tolerance and wrapper, submission file.
**You should see:**
```
cases=208 positives=101 negatives=107  TP=101 FN=0 TN=107 FP=0  invalid refused 15/15
  suspect-random       {'n': 20, 'positives': 7, 'refused': 7}
  qiskit-opt0          {'n': 20, 'positives': 0, 'refused': 0}
  mut:flip-rz-sign     {'n': 20, 'positives': 19, 'refused': 19}
  ... (12 kinds in all)
mutations the oracle says changed nothing: ['mut:flip-rz-sign']
oracle vs 'differs from trusted baseline' on suspect outputs: 28/28 agree
qiskit-opt0 outputs that carry a barrier: 6, refused among them: 0
qiskit-opt2 outputs with a layout: 2 of 20; correct when layout-aware: True; refused by us (out of contract): True
angle error -> accepted? {'1e-10': True, '1e-09': True, '1e-08': True, '3e-08': False, '1e-07': False, '0.001': False}
guarded_compile suspect  refused ['SCAN-B', 'SCAN-D', 'SCAN-F']  returned ['CAL-BELL', 'LEGACY-REDUNDANCY', 'SCAN-A', 'SCAN-C', 'SCAN-E']
guarded_compile baseline refused []  returned ['CAL-BELL', ..., 'SCAN-F']  (all 8)
Z-histogram TV of the refused outputs (0 = a histogram check would pass them): {'SCAN-B': 0.544, 'SCAN-D': 0.0, 'SCAN-F': 0.0}
hostile compiler edits the source: checking against the edited source accepts=True, guarded_compile accepts=False
student_api.py (loaded from file) agrees with the notebook on 223/223 inputs
```
**What it means:**
- Positive means "candidate is NOT equivalent": 101 changes all refused (FN 0), 107 legitimate cases all accepted (FP 0), 15 of 15 invalid inputs refused (incl. a fake `x` gate, a layout, an ancilla). Labels come from an independent oracle, not from names or from the verifier: 8 random input states, whose overlaps must all have modulus 1 and one phase (it sees errors of about 1e-4 rad or more). It catches the trap: `rz(pi)` with its sign flipped is the same operator up to phase (19 of 20 flips are real changes).
- Legitimate rewrites pass: baseline, extra global phase, Qiskit levels 0 and 1 (6 of 20 level-0 outputs carry a barrier and pass). Qiskit level 2 can elide a swap and record it as a layout (2 of 20): right when read layout-aware, but outside our contract, so refused (a stated limit). Error 1e-8 passes, 3e-8 is refused. Seeds 7, 2027, 3, 6, 11: FN 0 and FP 0 each time (TP 101, 101, 101, 100, 101).
- A histogram check passes SCAN-D and SCAN-F (TV 0): the error is a phase, visible only if a later gate rotates the basis (SCAN-B has `sdg; h`, TV 0.544). A compiler that edits the caller's circuit fools a check against the edited source (accepts=True) but not `guarded_compile` (False). Names are display text only. The cell writes `student_api.py` from the notebook function and reloads it: 223 of 223 answers match.

**Jury line:** "On 208 labelled cases we refuse 101 of 101 changes and accept 107 of 107 legitimate rewrites, and we refuse 15 of 15 invalid inputs; it is a numerical small-circuit check, not a proof."


---

## Extensions, evidence and submission

### Advanced extensions — three extra experiments (boundary, gate count, witness)
**Goal:** measure the trigger boundary on a fine grid, show that gate count and depth prove nothing, and show how a trusted witness reveals a change that the Z histogram hides.
**Think first:** if the plugin only fires inside an angle window, what should a plot of "difference a tester sees" against the angle look like?
**Paste:** `%load guide/ext.py` (then run the cell; 5 to 15 s depending on load; draws one plot).
**You should see:**
```
1. 600 rows, grid step 0.004: suspect/target breaks equivalence on [0.327, 0.823] (125 grid points); bisected edges [0.3250, 0.8250]; gaps +0.0020, +0.0020 (< step 0.004: True)
   baseline always equivalent: True | suspect with rz on control always equivalent: True
2. minimal_source: baseline (3, 3, {'cx': 2, 'rz': 1}) vs suspect (3, 3, {'cx': 2, 'rz': 1}): identical; unitary distance 0.5671, equivalent False
   suspect output has the same size/depth/ops as the trusted baseline output in 8 of 8 workloads; wrong ones: ['SCAN-B', 'SCAN-D', 'SCAN-F']
   same size AND depth as the SOURCE but wrong: ['SCAN-F']; ...
3. TV(baseline, suspect) by trusted preparation (rows) and analysis basis (columns):
   |+>   {'Z': 0.0, 'X': 0.0, 'Y': 0.543835}
   |+i>  {'Z': 0.0, 'X': 0.543835, 'Y': 0.0}
   zero-input TV 0.0e+00, unitaries equivalent False, witness (|+i>, then h) TV 0.543835 = |sin theta| 0.543835
```
The plot is flat at 0, jumps to `|sin theta|` (0.32 at the left edge, 0.73 at the right edge) inside the shaded window, and drops to 0 again. It is drawn from the rows read back from `submission_artifacts/trigger_sweep.csv` (600 rows), so file and picture are the same data.
**What it means:**
- The sweep pins each edge to one grid step (0.004 rad): the first and last hit sit 0.002 inside the edges 0.325 and 0.825 found by bisection. `rz` on the control wire and the baseline never trigger.
- Good and bad outputs have the same size, depth and gate counts in 8 of 8 workloads, yet 3 differ as operators; SCAN-F even keeps the source's size and depth. So counts prove nothing.
- Seen from `|0>` or `|1>`: nothing in any basis. From `|+>` only the Y basis sees the flip, from `|+i>` only X, and the size is `|sin theta|`: a phase becomes a probability only on the equator of the Bloch sphere.

**Jury line:** "Gate count, depth and the Z histogram were identical for the good and the bad output; only a trusted preparation and analysis, or the full unitary, shows the change."

### Evidence export — CSV files, plot and the standalone verifier file
**Goal:** save our measurements as files (not screenshots) and write `submission_artifacts/student_api.py`.
**Think first:** the scaffold says "copy your final implementation into that file manually"; what could go wrong with a hand copy?
**Paste:** `%load guide/export.py` (then run the cell).
**You should see:**
```
student_api.py: 2880 bytes, agrees with the notebook on 223/223 inputs; notebook names inside: []
exports ('local simulation'):
  comparison.csv                1119 bytes  16 rows
  defense_tests.csv            12060 bytes  223 rows
  stage_evidence.csv            3790 bytes  44 rows
  student_api.py                2880 bytes
  trigger_boundary.png         37697 bytes
  trigger_experiments.csv       2301 bytes  29 rows
  trigger_sweep.csv            51257 bytes  600 rows
```
**What it means:**
- Every CSV row carries `label = local simulation` and the instance seed. The scaffold helper `save_evidence_rows` is kept unchanged.
- The cell writes `student_api.py` from the notebook function itself (no hand copy), reloads it as a separate module and compares 223 answers. `notebook names inside: []` means no notebook name (`service`, `workloads`, ...) is in the file, so it stands alone.
- Open `submission_artifacts/student_api.py` once and read it. If you change `verify_compilation`, run this cell again.

**Jury line:** "All tables are CSV files written by the notebook and labelled local simulation, and our verifier file is generated from the notebook function and gives the same answers on 223 inputs."

### Claim sheet and contributions — what we claim, with proof, assumption and limit
**Goal:** write the security claim and six claims, each with evidence, assumption and limitation, plus who did what.
**Think first:** for each claim, which one experiment would change your mind?
**Paste:** `%load guide/claims.py` (then run the cell). Afterwards EDIT `member_contributions` in the cell.
**You should see:**
```
On this instance (seed 2026) the 'suspect' build is NOT contract-preserving: a vendor pass negates one rz angle in [0.325, 0.825] rad ... (03:vendor-echo-balance). The 'baseline' build preserved the unitary in 8 of 8 workloads. Our verifier ... refused 101 of 101 changed outputs and accepted 107 of 107 legitimate ones on our test set (local simulation). ...

claim_sheet: 6 claims, each with claim / evidence / assumption / limitation.
member_contributions: lines still to edit (contain REPLACE): 3
```
**What it means:**
- All numbers in the claims are read from your own variables, so on another instance seed they change by themselves.
- Replace the three `REPLACE` lines with real names and what each person did and can explain. Keep the AI-assistant line only if it is true; edit or delete it otherwise.
- `hints_used` lists all four hints because the AI assistant saw the hint cell. Edit it only if that is untrue.

**Jury line:** "Every claim names the experiment behind it, the trusted assumption, and where it stops being true."

### Submission contract — completion status and the final export
**Goal:** set `completion_status` from what exists and, only at the very end, write `submission.json`.
**Think first:** which of core, exploit and defense could you honestly tick right now, and which file proves each?
**Paste:** `%load guide/submit.py` (then run the cell). `EXPORT_SUBMISSION` stays `False` until the end.
**You should see (with `False`):**
```
completion_status: {'core': True, 'exploit': True, 'defense': True} | unresolved placeholders: True | hints_used: ['Hint 1 (Comparing meanings)', ...]
Scaffold mode: no submission exported.
```
**What it means:**
- Status is computed, not typed: core = 16 comparison rows, a first bad transition and stage evidence; exploit = a minimal source that fails on the suspect build, trigger rows and a witness; defense = `student_api.py` exists, no changed output was accepted (FN 0) and every invalid input was refused.
- At the very end: fix the `REPLACE` lines in the claims cell, rerun it, set `EXPORT_SUBMISSION = True` here and run. With a `REPLACE` left it stops with a `ValueError`. We tested it: `submission.json` (about 17 KB, exactly the 17 scaffold keys, loads with `json.load`).
- It also writes `submission_artifacts/minimal_source.qpy` and `submission_artifacts/extra_evidence.json` (extension, trigger, stage and triage evidence). Hand in the notebook, `submission.json`, `team_instance.json` and `submission_artifacts/`; set the flag back to `False` for a clean rerun.

**Jury line:** "The status flags are computed from files and variables that exist, not typed in, and the export refuses to run while any placeholder is left."


---

## Oral defense — short answers (numbers from our runs, seed 2026, local simulation)

**1. Why can two different-looking compiled circuits be equivalent?**
A gate sequence is only a spelling of an operator. `h` equals `rz(pi/2) sx rz(pi/2)` up to a global phase (warm-up: `Operator.equiv` True). LEGACY-REDUNDANCY goes from 6 gates to 0 and CAL-BELL from 2 to 4, both equivalent.

**2. Why are a matching Z histogram and a matching all-zero output state not enough?**
SCAN-D and SCAN-F have exact TV 0 and both are different operators. SCAN-D keeps the Z histogram but its output state differs: fidelity from all-zero 0.704. SCAN-F has no `h`, so from all-zero the flip is only a global phase: fidelity 1.0. The change is a relative phase, and it is seen only after a basis change (SCAN-B ends with `sdg; h`: TV 0.5438).

**3. Which pass first violated the contract? Is an untrusted trace an attestation?**
`02:phase-convention` to `03:vendor-echo-balance` (overlap 0.839; rz angle 0.575 becomes -0.575). The phase stage only shifts the global phase by 0.4488 (pi/7), allowed. No, the trace is service output. We anchor it: snapshot 00 equals our source, the last snapshot equals `compile()`, and the final output is not equivalent to the source.

**4. What input features activate the exploit and which counterexamples support it?**
An `rz` angle in [0.325, 0.825] rad on the target wire of `cx ... cx`, nothing else on that wire between them. Not triggered: rz on the control, a gate between rz and cx, `p` or split rz, angle outside by 1e-3. 29 of 29 predictions matched; seed 2029 moved the window to [0.400, 0.900]; fine sweep (600 rows, step 0.004) agrees.

**5. Does a relative sign change necessarily change every experiment?**
No. From `|0>` or `|1>` all bases give TV 0. From `|+>` only Y sees it, from `|+i>` only X, TV 0.5438 = |sin 0.575|. And flipping `rz(pi)` gives `rz(-pi)`, the same operator up to a global phase: of 20 random sign flips in our tests, 19 changed the unitary and 1 flipped an `rz(pi)` (no change).

**6. How does your verifier handle global phase, unsupported circuits, a wider circuit?**
It aligns the global phase with `tr(U^dagger V)` and accepts if the matrix distance is at most 1e-8, so added phases pass. Qiskit's own `Operator.equiv` is looser: it still says True for a 1e-5 rad error and False at 1e-4; our verifier is stricter (3e-8 rad is refused, 1e-8 accepted). It refuses 15 of 15 invalid inputs (width mismatch, 7 qubits, measurement, free parameter, NaN, fake gate, layout, ancilla) and fails closed on any error. On 208 cases: TP 101, FN 0, TN 107, FP 0.

**7. Would the comparison stay valid after qubit remapping or ancillas?**
No, we assume the same wire meaning. Qiskit level 2 turned 2 of 20 outputs into circuits with a layout (a swap elided): correct if read layout-aware, but we refuse them (out of contract). Ancillas are refused too. Fixing this needs a layout-aware comparison (`Operator.from_circuit`), not done here.

**8. What changes if the adversary controls the simulator or the verification environment?**
Everything: we trust local Qiskit, the machine and this notebook, so a verifier run there proves nothing. Inside our model a compiler that edits the caller's circuit is handled: checking against the edited source accepts (True), `guarded_compile` against our own copy refuses (False). Remedy outside this lab: an independent second checker on another machine.

### Presentation target (5 lines)
1. Diagram: source, then 4 stages, then candidate; stage 03 `vendor-echo-balance` marked red, with the independent verifier box beside it.
2. Reproducer: `cx rz(0.575) cx`, 3 gates; zero-input TV 0 but the unitary differs; the witness (`|+i>`, then `h`) shows TV 0.5438.
3. Number: trigger window [0.325, 0.825] rad (600-row sweep, step 0.004) and verifier TP 101, FN 0, TN 107, FP 0, invalid 15 of 15 refused.
4. Mitigation: `guarded_compile`: compile, check the full unitary up to global phase (1e-8), refuse otherwise; suspect refused 3 of 8 workloads, baseline 0 of 8.
5. Limit: numerical small-circuit check (2^n matrices, n at most 6), rotation errors below about 2e-8 rad pass, and it trusts local Qiskit and the machine.

---

## Submission checklist
Hand in (all in one folder, as in the notebook's "Submission contract"):
- [ ] `02_treacherous_transpiler.ipynb`, run top to bottom (Restart and Run All) with no error.
- [ ] `submission.json` (written by the submit cell; exactly the 17 scaffold keys).
- [ ] `team_instance.json`, unchanged.
- [ ] `submission_artifacts/student_api.py`: standalone, exposes exactly `verify_compilation(source, candidate) -> bool`, imports only Qiskit/NumPy/stdlib, no notebook names, no case labels. It must match the notebook verifier: the export cell regenerates it and prints `agrees with the notebook on 223/223 inputs; notebook names inside: []`. If you change `verify_compilation`, rerun the tests cell and the export cell.
- [ ] Evidence in `submission_artifacts/`: `comparison.csv`, `stage_evidence.csv`, `trigger_experiments.csv`, `trigger_sweep.csv`, `defense_tests.csv`, `trigger_boundary.png`, `minimal_source.qpy`, `extra_evidence.json`.

Before the final export:
- [ ] Replace the 3 `REPLACE` lines in `member_contributions` with real names and what each person did. Keep the AI-assistant line only if true; edit or delete it otherwise. Rerun the claims cell.
- [ ] `hints_used`: keep the four hints (the AI assistant saw them) unless untrue, and keep the AI-assistant line in `member_contributions`.
- [ ] Set `EXPORT_SUBMISSION = True` as the LAST step, run the submit cell once (it stops with `ValueError` while a `REPLACE` is left), check `submission.json` exists, then set it back to `False`.
- [ ] Every member can answer the 8 oral-defense questions above.
