threat_model = {
    "protected_asset": "the meaning of the program: compiled circuit = source unitary (up to global phase)",
    "attacker_capability": "controls one third-party plugin pass inside the compiler; can rewrite the circuit",
    "trust_boundary": "everything from the compiler service is untrusted (output, trace, stage names, stats)",
    "security_property": "exact standalone-unitary equivalence up to global phase, 1-6 qubits, basis rz/sx/x/cx",
    "trusted_components": ["source circuit", "local Qiskit math (Operator, Statevector)", "local simulator", "our notebook"],
    "out_of_scope": ["large circuits", "controlled use (global phase visible)", "layout/routing/ancillas",
                     "attacker who controls the simulator or our verifier"],
}
print("Stronger claim: 'same standalone unitary' (implies the same histogram for EVERY input and basis).")
print("The contract requires the unitary claim; 'same observed distribution' is weaker.")
