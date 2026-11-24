"""Secure bridge from Streamlit recordings to optional trained acoustic decoder.

Never pass the service bearer to the browser and never persist raw audio.
Observed phones are separate from text-based Tajweed suggestions.
"""
from __future__ import annotations
import io
import math
import re
import wave
from typing import Any
from urllib.parse import urlsplit

import numpy as np
import requests

MAX_BYTES = 8_000_000
SHORT = {"a": "short /a/ · fathah-like", "i": "short /i/ · kasrah-like",
         "u": "short /u/ · dammah-like"}
LONG = {"aa": "long /aː/ sound", "ii": "long /iː/ sound", "uu": "long /uː/ sound",
        "AA": "long emphatic /aː/-like", "II": "long emphatic /iː/-like"}
SPECIAL = {"<pad>", "<unk>", "<s>", "</s>", "<ctc>", "|"}


def readable_phone(token: str) -> dict[str, str]:
    """Interpret only symbols explicitly known to our UI.

    Case-sensitive: IPA/Arabic phoneme inventory includes contrasts and long
    vowels that cannot be safely inferred from a case-folded string.
    """
    if token in SHORT:
        return {"kind": "short_vowel_hypothesis", "meaning": SHORT[token]}
    if token in LONG:
        return {"kind": "long_vowel_hypothesis", "meaning": LONG[token]}
    if re.fullmatch(r"([bdfghjklmnpqrstvwxyzHESZDTRQ])\1", token):
        return {"kind": "geminated_consonant_hypothesis",
                "meaning": "Possible doubled consonant; not a verified shaddah"}
    return {"kind": "other_phone_hypothesis", "meaning": "Model-predicted phone symbol"}


def sanitize_observation(data: Any) -> dict:
    """Only allow bounded, nonauthoritative acoustic evidence in the UI."""
    if not isinstance(data, dict) or data.get("status") != "unverified_acoustic_observation":
        raise ValueError("Unrecognised phoneme service response")
    raw = data.get("observed_phonemes")
    duration = data.get("audio_duration_s")
    if not isinstance(raw, list) or len(raw) > 300:
        raise ValueError("Invalid phoneme prediction list")
    if type(duration) not in (int, float) or not 0.35 <= duration <= 15:
        raise ValueError("Invalid audio duration")
    observations = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Invalid phoneme event")
        token = item.get("token")
        start, stop = item.get("start_s"), item.get("end_s")
        if (not isinstance(token, str) or not 1 <= len(token) <= 20
                or token in SPECIAL or not re.fullmatch(r"[A-Za-z<>'_]+", token)
                or type(start) not in (int, float) or type(stop) not in (int, float)
                or not math.isfinite(start) or not math.isfinite(stop)
                or not 0 <= start < stop <= duration + 0.15):
            raise ValueError("Phoneme event failed validation")
        classification = readable_phone(token)
        observations.append({
            "token": token, "start_s": round(start, 3), "end_s": round(stop, 3),
            "kind": classification["kind"], "meaning": classification["meaning"],
            "status": "unverified",
        })
    return {
        "engine": "acoustic_ctc_experimental",
        "model_id": str(data.get("model_id", ""))[:130],
        "audio_duration_s": round(float(duration), 3),
        "observations": observations,
        "heard_hypotheses": " ".join(o["token"] for o in observations)[:1200],
        "not_measured": [
            "Correctness of each written vowel",
            "Verified articulation/makharij of each consonant",
            "Madd duration versus a permitted Hafs reading",
            "Ghunnah/nasal resonance and all other Tajweed subtleties",
        ],
        "guidance": (
            "These are acoustic-model sound guesses, not Tajweed grades. "
            "Compare with your Hafs reference reciter, especially when the "
            "model predicts a vowel you did not expect. If unclear, listen "
            "again or ask a qualified teacher."
        ),
    }


def service_ready(url: str, token: str) -> bool:
    """Require HTTPS and a private token; never downgrade to HTTP."""
    if not isinstance(url, str) or not isinstance(token, str):
        return False
    u = urlsplit(url)
    return (u.scheme == "https" and bool(u.hostname) and
            not u.username and not u.password and
            len(token) >= 32 and u.query == "" and u.fragment == "")


def prepare_acoustic_wav(raw: bytes) -> bytes:
    """Convert 16-bit uncompressed WAV to bounded mono 16kHz PCM.

    Preserve the actual amplitude and fine phonetic content: unlike loudness
    normalization, a silent voice is not artificially amplified into a pass.
    """
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError("Recording is too large")
    try:
        with wave.open(io.BytesIO(raw), "rb") as w:
            rate,channels,nframes = w.getframerate(), w.getnchannels(), w.getnframes()
            if (w.getsampwidth() != 2 or w.getcomptype() != "NONE" or
                    channels not in (1, 2) or not 8000 <= rate <= 96000 or
                    nframes <= 0 or nframes / rate > 15):
                raise ValueError("Use a short PCM WAV recording, up to 15 seconds")
            data = np.frombuffer(w.readframes(nframes), dtype="<i2")
            if not len(data) or len(data) % channels:
                raise ValueError("Invalid recorded samples")
            audio = data.reshape(-1, channels).astype(np.float32).mean(axis=1)
            if rate != 16000:
                frame_count = int(round(audio.size * 16000 / rate))
                audio = np.interp(
                    np.linspace(0,audio.size-1,frame_count),np.arange(audio.size),audio
                ).astype(np.float32)
            result = io.BytesIO()
            with wave.open(result, "wb") as dst:
                dst.setnchannels(1)
                dst.setsampwidth(2)
                dst.setframerate(16000)
                dst.writeframes(np.clip(audio,-32768,32767).astype("<i2").tobytes())
            return result.getvalue()
    except (wave.Error, EOFError, OSError) as exc:
        raise ValueError("Only 16-bit PCM WAV microphone audio is supported") from exc


def infer_acoustic_phones(raw: bytes, url: str, token: str) -> dict:
    """Call one service request; fail closed and never return auth details."""
    if not service_ready(url, token):
        raise RuntimeError("The private acoustic model service is not configured")
    wav = prepare_acoustic_wav(raw)
    try:
        result = requests.post(
            url.rstrip("/") + "/v1/phonemes",
            headers={"Authorization": "Bearer " + token,
                     "Content-Type": "audio/wav"},
            data=wav, timeout=90,
        )
        if result.status_code != 200:
            if result.status_code == 422:
                raise ValueError("Recording quality or duration is unsuitable. Try a clear 2–10 second phrase.")
            raise RuntimeError("The acoustic inference service could not process this recording")
        return sanitize_observation(result.json())
    except requests.RequestException as exc:
        raise RuntimeError("The acoustic inference service is temporarily unavailable") from exc
