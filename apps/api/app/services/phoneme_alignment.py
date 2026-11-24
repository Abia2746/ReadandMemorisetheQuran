"""Reference-aligned *candidate* phones, never certified Tajweed grades.

Intended for use with a trained acoustic phone decoder plus independently
reviewed Hafs target sequences. Alignment alone does not prove pronunciation.
"""
from __future__ import annotations
from typing import Any, Mapping, Sequence

from .quran_metadata import valid_verse

MAX_PHONES = 450
KINDS = {"match", "substitution_candidate", "deletion_candidate", "insertion_candidate"}


def _phone(item: Mapping[str, Any] | str) -> str:
    if isinstance(item, str):
        return item
    return str(item.get("phone", ""))


def align_phone_sequence(
    reference: Sequence[Mapping[str, Any] | str],
    observed: Sequence[Mapping[str, Any] | str],
    *, partial_window: bool = False,
) -> dict[str, Any]:
    """Levenshtein alignment with explicit insertions/deletions.

    Observed phone boundaries are approximate CTC emission-time windows.
    This function does NOT infer whether an expected sound was omitted or
    mispronounced; edit differences are *candidates to inspect*.
    """
    if len(reference) > MAX_PHONES or len(observed) > MAX_PHONES:
        raise ValueError("Too many phones in one window")
    expected = [_phone(x) for x in reference]
    heard = [_phone(x) for x in observed]
    if any(not x or len(x) > 64 for x in expected + heard):
        raise ValueError("Invalid phone symbol")
    n, m = len(expected), len(heard)
    # DP with stable tie order match/substitute, delete, insert.
    scores = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        scores[i][0] = 0 if partial_window else i
    for j in range(m + 1):
        scores[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            scores[i][j] = min(
                scores[i-1][j-1] + (expected[i-1] != heard[j-1]),
                scores[i-1][j] + 1, scores[i][j-1] + 1
            )
    events = []
    i, j = n, m
    if partial_window:
        # A rolling clip can start/end anywhere in the reviewed verse.
        distance = min(row[m] for row in scores)
        ends = [k for k, row in enumerate(scores) if row[m] == distance]
        if not m or len(ends) != 1 or distance >= m:
            return {"status": "uncertain_location", "events": [], "verified_tajweed": False}
        i = ends[0]
    distance = scores[i][j]
    while j or (i and not partial_window):
        if partial_window:
            choices = [
                i and j and scores[i][j] == scores[i-1][j-1] + (expected[i-1] != heard[j-1]),
                i and scores[i][j] == scores[i-1][j] + 1,
                j and scores[i][j] == scores[i][j-1] + 1,
            ]
            if sum(bool(choice) for choice in choices) != 1:
                return {"status": "uncertain_location", "events": [], "verified_tajweed": False}
        if i and j and scores[i][j] == scores[i-1][j-1] + (expected[i-1] != heard[j-1]):
            kind = "match" if expected[i-1] == heard[j-1] else "substitution_candidate"
            events.append((kind, i-1, j-1))
            i -= 1; j -= 1
        elif i and scores[i][j] == scores[i-1][j] + 1:
            events.append(("deletion_candidate", i-1, None))
            i -= 1
        else:
            events.append(("insertion_candidate", None, j-1))
            j -= 1
    events.reverse()
    output = []
    for kind, ref_i, obs_i in events:
        sound = observed[obs_i] if obs_i is not None else None
        data = sound if isinstance(sound, Mapping) else {}
        output.append({
            "kind": kind,
            "reference_index": ref_i,
            "observed_index": obs_i,
            "expected": expected[ref_i] if ref_i is not None else None,
            "observed": heard[obs_i] if obs_i is not None else None,
            "approx_start_ms": data.get("approx_start_ms"),
            "approx_end_ms": data.get("approx_end_ms"),
            "outcome": "uncertain",
            "explanation": (
                "Model phones align in this location, but individual sound accuracy is not verified."
                if kind == "match" else
                "Possible phoneme difference. Could reflect model uncertainty, timing, or pronunciation."
            ),
        })
    return {
        "edit_distance": distance,
        "reference_phones": n,
        "observed_phones": m,
        "events": output,
        "verified_tajweed": False,
        "interpretation": "Alignment candidates only. No Tajweed grades without independent acoustic validation.",
    }


def align_approved_verse(
    registry: Mapping[str, Any],
    surah: int,
    ayah: int,
    observed: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Never trust browser-supplied phonetic labels as canonical reference."""
    if not valid_verse(surah, ayah):
        raise ValueError("Invalid verse")
    entries = registry.get("verse_phone_references")
    key = f"{surah}:{ayah}"
    reference = entries.get(key) if isinstance(entries, dict) else None
    if not isinstance(reference, list) or not reference:
        return {"status": "reference_unavailable", "reference": key,
                "events": [], "verified_tajweed": False,
                "message": "No expert-reviewed phone reference configured for this verse"}
    if not all(isinstance(x, str) and x and len(x) <= 64 for x in reference):
        raise ValueError("Malformed reviewed reference")
    result = align_phone_sequence(reference, observed, partial_window=True)
    return {"status": "candidate_alignment", "reference": key, **result}


FEATURE_GROUPS = {
    "fathah": {"a", "ă", "a_short"},
    "kasrah": {"i", "ĭ", "i_short"},
    "dammah": {"u", "ŭ", "u_short"},
}
# The above is illustrative only and is not used as a pronunciation-scoring
# rule; each actual model must specify its expert-approved phone inventory.
