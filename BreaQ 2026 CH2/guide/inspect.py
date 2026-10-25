# Implement your own comparison, not a workload-name lookup.
# Prediction before running: SCAN-D keeps the histogram (TV=0) but its unitary differs.
def inspect_compilation(source, candidate):
    return {
        "src_gates": source.size(), "src_depth": source.depth(),
        "cand_gates": candidate.size(), "cand_depth": candidate.depth(),
        "exact_tv": round(total_variation(exact_probabilities(source), exact_probabilities(candidate)), 6),
        "fidelity_000": round(float(state_fidelity(Statevector(source), Statevector(candidate))), 6),
        "unitary_equiv": bool(Operator(source).equiv(Operator(candidate))),  # up to global phase
    }

comparison_rows = []
for name, source in workloads.items():
    comparison_rows.append({"case_id": name, "build": "suspect", **inspect_compilation(source, compiled[name])})
    baseline = service.compile(source, build="baseline")          # control: the trusted build
    comparison_rows.append({"case_id": name, "build": "baseline", **inspect_compilation(source, baseline)})
for row in comparison_rows:
    print(row)
print("Histogram looks fine but unitary differs:",
      [r["case_id"] for r in comparison_rows if r["exact_tv"] == 0 and not r["unitary_equiv"]])
