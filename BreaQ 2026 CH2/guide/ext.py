# Three extensions from our own runs: (1) fine trigger-boundary sweep, (2) gate count is no certificate, (3) the witness grid.
# Reuses from earlier cells: circ, low, high, theta, minimal_source, witness, zero_tv, tv_exact, compiled, workloads.
import time
t0 = time.time(); Path("submission_artifacts").mkdir(exist_ok=True)
eq = lambda a, b: bool(Operator(a).equiv(Operator(b)))          # equal up to global phase
wtv = lambda a, b: total_variation(exact_probabilities(witness(a)), exact_probabilities(witness(b)))

# ---- 1. Trigger boundary: sweep the rz angle around the measured interval, rz on the target wire vs on the control wire ----
STEP, rows = 0.004, []
for role, wire in (("target", 1), ("control", 0)):
    for a in np.arange(low - 0.05, high + 0.05, STEP):
        src = circ(("cx", 0, 1), ("rz", float(a), wire), ("cx", 0, 1), n=2)
        for build in ("baseline", "suspect"):
            out = service.compile(src, build=build)
            rows.append({"build": build, "role": role, "angle_rad": round(float(a), 6), "width": 2, "unitary_equiv": eq(src, out),
                         "state_fidelity_zero_input": round(float(state_fidelity(Statevector(src), Statevector(out))), 6),
                         "zero_input_tv": round(total_variation(exact_probabilities(src), exact_probabilities(out)), 9),
                         "witness_tv": round(wtv(src, out), 6), "shots": "exact (no sampling)",
                         "instance_seed": service.seed, "label": "local simulation"})
with open("submission_artifacts/trigger_sweep.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
with open("submission_artifacts/trigger_sweep.csv", encoding="utf-8") as f:              # plot what is in the file
    saved = [{**r, "angle_rad": float(r["angle_rad"]), "witness_tv": float(r["witness_tv"])} for r in csv.DictReader(f)]
fig, ax = plt.subplots(figsize=(7, 3.5))
for build, role, style in (("baseline", "target", "k:"), ("suspect", "control", "g--"), ("suspect", "target", "r-")):
    pts = [r for r in saved if r["build"] == build and r["role"] == role]
    ax.plot([r["angle_rad"] for r in pts], [r["witness_tv"] for r in pts], style, label=f"{build}, rz on {role}")
ax.axvspan(low, high, alpha=0.1, color="r")
ax.set(xlabel="rz angle (rad)", ylabel="witness TV vs source", title=f"Trigger boundary, step {STEP} rad (local simulation)")
ax.legend(); fig.tight_layout(); fig.savefig("submission_artifacts/trigger_boundary.png", dpi=120); plt.show()
hit = [r["angle_rad"] for r in rows if r["build"] == "suspect" and r["role"] == "target" and not r["unitary_equiv"]]
gap_lo, gap_hi = min(hit) - low, high - max(hit)
baseline_ok = all(r["unitary_equiv"] for r in rows if r["build"] == "baseline")
control_ok = all(r["unitary_equiv"] for r in rows if r["build"] == "suspect" and r["role"] == "control")
print(f"1. {len(rows)} rows, grid step {STEP}: suspect/target breaks equivalence on [{min(hit)}, {max(hit)}] ({len(hit)} grid points); "
      f"bisected edges [{low:.4f}, {high:.4f}]; gaps {gap_lo:+.4f}, {gap_hi:+.4f} (< step {STEP}: {gap_lo < STEP and gap_hi < STEP})")
print("   baseline always equivalent:", baseline_ok, "| suspect with rz on control always equivalent:", control_ok)

# ---- 2. Gate count / depth is not an integrity certificate ----
good, evil = service.compile(minimal_source, build="baseline"), service.compile(minimal_source, build="suspect")
sig = lambda c: (c.size(), c.depth(), dict(c.count_ops()))
gc_rows = []
for name, s in workloads.items():
    b, x = service.compile(s, build="baseline"), compiled[name]
    gc_rows.append({"case": name, "src_size_depth": [s.size(), s.depth()], "baseline_size_depth": [b.size(), b.depth()],
                    "suspect_size_depth": [x.size(), x.depth()], "suspect_counts_equal_baseline": sig(b) == sig(x),
                    "baseline_equiv": eq(s, b), "suspect_equiv": eq(s, x)})
same_bad = [r["case"] for r in gc_rows if r["suspect_counts_equal_baseline"] and not r["suspect_equiv"]]
diff_ok = [r["case"] for r in gc_rows if r["baseline_equiv"] and r["baseline_size_depth"] != r["src_size_depth"]]
unchanged_bad = [r["case"] for r in gc_rows if r["suspect_size_depth"] == r["src_size_depth"] and not r["suspect_equiv"]]
U, V = Operator(good).data, Operator(evil).data
phase = np.exp(1j * np.angle(np.vdot(U, V)))                    # best global phase that maps U onto V
dist = float(np.linalg.norm(V - phase * U, 2))                  # spectral-norm distance between the two outputs
n_same = sum(r["suspect_counts_equal_baseline"] for r in gc_rows)
print(f"2. minimal_source: baseline {sig(good)} vs suspect {sig(evil)}: identical; unitary distance {dist:.4f}, equivalent {eq(good, evil)}")
print(f"   suspect output has the same size/depth/ops as the trusted baseline output in {n_same} of {len(gc_rows)} workloads; wrong ones: {same_bad}")
print(f"   same size AND depth as the SOURCE but wrong: {unchanged_bad}; correct (baseline) outputs whose size/depth differ from the source: {diff_ok}")

# ---- 3. Measurement witness: equal Z histograms, different unitaries, revealed by trusted preparation + analysis ----
preps = {"|0>": [], "|1>": ["x"], "|+>": ["h"], "|+i>": ["h", "s"]}
ana_ops = {"Z": [], "X": ["h"], "Y": ["sdg", "h"]}
def tv_for(p, a):
    def wrap(c):
        qc = QuantumCircuit(2)
        for g in preps[p]: getattr(qc, g)(0)
        qc.compose(c, inplace=True)
        for g in ana_ops[a]: getattr(qc, g)(0)
        return exact_probabilities(qc)
    return round(total_variation(wrap(good), wrap(evil)), 6)
grid = {p: {a: tv_for(p, a) for a in ana_ops} for p in preps}
print("3. TV(baseline, suspect) by trusted preparation (rows) and analysis basis (columns):")
for p, r in grid.items(): print(f"   {p:5}", r)
print(f"   zero-input TV {zero_tv:.1e}, unitaries equivalent {eq(good, evil)}, witness (|+i>, then h) TV {tv_exact:.6f} = |sin theta| {abs(np.sin(theta)):.6f}")

extension_evidence = {
    "label": "local simulation", "instance_seed": service.seed,
    "trigger_boundary": {"csv": "submission_artifacts/trigger_sweep.csv", "png": "submission_artifacts/trigger_boundary.png", "n_rows": len(rows),
                         "grid_step_rad": STEP, "sweep_range": [round(low - 0.05, 6), round(high + 0.05, 6)], "bisected_interval": [float(low), float(high)],
                         "first_last_grid_hit": [min(hit), max(hit)], "baseline_always_equivalent": baseline_ok, "control_wire_never_triggers": control_ok,
                         "resolution_note": "edges known to within one grid step from the sweep; to 1e-6 from bisection"},
    "gate_count_counterexample": {"minimal_source_baseline": sig(good), "minimal_source_suspect": sig(evil), "unitary_distance": dist,
                                  "equivalent": eq(good, evil), "workloads_same_counts_as_baseline_but_inequivalent": same_bad,
                                  "workloads_same_size_depth_as_source_but_inequivalent": unchanged_bad,
                                  "correct_outputs_with_other_size_or_depth_than_source": diff_ok, "per_workload_suspect_vs_baseline": gc_rows,
                                  "conclusion": "equal size, depth and op counts with a different unitary: counts are not a certificate (and different counts can be correct)"},
    "measurement_witness": {"zero_input_tv": float(zero_tv), "unitaries_equivalent": eq(good, evil), "witness_exact_tv": float(tv_exact),
                            "abs_sin_theta": float(abs(np.sin(theta))), "tv_by_prep_and_analysis": grid,
                            "conclusion": "Z histograms from |00> are equal; the difference is a relative phase seen only with a prep and analysis that turn it into a population"},
}
assert json.dumps(extension_evidence, allow_nan=False)
print(f"extension_evidence ready ({time.time() - t0:.1f}s)")
