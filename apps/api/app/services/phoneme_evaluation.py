"""Independent phone error and *candidate* feature evaluation.

Scores compare phone-labelled human reference and model predictions.
Model agreement with a transcript is NOT Tajweed correctness. Specific
Tajweed assessments need separate human-labelled sound-error examples.
"""
from __future__ import annotations
from collections import Counter
from typing import Mapping, Sequence

from .phoneme_alignment import align_phone_sequence

FEATURES = (
    "fathah", "kasrah", "dammah", "shaddah",
    "madd", "ghunnah", "makharij",
)


def phoneme_error_rate(reference: Sequence[str], prediction: Sequence[str]) -> dict:
    if not reference:
        raise ValueError("Reference cannot be empty")
    alignment = align_phone_sequence(reference, prediction)
    counts = Counter(event["kind"] for event in alignment["events"])
    return {
        "per": alignment["edit_distance"] / len(reference),
        "reference_count": len(reference),
        "substitutions": counts["substitution_candidate"],
        "deletions": counts["deletion_candidate"],
        "insertions": counts["insertion_candidate"],
    }


def evaluate_human_labelled_errors(rows: Sequence[Mapping]) -> dict:
    """Evaluate candidate error flags against independently labelled mistakes.

    Rows must contain {'feature': str, 'teacher_error': bool,
    'model_flag': bool, 'heldout_speaker': str}. These labels must come
    from an external certified reviewer, not model pseudo-labelling.
    """
    if not rows:
        raise ValueError("Independent held-out expert labels required")
    scores = {}
    for feature in FEATURES:
        items = [r for r in rows if r.get("feature") == feature]
        if not items:
            scores[feature] = {"status": "not_evaluated", "samples": 0}
            continue
        if any(type(r.get("teacher_error")) is not bool
               or type(r.get("model_flag")) is not bool
               or not r.get("heldout_speaker") for r in items):
            raise ValueError("Expert labels, model flags and speaker split are required")
        tp = sum(r["teacher_error"] and r["model_flag"] for r in items)
        fp = sum(not r["teacher_error"] and r["model_flag"] for r in items)
        fn = sum(r["teacher_error"] and not r["model_flag"] for r in items)
        tn = len(items) - tp - fp - fn
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        scores[feature] = {
            "status": "measured_not_certified",
            "samples": len(items),
            "true_positives": tp, "false_corrections": fp,
            "missed_errors": fn, "true_negatives": tn,
            "precision": precision, "recall": recall,
            "false_correction_rate_on_correct_samples":
                fp/(fp+tn) if fp+tn else None,
        }
    return {"features": scores, "certified": False,
            "notice": "Metrics require independent provenance and review before deployment approval."}
