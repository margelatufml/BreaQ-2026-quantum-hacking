# Leave False until ready; a clean scaffold run must not export a false submission.
EXPORT_SUBMISSION = False
api_file = Path("submission_artifacts/student_api.py")
completion_status = {   # derived from what exists in this notebook; progress, not points
    "core": len(comparison_rows) == 2 * len(workloads) and bool(first_bad_transition) and bool(stage_evidence),
    "exploit": (minimal_source is not None and not reproducer_evidence.get("suspect_equiv", True)
                and bool(trigger_experiments) and reproducer_evidence.get("witness_exact_tv", 0) > 0),
    "defense": (api_file.exists() and defense_evidence.get("n_cases", 0) > 0 and defense_evidence.get("FN") == 0
                and defense_evidence.get("invalid_refused") == len(defense_evidence.get("invalid_inputs", []))),
}
print("completion_status:", completion_status, "| unresolved placeholders:", "REPLACE" in json.dumps(member_contributions),
      "| hints_used:", hints_used)

if EXPORT_SUBMISSION:
    if not security_claim.strip() or not claim_sheet or not member_contributions:
        raise ValueError("Fill the security claim, claim sheet, and contributions first")
    if "REPLACE" in json.dumps(member_contributions):
        raise ValueError("Replace the REPLACE placeholders in member_contributions with real names and contributions")
    destination = Path("submission_artifacts")
    destination.mkdir(exist_ok=True)
    if completion_status["defense"] and not (destination / "student_api.py").exists():
        raise ValueError("Save your standalone verifier in submission_artifacts/student_api.py")
    if minimal_source is not None:
        from qiskit import qpy
        with (destination / "minimal_source.qpy").open("wb") as handle:
            qpy.dump(minimal_source, handle)
    payload = {
        "schema": "breaq-submission-v1", "challenge": "02-treacherous-transpiler",
        "team_id": service.team_id, "instance_seed": service.seed,
        "environment": {"python": platform.python_version(), "qiskit": version("qiskit")},
        "security_claim": security_claim, "threat_model": threat_model,
        "first_bad_transition": first_bad_transition,
        "trigger_hypothesis": trigger_hypothesis,
        "completion_status": completion_status,
        "claims": claim_sheet, "member_contributions": member_contributions,
        "hints_used": hints_used, "verifier_limitations": verifier_limitations,
        "comparison": comparison_rows, "defense_evidence": defense_evidence,
        "reproducer_evidence": reproducer_evidence,
    }
    serialized = json.dumps(payload, indent=2, allow_nan=False)
    Path("submission.json").write_text(serialized, encoding="utf-8")
    # The rest of our evidence goes in its own file, so submission.json keeps exactly the scaffold's keys.
    extra = {"label": "local simulation", "instance_seed": service.seed, "extension_evidence": extension_evidence,
             "trigger_experiments": trigger_experiments, "stage_evidence": stage_evidence,
             "triage_evidence": triage_evidence, "initial_hypotheses": initial_hypotheses}
    (destination / "extra_evidence.json").write_text(json.dumps(extra, indent=2, allow_nan=False), encoding="utf-8")
    print("Exported submission.json; include the notebook and evidence directory as well.")
else:
    print("Scaffold mode: no submission exported.")
