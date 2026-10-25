"""Layer 3 - the auditor.

Access model: it sees only the bits of each request, in order, with request boundaries.
It never sees seeds, configuration or source code. Every check answers one question,
states its assumption, and raises a yes/no alarm per request (batch).
"""
import math

import numpy as np
from scipy.stats import binomtest

FREQ_ALPHA = 0.01                      # frequency check: ~1% false alarms on fair, independent bits
RCT_CUTOFF = 1 + math.ceil(20 / 1.0)   # NIST SP 800-90B repetition count test, alpha = 2^-20, H = 1 bit -> 21
PREFIX_BITS = 64                       # replay check fingerprint: the first 64 bits of a request


def frequency_alarm(batch) -> bool:
    """Question: is this batch consistent with P(1) = 1/2?
    Assumption: independent fair bits. Rule: two-sided exact binomial test, alarm if p < FREQ_ALPHA."""
    return bool(binomtest(int(batch.sum()), len(batch), 0.5).pvalue < FREQ_ALPHA)


def longest_run(batch) -> int:
    """Length of the longest run of identical consecutive bits."""
    edges = np.concatenate(([0], np.flatnonzero(np.diff(batch)) + 1, [len(batch)]))
    return int(np.diff(edges).max())


def repetition_alarm(batch) -> bool:
    """Question: is any value repeated RCT_CUTOFF (21) times in a row?
    Assumption: 1 bit of entropy per sample; a given position starts such a run with probability ~2^-20."""
    return longest_run(batch) >= RCT_CUTOFF


class ReplayDetector:
    """Question: did this request's first 64 bits already appear in an earlier request?
    Assumption: fresh bits repeat a 64-bit prefix by chance with probability 2^-64 per pair,
    so any repeat is treated as a replay. Stateful: it remembers fingerprints across requests.
    Using a prefix (not the whole batch) also catches replays when the request size changes."""

    def __init__(self):
        self._seen = set()

    def alarm(self, batch) -> bool:
        fingerprint = np.asarray(batch[:PREFIX_BITS], dtype=np.uint8).tobytes()
        repeated = fingerprint in self._seen
        self._seen.add(fingerprint)
        return repeated


def audit_stream(batches) -> list[dict]:
    """Run every check on the requests of ONE service, in order: one dict of alarms per request."""
    replay = ReplayDetector()
    return [{"frequency": frequency_alarm(b), "repetition": repetition_alarm(b), "replay": replay.alarm(b)}
            for b in batches]


if __name__ == "__main__":
    assert longest_run(np.array([0, 0, 1, 1, 1, 0])) == 3
    assert repetition_alarm(np.zeros(21, dtype=int)) and not repetition_alarm(np.tile([0, 1], 512))
    assert frequency_alarm(np.ones(1024, dtype=int)) and not frequency_alarm(np.tile([0, 1], 512))
    batch = np.random.default_rng(0).integers(0, 2, 1024)
    alarms = audit_stream([batch, np.random.default_rng(1).integers(0, 2, 1024), batch])
    assert [a["replay"] for a in alarms] == [False, False, True]
    print("auditor self-check passed; RCT cutoff =", RCT_CUTOFF, "| alarms on [A, B, A]:", alarms)
