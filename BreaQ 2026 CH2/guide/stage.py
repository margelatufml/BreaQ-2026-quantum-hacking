# Localize the first semantic change. Operator.equiv compares unitaries up to global phase (default atol 1e-8, rtol 1e-5).
def unitary_gap(a, b):
    """Return (equiv, |tr(A^dag B)|/dim, global-phase shift if equivalent)."""
    A, B = Operator(a).data, Operator(b).data
    t = np.trace(A.conj().T @ B) / A.shape[0]
    eq = bool(Operator(a).equiv(Operator(b)))
    return eq, round(float(abs(t)), 6), (round(float(np.angle(t)), 6) + 0.0 if eq else None)

def localize(source, snaps, case_id, build):
    rows, prev = [], source
    for s in snaps:
        eq_prev, ov_prev, shift = unitary_gap(prev, s["circuit"])
        eq_src, ov_src, _ = unitary_gap(source, s["circuit"])
        rows.append({"case_id": case_id, "build": build, "stage": s["stage"], "depth": int(s["depth"]),
                     "equiv_vs_previous": eq_prev, "overlap_vs_previous": ov_prev, "phase_shift_vs_previous": shift,
                     "equiv_vs_source": eq_src, "overlap_vs_source": ov_src})
        prev = s["circuit"]
    return rows

def first_bad(rows):
    return next((i for i, r in enumerate(rows) if not r["equiv_vs_previous"]), None)

main = localize(workloads[focus], trace, focus, "suspect")
control = localize(workloads[focus], service.trace(workloads[focus], build="baseline"), focus, "baseline")
print(f"{'build':9}{'stage':24}{'depth':>5}{'equiv_prev':>12}{'overlap_prev':>14}{'phase_shift':>13}{'equiv_source':>14}")
for r in main + control:
    print(f"{r['build']:9}{r['stage']:24}{r['depth']:>5}{r['equiv_vs_previous']!s:>12}{r['overlap_vs_previous']:>14}"
          f"{r['phase_shift_vs_previous']!s:>13}{r['equiv_vs_source']!s:>14}")

# Controls: every workload on the suspect build; the logic never looks at the names.
allrows = {n: localize(q, service.trace(q), n, "suspect") for n, q in workloads.items()}
verdict = {n: first_bad(rows) for n, rows in allrows.items()}
print("first bad snapshot index per workload:", verdict)
rz = lambda c: [(round(float(g.operation.params[0]), 6), c.find_bit(g.qubits[0]).index) for g in c.data if g.operation.name == "rz"]
print("rz (angle, wire) in each source:", {n: rz(q) for n, q in workloads.items()})
print("gate count source -> compiled:", {n: (len(q.data), len(service.compile(q).data)) for n, q in workloads.items()})
stage_evidence = main + control + [r for n, rows in allrows.items() if n != focus for r in rows]

i = first_bad(main)
assert i is not None, "no bad transition for the focus workload"
before, after = rz(trace[i - 1]["circuit"]), rz(trace[i]["circuit"])
final = service.compile(workloads[focus])
final_ok = Operator(workloads[focus]).equiv(Operator(final))            # independent of the trace
end_ok = Operator(trace[-1]["circuit"]).equiv(Operator(final))          # last snapshot agrees with the real output
phase_only = {r["stage"]: r["phase_shift_vs_previous"] for r in main if r["equiv_vs_previous"] and abs(r["phase_shift_vs_previous"]) > 1e-9}
print(f"rz (angle, wire) before {before} after {after}; final output equivalent to source: {final_ok}; last snapshot matches compile(): {end_ok}")
first_bad_transition = (f"{trace[i-1]['stage']} -> {trace[i]['stage']}: unitary changes (overlap {main[i]['overlap_vs_previous']}); "
                        f"rz (angle, wire) {before} -> {after}. Phase-only stages (allowed): {phase_only}. "
                        f"Localization trusts the trace snapshots (untrusted service output). Independent anchors: snapshot 00 equals our source "
                        f"({main[0]['equiv_vs_source']}), the last snapshot matches service.compile ({end_ok}), and the compiled circuit is "
                        f"{'equivalent' if final_ok else 'NOT equivalent'} to the source.")
print(first_bad_transition)
