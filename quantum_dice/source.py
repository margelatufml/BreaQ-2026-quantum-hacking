"""Layer 1 - the quantum coin: |0> --H--> measure, repeated n times (simulated).

Simulation boundary: Qiskit samples the measurement outcomes with a pseudorandom
generator. This models a quantum-bit source; it does not produce physical quantum
entropy, so the bits must not be used for passwords or keys.
"""
import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

COIN = QuantumCircuit(1)
COIN.h(0)  # |0> -> (|0> + |1>)/sqrt(2): each measurement gives 0 or 1 with probability 1/2


def ideal_probabilities() -> dict[str, float]:
    """Born-rule probabilities of one measurement of the coin: {'0': 0.5, '1': 0.5}."""
    return {str(k): float(v) for k, v in Statevector(COIN).probabilities_dict().items()}


def sample_bits(n: int, rng) -> np.ndarray:
    """n prepare-and-measure runs of the coin, in order, as an array of 0/1 ints.

    rng is an int seed or a numpy Generator. Passing the same Generator on every call
    continues its random stream; passing the same int restarts the stream from the
    beginning (that restart is the fault modelled in service.py).
    """
    sv = Statevector(COIN)
    sv.seed(rng)
    return sv.sample_memory(n).astype(int)


if __name__ == "__main__":
    probs = ideal_probabilities()
    assert abs(probs["0"] - 0.5) < 1e-9 and abs(probs["1"] - 0.5) < 1e-9
    bits = sample_bits(100_000, np.random.default_rng(1))
    assert set(np.unique(bits)) <= {0, 1}
    assert abs(bits.mean() - 0.5) < 0.01  # 100,000 draws: 0.5 +/- 0.003 at 95%
    print("ideal probabilities:", {k: round(v, 6) for k, v in probs.items()})
    print("first 32 bits:", "".join(map(str, bits[:32])))
    print("fraction of ones in 100,000 draws:", bits.mean())
