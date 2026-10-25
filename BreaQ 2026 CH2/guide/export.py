# Optional helper: call only after constructing nonempty uniform rows.
import importlib.util, inspect, shutil      # repeated here (the tests cell imports some) so this cell stands alone
def save_evidence_rows(rows, filename="comparison.csv"):
    if not rows:
        raise ValueError("No experimental rows to export")
    destination = Path("submission_artifacts")
    destination.mkdir(exist_ok=True)
    with (destination / filename).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

# Reuses from the tests cell: cases, pos, refused, bad, HEADER.
# Defense rows: one per labelled test case (positive = candidate is NOT equivalent) and one per invalid input.
tag = lambda rows: [{"label": "local simulation", "instance_seed": service.seed, **r} for r in rows]
defense_rows = [{"kind": k, "n_qubits": s.num_qubits, "not_equivalent_by_oracle": bool(p), "verifier_refused": bool(r),
                 "outcome": {(True, True): "TP", (True, False): "FN", (False, False): "TN", (False, True): "FP"}[bool(p), bool(r)]}
                for (k, s, _), p, r in zip(cases, pos, refused)]
defense_rows += [{"kind": "invalid:" + n, "n_qubits": getattr(s, "num_qubits", -1), "not_equivalent_by_oracle": None,
                  "verifier_refused": not verify_compilation(s, c), "outcome": "invalid"} for n, s, c in bad]
for rows, name in ((comparison_rows, "comparison.csv"), (stage_evidence, "stage_evidence.csv"),
                   (trigger_experiments, "trigger_experiments.csv"), (defense_rows, "defense_tests.csv")):
    save_evidence_rows(tag(rows), name)

# student_api.py: written from the CURRENT notebook function (same text as the cell above), then reloaded as a separate module.
api = Path("submission_artifacts/student_api.py")
api.write_text(HEADER + inspect.getsource(verify_compilation), encoding="utf-8")
spec = importlib.util.spec_from_file_location("student_api", api)
student_api = importlib.util.module_from_spec(spec); spec.loader.exec_module(student_api)
agree = sum(student_api.verify_compilation(s, c) == verify_compilation(s, c) for _, s, c in cases + bad)
shutil.rmtree("submission_artifacts/__pycache__", ignore_errors=True)    # do not hand in bytecode
leaks = [w for w in ("service", "workloads", "compiled", "case_id", "breaq_ch2") if w in api.read_text()]
print(f"student_api.py: {api.stat().st_size} bytes, agrees with the notebook on {agree}/{len(cases) + len(bad)} inputs; notebook names inside: {leaks}")
print("exports ('local simulation'):")
for p in sorted(Path("submission_artifacts").glob("*")):
    if p.suffix in (".csv", ".png", ".py"):
        print(f"  {p.name:26}{p.stat().st_size:>8} bytes" + (f"  {sum(1 for _ in p.open()) - 1} rows" if p.suffix == ".csv" else ""))
