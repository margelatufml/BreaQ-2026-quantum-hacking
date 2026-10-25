import random, inspect
import importlib.util
from collections import Counter
from qiskit import transpile
from qiskit.circuit import AncillaRegister, Gate, Parameter, QuantumRegister
from qiskit.circuit.library import RZGate

trng = random.Random(7)                                    # test-suite seed: reproducible, unrelated to the instance seed
ONE = ["id", "h", "x", "y", "z", "s", "sdg", "t", "tdg", "sx", "sxdg"]
BASIS = service.contract["basis_gates"]

# ---- 1. Case builders: random lab circuits, and one-edit mutations of a legitimate candidate ----
def rand_circuit(n):                                       # random lab circuit, 4..14 steps
    qc = QuantumCircuit(n)
    for _ in range(trng.randint(4, 14)):
        r = trng.random()
        if n > 1 and r < 0.15:                             # cx-rz-cx motif (shape seen in the plugin code), random angle 0..1.2
            a, b = trng.sample(range(n), 2); qc.cx(a, b); qc.rz(trng.uniform(0, 1.2), b); qc.cx(a, b)
        elif n > 1 and r < 0.35:
            getattr(qc, trng.choice(["cx", "cz", "swap"]))(*trng.sample(range(n), 2))
        elif r < 0.5:
            getattr(qc, trng.choice(["rx", "ry", "rz", "p"]))(trng.uniform(-6.3, 6.3), trng.randrange(n))
        elif r < 0.55:
            qc.barrier()
        else:
            getattr(qc, trng.choice(ONE))(trng.randrange(n))
    return qc

def mutate(qc, kind):                                      # change ONE thing in a legitimate candidate
    pick = {"flip-rz-sign": "rz", "shift-angle-1e-3": "rz", "reverse-cx": "cx"}.get(kind)
    pos = [j for j, ins in enumerate(qc.data) if pick is None or ins.operation.name == pick]
    if not pos:
        return None
    j, out = trng.choice(pos), QuantumCircuit(qc.num_qubits, global_phase=qc.global_phase)
    for k, ins in enumerate(qc.data):
        op, q = ins.operation, ins.qubits
        if k == j and kind == "drop-gate": continue
        if k == j and kind == "flip-rz-sign": op = RZGate(-op.params[0])
        if k == j and kind == "shift-angle-1e-3": op = RZGate(op.params[0] + 1e-3)
        if k == j and kind == "reverse-cx": q = q[::-1]
        out.append(op, q)
    if kind == "add-x": out.x(trng.randrange(qc.num_qubits))
    return out

# ---- 2. Independent label: 8 random states, overlaps must all have modulus 1 and one common phase ----
def oracle_equal(src, cand, k=8):                          # resolves errors of about 1e-4 rad or more
    g, ov = np.random.default_rng(5), []
    for _ in range(k):
        v = g.normal(size=2 ** src.num_qubits) + 1j * g.normal(size=2 ** src.num_qubits)
        psi = Statevector(v / np.linalg.norm(v))
        ov.append(np.vdot(psi.evolve(src).data, psi.evolve(cand).data))
    return abs(np.mean(ov)) > 1 - 1e-10

# ---- 3. The case list (kind, source, candidate) and the invalid inputs ----
cases = []
for _ in range(20):
    src = rand_circuit(trng.randint(1, 4)); base = service.compile(src, build="baseline")
    ph = base.copy(); ph.global_phase += trng.uniform(-3, 3)
    cases += [("baseline", src, base), ("baseline+phase", src, ph), ("suspect-random", src, service.compile(src, build="suspect"))]
    cases += [(f"qiskit-opt{o}", src, transpile(src, basis_gates=BASIS, optimization_level=o, seed_transpiler=1)) for o in (0, 1)]
    for kind in ("flip-rz-sign", "shift-angle-1e-3", "drop-gate", "add-x", "reverse-cx"):
        if (m := mutate(base, kind)) is not None: cases.append(("mut:" + kind, src, m))
for s, c in zip(workloads.values(), compiled.values()):   # labels come from the oracle, never from names
    cases += [("suspect-workload", s, c), ("baseline-workload", s, service.compile(s, build="baseline"))]

class Fake(Gate):                                          # says "x" but its matrix is the identity
    def __init__(self): super().__init__("x", 1, [])
    def __array__(self, dtype=None, copy=None): return np.eye(2, dtype=complex)
one, two, big, hh, toff, long = (QuantumCircuit(n) for n in (1, 2, 7, 1, 3, 1))
one.x(0); two.x(0); two.x(1); big.x(0); hh.h(0); toff.ccx(0, 1, 2)
for _ in range(501): long.x(0)
meas = one.copy(); meas.measure_all()
par = QuantumCircuit(1); par.rz(Parameter("t"), 0)
nan = QuantumCircuit(1); nan.rz(float("nan"), 0)
fake = QuantumCircuit(1); fake.append(Fake(), [0])
lay = transpile(two, basis_gates=BASIS, coupling_map=[[0, 1], [1, 0]], initial_layout=[1, 0], seed_transpiler=1)
anc = QuantumCircuit(QuantumRegister(1), AncillaRegister(1)); anc.x(0); anc.x(1)
bad = [("width-mismatch", one, two), ("7-qubits", big, big.copy()), ("measurement", one, meas), ("clbits", one, QuantumCircuit(1, 1)),
       ("parameters", par, par.copy()), ("nan-angle", nan, nan.copy()), ("h-in-candidate", hh, hh.copy()),
       ("source-gate-outside-lab", toff, toff.copy()), ("501-instructions", long, long.copy()), ("not-a-circuit", one, None),
       ("string-source", "x", one.copy()), ("numpy-candidate", one, np.eye(2)), ("fake-x-gate", QuantumCircuit(1), fake),
       ("layout", two, lay), ("ancilla", two, anc)]

# ---- 4. Score: positive class = NOT equivalent ----
pos = [not oracle_equal(s, c) for _, s, c in cases]
refused = [not verify_compilation(s, c) for _, s, c in cases]
hits = Counter(zip(pos, refused))                          # (is it really different?, did we refuse it?)
TP, FN, TN, FP = hits[True, True], hits[True, False], hits[False, False], hits[False, True]
refused_invalid = sum(not verify_compilation(s, c) for _, s, c in bad)
by_kind = {k: {"n": n, "positives": sum(p for (kk, _, _), p in zip(cases, pos) if kk == k),
               "refused": sum(r for (kk, _, _), r in zip(cases, refused) if kk == k)} for k, n in Counter(k for k, _, _ in cases).items()}
print(f"cases={len(cases)} positives={TP + FN} negatives={TN + FP}  TP={TP} FN={FN} TN={TN} FP={FP}  invalid refused {refused_invalid}/{len(bad)}")
for k, v in by_kind.items(): print(f"  {k:20s}", v)
print("mutations the oracle says changed nothing:", [kk for (kk, _, _), p in zip(cases, pos) if kk.startswith("mut:") and not p])
agree = [(p == (not Operator(service.compile(s, build="baseline")).equiv(c))) for (kk, s, c), p in zip(cases, pos) if kk.startswith("suspect")]
print(f"oracle vs 'differs from trusted baseline' on suspect outputs: {sum(agree)}/{len(agree)} agree")
o0 = [r for (kk, _, c), r in zip(cases, refused) if kk == "qiskit-opt0" and "barrier" in c.count_ops()]
print(f"qiskit-opt0 outputs that carry a barrier: {len(o0)}, refused among them: {sum(o0)}")
o2 = [(s, transpile(s, basis_gates=BASIS, optimization_level=2, seed_transpiler=1)) for k, s, _ in cases if k == "baseline"]
lay2 = [(s, c) for s, c in o2 if c.layout is not None]     # Qiskit level 2 may elide a swap and record it as a layout
print(f"qiskit-opt2 outputs with a layout: {len(lay2)} of {len(o2)}; correct when layout-aware: "
      f"{all(Operator.from_circuit(c).equiv(Operator(s)) for s, c in lay2)}; refused by us (out of contract): {all(not verify_compilation(s, c) for s, c in lay2)}")

# ---- 5. Tolerance, the wrapper, and a hostile compiler ----
demo = QuantumCircuit(2); demo.sx(0); demo.cx(0, 1); demo.rz(0.7, 1)
def nudge(d): c = QuantumCircuit(2); c.sx(0); c.cx(0, 1); c.rz(0.7 + d, 1); return c
tolerance_demo = {f"{d:g}": verify_compilation(demo, nudge(d)) for d in (1e-10, 1e-9, 1e-8, 3e-8, 1e-7, 1e-3)}
print("angle error -> accepted?", tolerance_demo)

guard = {b: {"returned": [], "refused": []} for b in ("suspect", "baseline")}   # names are display text only
for name, s in workloads.items():
    for build in guard:
        try: guarded_compile(service, s, build=build); guard[build]["returned"].append(name)
        except ValueError: guard[build]["refused"].append(name)
for b, g in guard.items(): print(f"guarded_compile {b:8s} refused {g['refused']}  returned {g['returned']}")
tv = {n: round(total_variation(exact_probabilities(workloads[n]), exact_probabilities(compiled[n])), 3) for n in guard["suspect"]["refused"]}
print("Z-histogram TV of the refused outputs (0 = a histogram check would pass them):", tv)

class Hostile:                                             # compiler that also rewrites the caller's circuit to match its output
    def compile(self, qc, build="suspect"):
        out = service.compile(qc, build=build); qc.clear(); qc.compose(out, inplace=True); return out
target = workloads[guard["suspect"]["refused"][0]]         # a circuit the plugin really changes
edited = target.copy(); naive_accepts = verify_compilation(edited, Hostile().compile(edited))
try: guarded_compile(Hostile(), target); guarded_accepts = True
except ValueError: guarded_accepts = False
print(f"hostile compiler edits the source: checking against the edited source accepts={naive_accepts}, guarded_compile accepts={guarded_accepts}")

# ---- 6. Write the standalone submission file from the notebook function, load it back and compare ----
HEADER = ('"""Standalone verifier (BreaQ CH2): verify_compilation(source, candidate) -> bool, fails closed."""\n'
          "import math\nfrom numbers import Real\n\nimport numpy as np\nfrom qiskit import QuantumCircuit\nfrom qiskit.quantum_info import Operator\n\n__all__ = [\"verify_compilation\"]\n\n\n")
Path("submission_artifacts").mkdir(exist_ok=True)
Path("submission_artifacts/student_api.py").write_text(HEADER + inspect.getsource(verify_compilation), encoding="utf-8")
spec = importlib.util.spec_from_file_location("student_api", "submission_artifacts/student_api.py")
student_api = importlib.util.module_from_spec(spec); spec.loader.exec_module(student_api)
same = sum(student_api.verify_compilation(s, c) == verify_compilation(s, c) for _, s, c in cases + bad)
print(f"student_api.py (loaded from file) agrees with the notebook on {same}/{len(cases) + len(bad)} inputs")

defense_evidence = {"labels": "independent oracle: 8 random states, one common phase (not the verifier's method)",
                    "tolerance": "spectral-norm distance <= 1e-8 after best global phase", "n_cases": len(cases),
                    "TP": TP, "FN": FN, "TN": TN, "FP": FP, "invalid_inputs": [n for n, _, _ in bad], "invalid_refused": refused_invalid,
                    "by_kind": by_kind, "tolerance_demo": tolerance_demo, "guarded_compile": guard, "z_histogram_tv_of_refused": tv,
                    "hostile_source_edit": {"naive_accepts": naive_accepts, "guarded_accepts": guarded_accepts},
                    "student_api_agrees": f"{same}/{len(cases) + len(bad)}"}
verifier_limitations = [
    "Numerical check, not a proof: equal to within 1e-8 in spectral norm, so a single rotation error below about 2e-8 rad is accepted.",
    "Builds the full 2^n x 2^n matrix: fine for n <= 6, hopeless for useful sizes; it refuses n > 6 rather than guess.",
    "Fails closed: an equivalent candidate outside the contract (h gate, measurement, layout, ancillas, 7 qubits) is refused. "
    "Qiskit levels 2-3 can elide swaps and attach a layout; those correct outputs are refused too.",
    "Checks one compile of one circuit; a compiler could still act differently on the next run or on other inputs.",
    "Trusts local Qiskit (gate matrices, Operator) and the machine it runs on; an attacker controlling those wins.",
    "Only standalone unitary equality up to global phase; a global phase can matter if the circuit is later controlled.",
]
