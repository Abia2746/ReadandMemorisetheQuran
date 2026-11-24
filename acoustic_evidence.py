"""Evidence contract for future trained Qur'anic phoneme recognisers.

This module does NOT recognise phonemes. It accepts outputs from a separately
trained and validated *acoustic* model, and rejects unsupported certainty.
Text-only ASR and verse-position matching must never populate acoustic findings.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Any, Mapping, Sequence

KINDS = frozenset({
    "fathah", "kasrah", "dammah", "sukun", "shaddah",
    "consonant", "madd", "ghunnah", "qalqalah", "tafkhim",
    "tarqiq", "ikhfa", "idgham", "izhar", "iqlab", "waqf",
})
OUTCOMES = frozenset({"supported", "possible_mismatch", "uncertain"})
MIN_AUDIO_MS = 120
MAX_AUDIO_MS = 30_000


@dataclass(frozen=True)
class AudioQuality:
    duration_ms: int
    rms: float
    peak: float
    clipped_fraction: float
    silence_fraction: float
    usable: bool
    reasons: tuple[str, ...]


def inspect_pcm(samples: Sequence[float], sample_rate: int) -> AudioQuality:
    """Basic signal *quality*, never a phonetic or Tajweed judgement.

    Input must be mono, normalized [-1,1] PCM from the actual microphone.
    The absence of a quality warning is not proof of clear articulation.
    """
    if not isinstance(sample_rate, int) or not 8000 <= sample_rate <= 96000:
        raise ValueError("Unsupported sample rate")
    length = len(samples)
    duration_ms = round(length * 1000 / sample_rate)
    if length > sample_rate * 30:
        raise ValueError("Audio window exceeds 30 seconds")
    if any(not isfinite(float(s)) or abs(float(s)) > 1.0001 for s in samples):
        raise ValueError("Audio must be normalized, finite PCM")
    if not length:
        return AudioQuality(0, 0.0, 0.0, 0.0, 1.0, False, ("empty_audio",))
    rms = sqrt(sum(float(s) ** 2 for s in samples) / length)
    peak = max(abs(float(s)) for s in samples)
    clipped = sum(abs(float(s)) >= 0.999 for s in samples) / length
    # This is only a near-silence proxy, not voice activity detection.
    near_silent = sum(abs(float(s)) < 0.002 for s in samples) / length
    reasons = []
    if duration_ms < MIN_AUDIO_MS:
        reasons.append("too_short")
    if rms < 0.005:
        reasons.append("low_level")
    if clipped > 0.01:
        reasons.append("clipping")
    return AudioQuality(duration_ms, rms, peak, clipped, near_silent,
                        not reasons, tuple(reasons))


def assess_acoustic_observations(
    *,
    quality: AudioQuality,
    model_metadata: Mapping[str, Any] | None,
    observations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Conservatively transform model observations into learner-facing findings.

    'supported' means the *validated model detected supporting acoustic
    evidence*, NOT that a teacher has certified Tajweed correctness.

    Model adapter must supply a model/version, evaluation-set identifier,
    approval flag and acoustic modality. Thresholding is an additional gate,
    not a replacement for held-out calibration and teacher review.
    """
    meta = model_metadata or {}
    eligible = (
        quality.usable
        and meta.get("modality") == "microphone_pcm"
        and meta.get("validation_approved") is True
        and isinstance(meta.get("model_id"), str)
        and bool(meta.get("model_id", "").strip())
        and isinstance(meta.get("evaluation_set_id"), str)
        and bool(meta.get("evaluation_set_id", "").strip())
    )
    findings: list[dict[str, Any]] = []
    for item in observations[:100]:
        kind = item.get("kind")
        try:
            start_ms, end_ms = int(item["start_ms"]), int(item["end_ms"])
            confidence = float(item["calibrated_probability"])
        except (TypeError, ValueError, KeyError, OverflowError):
            continue
        if (kind not in KINDS or not 0 <= start_ms < end_ms <= quality.duration_ms
                or not isfinite(confidence) or not 0 <= confidence <= 1):
            continue
        # A text hypothesis alone is *not* microphone evidence.
        evidence = item.get("acoustic_evidence")
        has_evidence = isinstance(evidence, str) and len(evidence.strip()) >= 8
        proposed = item.get("outcome")
        if not eligible or not has_evidence or confidence < 0.90:
            outcome = "uncertain"
        elif proposed in {"supported", "possible_mismatch"}:
            outcome = proposed
        else:
            outcome = "uncertain"
        findings.append({
            "kind": kind,
            "start_ms": start_ms, "end_ms": end_ms,
            "expected": str(item.get("expected", ""))[:100],
            "observed": str(item.get("observed", ""))[:100] if has_evidence else "",
            "outcome": outcome,
            "confidence": round(confidence, 3) if eligible else None,
            "acoustic_evidence": evidence[:300] if has_evidence and eligible else "",
            "practice_tip": str(item.get("practice_tip", ""))[:250],
            "model_id": meta.get("model_id") if eligible else None,
        })
    return {
        "status": "acoustic_model_evaluated" if eligible else "not_verified",
        "audio_quality": {
            "duration_ms": quality.duration_ms,
            "usable": quality.usable,
            "reasons": list(quality.reasons),
        },
        "findings": findings,
        "supported_count": sum(x["outcome"] == "supported" for x in findings),
        "possible_mismatch_count": sum(
            x["outcome"] == "possible_mismatch" for x in findings
        ),
        "uncertain_count": sum(x["outcome"] == "uncertain" for x in findings),
        "disclaimer": (
            "Acoustic AI practice feedback, not a certified Tajweed judgement. "
            "Uncertain does not mean correct or incorrect."
        ),
    }
