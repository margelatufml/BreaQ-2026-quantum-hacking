# Minimal reproducer + observable witness. Run the trigger cell first: this cell uses its low, high (measured interval).
import itertools
def build(ops, n):
    qc = QuantumCircuit(n)
    for op, q in ops: qc.append(op, q)
    return qc
def text(c): return [f"{i.operation.name}{'(%.3f)' % i.operation.params[0] if i.operation.params else ''} q{[c.find_bit(q).index for q in i.qubits]}" for i in c.data]
def prop(qc):
    """(suspect output NOT equivalent to source, baseline output equivalent to source)."""
    return (not Operator(qc).equiv(Operator(service.compile(qc, build="suspect"))),
            bool(Operator(qc).equiv(Operator(service.compile(qc, build="baseline")))))

# 1. Greedy minimization from SCAN-B: delete one instruction, keep the deletion only if the property still holds.
minimization_criterion = "keep a deletion only if the suspect output is NOT equivalent to the source AND the baseline output IS (Operator.equiv, up to global phase)"
src = workloads["SCAN-B"]
ops = [(i.operation, tuple(src.find_bit(q).index for q in i.qubits)) for i in src.data]
deletions_tried, n_pass, changed = [], 0, True
while changed:
    n_pass, changed, i = n_pass + 1, False, 0
    while i < len(ops):
        trial = ops[:i] + ops[i + 1:]
        bad, good = prop(build(trial, src.num_qubits))
        name = text(build([ops[i]], src.num_qubits))[0]
        deletions_tried.append({"pass": n_pass, "index": i, "deleted": name, "suspect_equiv": not bad, "baseline_equiv": good, "kept": bad and good})
        print(f"pass {n_pass} #{i}: delete {name:16} suspect_equiv={not bad!s:5} baseline_equiv={good!s:5} -> {'KEPT' if bad and good else 'rejected'}")
        if bad and good: ops, changed = trial, True
        else: i += 1

# 2. Rebuild on the fewest qubits, theta = middle of the measured interval, and check it is 1-minimal.
used = sorted({q for _, qs in ops for q in qs})
ops = [(op, tuple(used.index(q) for q in qs)) for op, qs in ops]
assert [(o.name, q) for o, q in ops] == [("cx", (0, 1)), ("rz", (1,)), ("cx", (0, 1))], "unexpected survivor"
theta = (low + high) / 2
minimal_source = QuantumCircuit(len(used)); minimal_source.cx(0, 1); minimal_source.rz(theta, 1); minimal_source.cx(0, 1)
bad, good = prop(minimal_source)
assert bad and good and not any(all(prop(build(ops[:k] + ops[k + 1:], 2))) for k in range(3))
lib = [(g, (q,)) for g in ("h", "x", "sx", "s", "rz") for q in (0, 1)] + [("cx", (0, 1)), ("cx", (1, 0))]
def mk(seq):
    qc = QuantumCircuit(2)
    for g, q in seq: qc.rz(theta, *q) if g == "rz" else getattr(qc, g)(*q)
    return qc
smaller = [s for k in (1, 2) for s in itertools.product(lib, repeat=k) if all(prop(mk(s)))]
n_smaller = sum(len(lib) ** k for k in (1, 2))
print("minimal_source:", text(minimal_source), f"theta={theta:.6f} suspect_equiv={not bad} baseline_equiv={good}")
print(f"all 3 single deletions fail the property; {len(smaller)} of {n_smaller} circuits with 1-2 instructions (12-gate library) satisfy it")

# 3. Witness: the TESTER adds prep and analysis AFTER compilation (the compiler never sees them).
prep = QuantumCircuit(2); prep.h(0); prep.s(0)       # control -> |+i>, target stays |0>
ana = QuantumCircuit(2); ana.h(0)                     # turns the control's relative phase into a population
witness = lambda c: prep.compose(c).compose(ana)
cand = {b: service.compile(minimal_source, build=b) for b in ("baseline", "suspect")}
P0 = lambda p: sum(v for k, v in p.items() if k[-1] == "0")   # P(q0 = 0); last character of the string is q0
ideal = exact_probabilities(witness(minimal_source))
exact = {b: exact_probabilities(witness(c)) for b, c in cand.items()}
shots, shot_seed = 4096, 5                                       # sampling seed: free choice, not the instance seed
counts = {b: sample_counts(witness(c), shots=shots, seed=shot_seed) for b, c in cand.items()}
norm = lambda d: {k: v / sum(d.values()) for k, v in d.items()}
zero_tv = total_variation(exact_probabilities(cand["baseline"]), exact_probabilities(cand["suspect"]))
tv_exact, tv_sampled = total_variation(exact["baseline"], exact["suspect"]), total_variation(*map(norm, counts.values()))
assert zero_tv < 1e-9, "the bare circuit should be invisible from |00>"
assert np.isclose(tv_exact, abs(np.sin(theta)), atol=1e-9) and np.isclose(P0(exact["baseline"]), (1 - np.sin(theta)) / 2)
print(f"bare minimal_source from |00>: TV(baseline, suspect) = {zero_tv:.1e}  (no difference)")
print(f"witness P(q0=0): source {P0(ideal):.4f}, baseline {P0(exact['baseline']):.4f}, suspect {P0(exact['suspect']):.4f}; formula (1-sin t)/2 = {(1-np.sin(theta))/2:.4f}")
print(f"witness exact TV = {tv_exact:.6f}, |sin theta| = {abs(np.sin(theta)):.6f}; sampled TV ({shots} shots) = {tv_sampled:.4f}")
print("counts baseline:", counts["baseline"], "| suspect:", counts["suspect"])

reproducer_evidence = {
    "theta": float(theta), "interval_used": [float(low), float(high)], "minimal_source_instructions": text(minimal_source),
    "suspect_equiv": not bad, "baseline_equiv": good, "minimization_start": f"SCAN-B workload ({len(src.data)} instructions, {src.num_qubits} qubits)",
    "minimization_criterion": minimization_criterion, "deletions_tried": deletions_tried,
    "smaller_circuits_satisfying": len(smaller), "smaller_circuits_checked": n_smaller,
    "witness": {"prep": "h(q0); s(q0): control in |+i>, target |0>", "analysis": "h(q0), then Z-measure",
                "applied": "tester composes prep + compiled candidate + analysis AFTER compilation, outside the submitted subroutine"},
    "zero_input_tv": float(zero_tv), "witness_exact_tv": float(tv_exact), "abs_sin_theta": float(abs(np.sin(theta))),
    "witness_p_q0_zero": {"source": float(P0(ideal)), "baseline": float(P0(exact["baseline"])), "suspect": float(P0(exact["suspect"]))},
    "witness_sampled_tv": float(tv_sampled), "shots": shots, "sampling_seed": shot_seed, "witness_counts": counts,
    "instance_seed": service.seed, "label": "local simulation"}
assert json.dumps(reproducer_evidence, allow_nan=False)
