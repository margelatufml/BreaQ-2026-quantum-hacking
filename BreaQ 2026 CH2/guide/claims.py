# Every number below is read from variables our own cells computed, so the text cannot drift from the evidence.
d, rep, ext = defense_evidence, reproducer_evidence, extension_evidence
gc = ext["gate_count_counterexample"]["per_workload_suspect_vs_baseline"]
base_ok = sum(r["unitary_equiv"] for r in comparison_rows if r["build"] == "baseline")
hist_blind = [r["case_id"] for r in comparison_rows if r["build"] == "suspect" and r["exact_tv"] == 0 and not r["unitary_equiv"]]
bad_stage = first_bad_transition.split(": unitary")[0]            # text before the first metric, from the stage cell
same_counts = sum(r["suspect_counts_equal_baseline"] for r in gc)

security_claim = (
    f"On this instance (seed {service.seed}) the 'suspect' build is NOT contract-preserving: a vendor pass negates one rz angle in "
    f"[{low:.3f}, {high:.3f}] rad that sits between two identical cx gates on the target wire ({bad_stage.split(' -> ')[-1]}). "
    f"The 'baseline' build preserved the unitary in {base_ok} of {len(workloads)} workloads. Our verifier compares source and candidate as "
    f"matrices and refused {d['TP']} of {d['TP'] + d['FN']} changed outputs and accepted {d['TN']} of {d['TN'] + d['FP']} legitimate ones "
    "on our test set (local simulation). This is a numerical small-circuit check, not a proof, and says nothing about other triggers "
    "or other compilers.")

claim_sheet = [
    {"claim": f"Histograms are not enough: {', '.join(hist_blind)} change the unitary but keep the Z histogram (exact TV 0).",
     "evidence": "comparison_rows / comparison.csv: exact_tv = 0 and unitary_equiv = False for the suspect build; extension 3 table",
     "assumption": "Operator.equiv (Qiskit math) and the exact simulator are trusted",
     "limitation": "shows one failure mode of one plugin, not all histogram-invisible faults"},
    {"claim": f"The first violating transition is {bad_stage}; the earlier stages only change syntax or the global phase.",
     "evidence": "stage_evidence / stage_evidence.csv: unitary overlap and equiv_vs_previous per stage; the baseline trace has no bad stage",
     "assumption": "trace snapshots are honest; anchored by snapshot 00 = our source and last snapshot = compile() output",
     "limitation": "the trace is untrusted service output, not an attestation of what a remote service ran"},
    {"claim": f"Activation: rz angle in [{low:.3f}, {high:.3f}] rad, rz on the target wire of a cx pair, nothing between; the angle is negated.",
     "evidence": f"trigger_experiments.csv ({len(trigger_experiments)} rows, predictions matched: {all(r['match'] for r in trigger_experiments)}); "
                 f"trigger_sweep.csv + trigger_boundary.png (step {ext['trigger_boundary']['grid_step_rad']} rad, edges bisected to 1e-6)",
     "assumption": "the window shifts with the instance seed; we confirmed a second seed and cite service.py only for predictions",
     "limitation": "found by one-feature experiments on this build; a different build may use other features"},
    {"claim": "A 3-instruction reproducer plus a trusted witness shows the fault.",
     "evidence": f"reproducer_evidence: cx rz({rep['theta']:.3f}) cx, zero-input TV {rep['zero_input_tv']:.0e}, "
                 f"witness TV {rep['witness_exact_tv']:.4f} = |sin theta|; "
                 f"{rep['smaller_circuits_satisfying']} of {rep['smaller_circuits_checked']} smaller circuits reproduce it",
     "assumption": "tester adds preparation and analysis after compilation, outside the submitted subroutine",
     "limitation": "1-minimal by deletion and by a 12-gate library search, not globally minimal"},
    {"claim": "Gate count and depth are not an integrity certificate.",
     "evidence": f"extension 2: suspect and baseline outputs have equal size, depth and op counts in {same_counts} of {len(gc)} workloads, "
                 f"yet {ext['gate_count_counterexample']['workloads_same_counts_as_baseline_but_inequivalent']} differ in unitary",
     "assumption": "baseline output is the trusted reference only for this comparison",
     "limitation": "one plugin; says nothing about plugins that also change gate counts"},
    {"claim": f"verify_compilation separates changed from legitimate outputs on our test set and refuses invalid inputs "
              f"({d['invalid_refused']} of {len(d['invalid_inputs'])}).",
     "evidence": f"defense_evidence / defense_tests.csv: TP {d['TP']} FN {d['FN']} TN {d['TN']} FP {d['FP']}; "
                 f"labels from an independent oracle; student_api.py agrees on {d['student_api_agrees']}",
     "assumption": "local Qiskit and this machine are trusted; circuits are 1 to 6 qubits",
     "limitation": "rotation errors below about 2e-8 rad pass; full-matrix method does not scale; "
                   "out-of-contract but correct outputs (h gate, layout) are refused"},
]
assert json.dumps([security_claim, claim_sheet], allow_nan=False)

# TEAM: replace every REPLACE text with the real name and an honest, concrete contribution. Export is blocked until you do.
member_contributions = [
    {"member": "REPLACE: name or alias of member 1", "contribution": "REPLACE: what this person did and can explain (e.g. triage and fault localization)"},
    {"member": "REPLACE: name or alias of member 2", "contribution": "REPLACE: e.g. trigger discovery and reproducer"},
    {"member": "REPLACE: name or alias of member 3", "contribution": "REPLACE: e.g. verifier, tests, limitations"},
    # Keep this last line only if it is true for your team; edit or delete it otherwise.
    {"member": "AI assistant (Claude Code)", "contribution": "Wrote the notebook code and the written explanations; "
                                                             "the team ran every cell, checked the outputs and can explain each step."},
]
# The hint cell was visible to the AI assistant while it wrote these cells, so all four are listed. Edit only if untrue.
hints_used = ["Hint 1 (Comparing meanings)", "Hint 2 (Observability)", "Hint 3 (Fault localization)",
              "Hint 4 (Counterfactual experiment)"]

print(security_claim)
print(f"\nclaim_sheet: {len(claim_sheet)} claims, each with claim / evidence / assumption / limitation.")
print("member_contributions: lines still to edit (contain REPLACE):", sum("REPLACE" in json.dumps(m) for m in member_contributions))
