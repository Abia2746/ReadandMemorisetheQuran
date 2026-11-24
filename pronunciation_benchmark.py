"""Teacher-labelled phonetic assessment quality gate.

This module measures *actual labelled model predictions*. It deliberately
supplies no model and no fabricated accuracy figures. Only independent Hafs
teacher annotations should be fed to an external evaluation run.

Each item: {"sample_id", "speaker_id", "device", "phenomenon",
"truth": "issue"|"correct", "prediction": "issue"|"correct"|"uncertain"}.
A pronunciation verdict cannot be counted as accurate when it abstains.
"""
from __future__ import annotations
from collections import defaultdict

TRUTH = {"issue", "correct"}
PREDICTION = {"issue", "correct", "uncertain"}


def evaluate_teacher_labels(items: list[dict]) -> dict:
    """Calculate conservative mispronunciation detection diagnostics."""
    if not isinstance(items, list):
        raise ValueError("Labels must be an array")
    seen = set()
    counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0, "abstain": 0}
    cohort = defaultdict(list)
    for row in items:
        if not isinstance(row, dict):
            raise ValueError("Invalid label")
        ident = row.get("sample_id")
        if not isinstance(ident, str) or not ident or ident in seen:
            raise ValueError("Missing or repeated sample identity")
        seen.add(ident)
        truth, prediction = row.get("truth"), row.get("prediction")
        if truth not in TRUTH or prediction not in PREDICTION:
            raise ValueError("Labels must be teacher-verified: issue or correct")
        if prediction == "uncertain":
            counts["abstain"] += 1
        elif prediction == "issue":
            counts["tp" if truth == "issue" else "fp"] += 1
        else:
            counts["fn" if truth == "issue" else "tn"] += 1
        if isinstance(row.get("device"), str):
            cohort[("device", row["device"])].append(row)
        if isinstance(row.get("phenomenon"), str):
            cohort[("phenomenon", row["phenomenon"])].append(row)
    def ratio(a, b):
        return round(a / b, 4) if b else None
    count = len(items)
    attempted = count-counts["abstain"]
    result = {
        "sample_count": count, "assessed_count": attempted,
        "abstained_count": counts["abstain"],
        "coverage": ratio(attempted, count),
        "counts": counts,
        "precision_of_error_flags": ratio(counts["tp"], counts["tp"]+counts["fp"]),
        "error_detection_recall_assessed_only": ratio(
            counts["tp"], counts["tp"]+counts["fn"]),
        "false_alarm_rate_assessed_only": ratio(
            counts["fp"], counts["fp"]+counts["tn"]),
        "missed_error_rate_assessed_only": ratio(
            counts["fn"], counts["fn"]+counts["tp"]),
    }
    # Coverage is separate: abstaining on difficult cases can inflate reported
    # precision and assessed-only recall.
    result["cohorts"] = {
        f"{category}:{name}": {
            "count": len(rows), "coverage": ratio(
                sum(r["prediction"] != "uncertain" for r in rows),len(rows))
        }
        for (category,name),rows in sorted(cohort.items())
    }
    return result


def teacher_review_release_gate(metrics: dict, *,
                                minimum_sample_count: int = 500,
                                minimum_precision: float = 0.95,
                                minimum_recall: float = 0.85,
                                minimum_coverage: float = 0.85) -> dict:
    """Conservative ENGINEERING targets, not a scholarly endorsement.

    No passing metric establishes a qualified teacher replacement. Human
    annotation quality and independent test-set integrity must be audited.
    """
    reasons = []
    if metrics.get("sample_count", 0) < minimum_sample_count:
        reasons.append("Insufficient independently labelled held-out samples")
    for key, threshold in [
        ("precision_of_error_flags", minimum_precision),
        ("error_detection_recall_assessed_only", minimum_recall),
        ("coverage", minimum_coverage),
    ]:
        value = metrics.get(key)
        if not isinstance(value, (int,float)) or value < threshold:
            reasons.append(f"{key} below engineering target")
    if not metrics.get("cohorts"):
        reasons.append("No microphone/phenomenon coverage information")
    return {
        "engineering_gate_passed": not reasons,
        "reasons": reasons,
        "teacher_level_accuracy_established": False,
        "warning": "Metrics alone never imply an ijazah, sanad, or qualified teacher approval.",
    }
