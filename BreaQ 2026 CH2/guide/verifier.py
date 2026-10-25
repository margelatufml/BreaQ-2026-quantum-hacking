# Independent check: compare the SOURCE and the CANDIDATE as matrices. Fail closed on anything odd.
import math
from numbers import Real

def verify_compilation(source, candidate) -> bool:
    """True only if candidate = source up to a global phase (spectral-norm distance <= 1e-8) and both are
    plain bound circuits of equal width 1..6; the candidate may use only rz/sx/x/cx (+ barrier, id).
    Numerical check of a 2^n x 2^n matrix, not a proof. Never reads circuit names, metadata, counts or hashes."""
    lab = {"id", "h", "x", "y", "z", "s", "sdg", "t", "tdg", "sx", "sxdg", "rx", "ry", "rz",
           "p", "cx", "cz", "swap", "barrier"}                    # the lab's own allowed gates
    basis = {"rz", "sx", "x", "cx", "id", "barrier"}              # policy: id/barrier = no unitary effect, lab allows them

    def ok(qc, gates, max_ops):                                    # structure checks, no matrices yet
        if not isinstance(qc, QuantumCircuit) or not 1 <= qc.num_qubits <= 6:
            return False
        if qc.num_clbits or qc.num_ancillas or qc.parameters or qc.layout is not None:
            return False
        if len(qc.data) > max_ops or not math.isfinite(float(qc.global_phase)):
            return False
        return all(i.operation.name in gates and not i.clbits and
                   all(isinstance(p, Real) and math.isfinite(float(p)) for p in i.operation.params)
                   for i in qc.data)

    def plain(qc):                                                 # re-make every gate from (name, angles, wires) with Qiskit's own code
        out = QuantumCircuit(qc.num_qubits, global_phase=qc.global_phase)
        for i in qc.data:
            getattr(out, i.operation.name)(*i.operation.params, *[qc.find_bit(q).index for q in i.qubits])
        return out
    try:
        if not (ok(source, lab, 500) and ok(candidate, basis, 5000)):
            return False
        if source.num_qubits != candidate.num_qubits:
            return False
        u, v = Operator(source).data, Operator(candidate).data
        for qc, m in ((source, u), (candidate, v)):                # a fake gate object whose own matrix disagrees with its name+angle
            if not np.allclose(Operator(plain(qc)).data, m, atol=1e-12):
                return False
        z = np.vdot(u, v)                                          # tr(U^dagger V) gives the best global phase
        if abs(z) < len(u) / 2:
            return False                                           # far from any phase multiple of U
        return bool(np.linalg.norm(v - z / abs(z) * u, 2) <= 1e-8)  # tolerance: spectral norm <= 1e-8
    except Exception:
        return False                                               # fail closed


def guarded_compile(compiler, source, build="suspect"):
    try:
        pristine = source.copy()                                   # we verify against our own copy of the source,
        candidate = compiler.compile(source.copy(), build=build).copy()   # never the objects the compiler could edit
    except Exception as exc:
        raise ValueError("Compilation refused: compiler failed") from exc
    if not verify_compilation(pristine, candidate):
        raise ValueError("Compilation refused: integrity not established")
    return candidate
