# Your experiment: compare more inputs or exact distributions.
# Record the difference between an observation and a security conclusion.
rng = np.random.default_rng(0)

def normalize(counts):
    shots = sum(counts.values())
    return {k: v / shots for k, v in counts.items()}

def noise_floor(probs, shots=512, trials=2000):
    """99th percentile of the TV between two 512-shot samples of the SAME distribution."""
    p = np.array(list(probs.values()))
    a = rng.multinomial(shots, p, size=trials) / shots
    b = rng.multinomial(shots, p, size=trials) / shots
    return float(np.percentile(0.5 * np.abs(a - b).sum(axis=1), 99))

triage_evidence = []
for name, src in workloads.items():
    p_src, p_cand = exact_probabilities(src), exact_probabilities(compiled[name])
    sampled = total_variation(normalize(sample_counts(src, shots=512, seed=1)),
                              normalize(sample_counts(compiled[name], shots=512, seed=2)))  # different seeds!
    triage_evidence.append({"case_id": name, "sampled_tv": round(sampled, 3),
                            "noise_floor_p99": round(noise_floor(p_src), 3),
                            "exact_tv": round(total_variation(p_src, p_cand), 6)})
    print(triage_evidence[-1])

initial_hypotheses = [
    "Observation: only SCAN-B's histogram moves beyond shot noise; CAL-BELL, SCAN-D look identical.",
    "H1: the compiler changes the meaning of some circuits (SCAN-B), not all (CAL-BELL).",
    "H2: identical histograms do not prove equivalence: a phase-only change is invisible in the Z basis.",
    "So a histogram is an observation, not a security conclusion: compare full unitaries next.",
]
