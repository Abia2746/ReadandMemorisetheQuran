"""Evidence-first phonetic study support for Hafs Qur'an recordings.

A phonetic *reference* is not an acoustic measurement. The marks below are
copied from selected Uthmani text; recordings need a trained vowel/phoneme
recogniser and validated time alignment before any sound can be certified.
"""
from __future__ import annotations

import io
import unicodedata
import wave
from typing import Any

import numpy as np

VOWEL_MARKS = {
    "\u064e": ("fathah", "short a"),
    "\u064f": ("dammah", "short u"),
    "\u0650": ("kasrah", "short i"),
    "\u064b": ("fathatayn", "an ending"),
    "\u064c": ("dammatayn", "un ending"),
    "\u064d": ("kasratayn", "in ending"),
}
OTHER_MARKS = {
    "\u0651": "shaddah (consonant doubling)",
    "\u0652": "sukun (no following short vowel)",
    "\u0670": "superscript alif (madd context)",
    "\u0653": "maddah (elongation context)",
}
MAX_AUDIO_SECONDS = 180


def phonetic_reference(words: list[dict]) -> list[dict[str, Any]]:
    """Enumerate every written Arabic letter and the accompanying markings.

    This is an Uthmani-text guide, NOT a verified phoneme or articulatory
    transcription: contextual Tajweed, hamzat al-wasl, and waqf can change
    the realised sound. Do not infer sounds where no short vowel is written.
    """
    output = []
    for word_i, word in enumerate(words):
        raw = str(word.get("ar") or "")
        ayah = word.get("ayah")
        current: dict | None = None
        letter_i = -1
        for char in raw:
            category = unicodedata.category(char)
            if category.startswith("M"):
                if current is not None:
                    current["marks"].append(char)
                continue
            if category != "Lo" or not ("\u0600" <= char <= "\u06ff"):
                continue
            letter_i += 1
            current = {
                "word_i": word_i, "letter_i": letter_i, "ayah": ayah,
                "word": raw, "letter": char, "marks": [],
            }
            output.append(current)
    for unit in output:
        unit["vowels"] = [
            {"name": VOWEL_MARKS[mark][0], "sound": VOWEL_MARKS[mark][1]}
            for mark in unit["marks"] if mark in VOWEL_MARKS
        ]
        unit["features"] = [
            OTHER_MARKS.get(mark, unicodedata.name(mark, "unclassified Uthmani mark").lower())
            for mark in unit["marks"] if mark not in VOWEL_MARKS
        ]
        unit["status"] = "not_acoustically_verified"
        unit.pop("marks")
    return output


def wav_signal_evidence(raw: bytes) -> dict:
    """Numerical WAV quality gates; never claim to detect correct phonemes.

    Works on mono/multichannel PCM 16-bit WAV, and returns unknown for other
    formats rather than guessing from unparsed bytes.
    """
    unknown = {
        "available": False, "duration_s": None, "peak": None,
        "rms": None, "clipped_fraction": None, "quality": "unavailable",
        "notes": ["Audio quality could not be measured for this format."],
    }
    try:
        with wave.open(io.BytesIO(raw), "rb") as audio:
            if audio.getcomptype() != "NONE" or audio.getsampwidth() != 2:
                return unknown
            rate,channels,frames = audio.getframerate(),audio.getnchannels(),audio.getnframes()
            if not rate or channels < 1 or frames < 1:
                return unknown
            if frames / rate > MAX_AUDIO_SECONDS:
                return {**unknown, "notes": ["Recordings over 3 minutes require a shorter passage."]}
            sound = np.frombuffer(audio.readframes(frames), dtype="<i2")
            if sound.size < channels:
                return unknown
            mono = sound[:sound.size//channels*channels].reshape(-1,channels).astype(np.float64).mean(axis=1)/32768.0
            peak = float(np.max(np.abs(mono)))
            rms = float(np.sqrt(np.mean(mono*mono)))
            # Clipping is evaluated per original channel, not averaged mono.
            clipped_fraction = float(np.mean(np.abs(sound.astype(np.int32)) >= 32760))
            duration = round(frames/rate, 3)
            notes = []
            if rms < 0.005:
                notes.append("The recording is almost silent; pronunciation cannot be evaluated.")
            if peak < 0.03:
                notes.append("The microphone level is very low; try a closer, quieter recording.")
            if clipped_fraction > 0.005:
                notes.append("The recording is clipped or distorted; lower microphone gain.")
            if duration < 0.7:
                notes.append("The recording is too short for reliable phrase analysis.")
            quality = "review_needed" if notes else "usable_signal"
            return {
                "available": True, "duration_s": duration,
                "peak": round(peak, 5), "rms": round(rms, 5),
                "clipped_fraction": round(clipped_fraction, 6),
                "quality": quality, "notes": notes,
            }
    except (ValueError, wave.Error, EOFError, OSError):
        return unknown


def review_vowel_suggestions(model_output: object, reference: list[dict],
                             audio_quality: dict) -> list[dict]:
    """Sanitise LLM hypotheses; never turn them into verified vowel grades.

    Only written vowel targets in the selected text are eligible. Evidence
    should be timestamped and specific; signal quality must be usable.
    """
    if not isinstance(model_output, list):
        return []
    lookup = {(p["word_i"], p["letter_i"]): p for p in reference}
    duration = audio_quality.get("duration_s")
    if audio_quality.get("quality") != "usable_signal" or not isinstance(duration,(float,int)):
        return []
    result = []
    seen = set()
    for item in model_output[:100]:
        if not isinstance(item, dict) or item.get("status") != "possible_issue":
            continue
        wi,li = item.get("word_i"),item.get("letter_i")
        if type(wi) is not int or type(li) is not int or (wi,li) in seen:
            continue
        unit=lookup.get((wi,li))
        if not unit or not unit["vowels"]:
            continue
        time_s=item.get("time_s")
        if type(time_s) not in (int,float) or not 0<=time_s<=duration:
            continue
        evidence = item.get("evidence")
        guidance = item.get("guidance")
        if not isinstance(evidence,str) or len(evidence.strip()) < 12:
            continue
        if not isinstance(guidance,str) or len(guidance.strip()) < 12:
            continue
        result.append({
            "word_i": wi, "letter_i": li, "ayah": unit["ayah"],
            "word": unit["word"], "letter": unit["letter"],
            "expected": [v["name"] for v in unit["vowels"]],
            "time_s": round(float(time_s),2),
            "evidence": evidence.strip()[:300],
            "guidance": guidance.strip()[:300],
            "status": "possible_issue_unverified",
        })
        seen.add((wi,li))
    return result[:24]
