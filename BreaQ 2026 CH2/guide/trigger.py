# Black-box trigger hunt: own circuits -> service.compile -> Operator.equiv vs source. One feature per row.
# Source reading (breaq_ch2/service.py: _EchoBalance.run lines 75-89, _profile lines 52-56) only gives predictions; each row tests one.
# Operator.equiv uses atol 1e-8 / rtol 1e-5 by default; the flips below are >= 0.2 rad, far above that.
import tempfile, time
t0 = time.time()

def circ(*ops, n=3):
    qc = QuantumCircuit(n)
    for name, *args in ops: getattr(qc, name)(*args)
    return qc

def flips(svc, qc, control=False):
    """True if the suspect output breaks equivalence (and, with control=True, the baseline does not)."""
    bad = not Operator(qc).equiv(Operator(svc.compile(qc, build="suspect")))
    return bad and (not control or Operator(qc).equiv(Operator(svc.compile(qc, build="baseline"))))

def discover(svc, a=2 * np.pi, step=0.01):
    """Grid-sweep the angle of cx(0,1) rz(angle,1) cx(0,1), then bisect both edges to 1e-6."""
    grid = np.arange(-a, a, step)
    hits = np.array([flips(svc, circ(("cx", 0, 1), ("rz", g, 1), ("cx", 0, 1))) for g in grid])
    idx = np.flatnonzero(hits)
    assert len(idx) and np.all(np.diff(idx) == 1), "no hit, or hits are not one interval"
    def bisect(out, inn):
        while abs(inn - out) > 1e-6:
            m = (inn + out) / 2
            out, inn = (out, m) if flips(svc, circ(("cx", 0, 1), ("rz", m, 1), ("cx", 0, 1))) else (m, inn)
        return inn
    return bisect(grid[idx[0] - 1], grid[idx[0]]), bisect(grid[idx[-1] + 1], grid[idx[-1]]), step

low, high, step = discover(service)
m = (low + high) / 2
print(f"activation interval ~ [{low:.6f}, {high:.6f}] rad, width {high-low:.6f}; grid step {step}, edges bisected to 1e-6")

P = lambda *mid, n=3: circ(("h", 0), ("cx", 0, 1), *mid, ("cx", 0, 1), n=n)
features = [  # (feature varied, circuit, predicted trigger)
    ("reference: h(0) cx(0,1) rz(mid,1) cx(0,1)", P(("rz", m, 1)), True),
    ("angle 1e-3 below lower edge", P(("rz", low - 1e-3, 1)), False),
    ("angle 1e-3 above upper edge", P(("rz", high + 1e-3, 1)), False),
    ("angle 1e-3 inside lower edge", P(("rz", low + 1e-3, 1)), True),
    ("angle 1e-3 inside upper edge", P(("rz", high - 1e-3, 1)), True),
    ("negative angle -mid", P(("rz", -m, 1)), False),
    ("angle mid + 2*pi (same rotation, other number)", P(("rz", m + 2 * np.pi, 1)), False),
    ("rz on the control wire", P(("rz", m, 0)), False),
    ("cx reversed: rz on qubit 1 (now control)", circ(("cx", 1, 0), ("rz", m, 1), ("cx", 1, 0)), False),
    ("cx reversed: rz on qubit 0 (now target)", circ(("cx", 1, 0), ("rz", m, 0), ("cx", 1, 0)), True),
    ("closing cx has other orientation", circ(("cx", 0, 1), ("rz", m, 1), ("cx", 1, 0)), False),
    ("cz instead of cx", circ(("cz", 0, 1), ("rz", m, 1), ("cz", 0, 1)), False),
    ("x on target between cx and rz", P(("x", 1), ("rz", m, 1)), False),
    ("x on control between (target wire untouched)", P(("x", 0), ("rz", m, 1)), True),
    ("spectator x on third qubit inside the pattern", P(("x", 2), ("rz", m, 1)), True),
    ("barrier inside the pattern", P(("barrier",), ("rz", m, 1)), True),
    ("no input prep (no h)", circ(("cx", 0, 1), ("rz", m, 1), ("cx", 0, 1)), True),
    ("control starts in |1> (x), no h", circ(("x", 0), ("cx", 0, 1), ("rz", m, 1), ("cx", 0, 1)), True),
    ("both qubits in superposition (h, h)", circ(("h", 0), ("h", 1), ("cx", 0, 1), ("rz", m, 1), ("cx", 0, 1)), True),
    ("rz split in two halves", P(("rz", m / 2, 1), ("rz", m / 2, 1)), False),
    ("p(mid) instead of rz(mid)", P(("p", m, 1)), False),
]
trigger_experiments = []
def record(svc, feature, qc, predicted, observed=None):
    observed, predicted = bool(flips(svc, qc, control=True) if observed is None else observed), bool(predicted)
    trigger_experiments.append({"feature_varied": feature, "instance_seed": svc.seed, "predicted_trigger": predicted,
                                "observed_trigger": observed, "match": predicted == observed})
for f, qc, pred in features: record(service, f, qc, pred)

# Several patterns (spec = [(target, angle)]): which rz is negated? Compare the output with "only rz #k negated".
def pats(spec, flip=()):
    qc = circ(("h", 0))
    for k, (t, a) in enumerate(spec):
        qc.cx(0, t); qc.rz(-a if k in flip else a, t); qc.cx(0, t)
    return qc
def negated(svc, spec):
    out = Operator(svc.compile(pats(spec)))
    return [k for k in range(len(spec)) if out.equiv(Operator(pats(spec, (k,))))]
for feature, spec, expect in [
        ("two patterns, targets 1 then 2: only the first rz is negated", [(1, m), (2, m)], [0]),
        ("two patterns, target 2 written first: the lower wire (1) is negated, not the earlier gate", [(2, m), (1, m)], [1]),
        ("a pattern outside the window does not block a later one", [(1, low - 0.1), (2, m)], [1])]:
    record(service, feature, None, True, negated(service, spec) == expect)

# Generalization: a second instance (other seed, temp file) must show the same behaviour with a shifted interval.
rule = lambda s: (0.25 + 0.025 * (s % 7), 0.75 + 0.025 * (s % 7))     # copied from _profile (service.py lines 54-55), a prediction only; a False row means a different build
edges_ok = lambda svc, lo, hi: max(abs(lo - rule(svc.seed)[0]), abs(hi - rule(svc.seed)[1])) < 1e-5
record(service, "measured edges equal the source rule", None, True, edges_ok(service, low, high))
with tempfile.TemporaryDirectory() as d:
    cfg = Path(d) / "other.json"
    cfg.write_text(json.dumps({"schema": "breaq-ch2-v1", "team_id": "jury-test", "seed": service.seed + 3}))
    other = CompilerService(str(cfg))
low2, high2, _ = discover(other)
print(f"seed {other.seed}: interval ~ [{low2:.6f}, {high2:.6f}], width {high2-low2:.6f}  (shift of lower edge {low2-low:+.6f})")
record(other, "measured edges equal the source rule", None, True, edges_ok(other, low2, high2))
for name, a in [("old lower edge + 0.01", low + 0.01), ("old upper edge - 0.01", high - 0.01), ("new interval centre", (low2 + high2) / 2)]:
    record(other, f"second instance: angle at {name}", P(("rz", a, 1)), low2 <= a <= high2)

for r in trigger_experiments: print(r["match"], "|", r["instance_seed"], "|", r["feature_varied"], "| pred", r["predicted_trigger"], "obs", r["observed_trigger"])
print("all predictions matched:", all(r["match"] for r in trigger_experiments), f"({len(trigger_experiments)} rows, {time.time()-t0:.1f}s)")
trigger_hypothesis = (f"The suspect build negates an rz angle when (1) the angle lies in [{low:.6f}, {high:.6f}] rad "
    f"(grid step {step}, edges bisected to 1e-6; the window shifts with the instance seed: {low2:.6f}..{high2:.6f} for seed {other.seed}), "
    "(2) the rz sits on the TARGET wire of a cx pair with identical qubits and nothing else on that wire between them. "
    "(3) At most one rz is negated per compile: the matching pattern on the lowest-numbered target wire, whatever the gate order "
    "in the circuit; a pattern outside the window does not block a later one. "
    "Not triggered by: rz on the control, a gate on the target wire between rz and cx, p or split-rz syntax, a different angle number "
    "(negative, +2pi). Spectators, barriers and input preparation are irrelevant. Matches _EchoBalance in service.py.")
print(trigger_hypothesis)
