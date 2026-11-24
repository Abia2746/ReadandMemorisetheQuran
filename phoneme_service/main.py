"""Qur'an-aware acoustic phoneme inference (separate, opt-in CPU/GPU service).

This endpoint runs a REAL pretrained Wav2Vec2-CTC acoustic model on uploaded
16-bit PCM WAV. Its output is an observed *phoneme hypothesis*, NOT a
pronunciation or Tajweed grade. No target verse is fed to the acoustic model
(avoids automatically repeating expected words when only a syllable was said).

Use a private authenticated deployment. Never ship the service bearer token to
the browser. Audio is processed in RAM and not stored.
"""
from __future__ import annotations

import io
import os
import secrets
import wave
from functools import lru_cache

import numpy as np
from fastapi import FastAPI, Header, HTTPException, Request

MODEL_ID = "FatimahEmadEldin/wav2vec2-xls-r-300m-iqraeval"
MAX_AUDIO_BYTES = 8_000_000
MAX_SECONDS = 15.0
MIN_SECONDS = 0.35
app = FastAPI(title="Al-Muallim acoustic evidence", docs_url=None, redoc_url=None,
              openapi_url=None)


def _authenticated(value: str | None) -> bool:
    expected = os.environ.get("PHONEME_SERVICE_TOKEN", "")
    return (len(expected) >= 32 and isinstance(value, str)
            and value.startswith("Bearer ")
            and secrets.compare_digest(value.removeprefix("Bearer ").strip(), expected))


def parse_wav(raw: bytes) -> tuple[np.ndarray, int]:
    """Reject oversized, malformed, short, clipped or silent WAV recordings."""
    if not raw or len(raw) > MAX_AUDIO_BYTES:
        raise ValueError("Recording is empty or too large")
    try:
        with wave.open(io.BytesIO(raw), "rb") as w:
            rate = w.getframerate()
            channels = w.getnchannels()
            frames = w.getnframes()
            if (w.getcomptype() != "NONE" or w.getsampwidth() != 2
                    or not 8000 <= rate <= 96000 or channels not in (1, 2)):
                raise ValueError("Only uncompressed 16-bit PCM mono/stereo WAV is supported")
            length = frames / rate
            if not MIN_SECONDS <= length <= MAX_SECONDS:
                raise ValueError("Record between 0.35 and 15 seconds")
            samples = np.frombuffer(w.readframes(frames), dtype="<i2")
            if len(samples) != frames * channels:
                raise ValueError("Incomplete audio payload")
            peak = int(np.max(np.abs(samples.astype(np.int32))))
            if peak < 600:
                raise ValueError("Microphone recording is too quiet for phoneme assessment")
            if np.mean(np.abs(samples.astype(np.int32)) >= 32760) > 0.005:
                raise ValueError("Recording is clipped; reduce input level")
            mono = samples.reshape(-1, channels).astype(np.float32).mean(axis=1) / 32768.0
            if np.std(mono) < .008:
                raise ValueError("Microphone recording contains too little varying audio")
            # The model expects 16kHz. Resampling is independent of phoneme
            # recognition; it does not invent or correct pronunciation.
            if rate != 16000:
                n = round(mono.size * 16000 / rate)
                mono = np.interp(
                    np.linspace(0, mono.size - 1, n, dtype=np.float64),
                    np.arange(mono.size, dtype=np.float64), mono
                ).astype(np.float32)
            return mono, 16000
    except (EOFError, OSError, wave.Error) as exc:
        raise ValueError("Invalid PCM WAV audio") from exc


@lru_cache(maxsize=1)
def _model():
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    # Production should pin PHONEME_MODEL_REVISION to an audited commit.
    revision = os.environ.get("PHONEME_MODEL_REVISION", "main")
    processor = Wav2Vec2Processor.from_pretrained(
        MODEL_ID, revision=revision, trust_remote_code=False)
    model = Wav2Vec2ForCTC.from_pretrained(
        MODEL_ID, revision=revision, use_safetensors=True,
        trust_remote_code=False).eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    return model, processor, device


def ctc_spans(ids: list[int], probabilities: list[float], tokenizer,
              duration_s: float, blank: int) -> list[dict]:
    """Collapse CTC repeats and blanks into approximate, observed frame spans.

    Frame confidence is the model's own softmax, NOT calibrated error
    probability. Frame time is approximate and must never be called a
    phoneme-accurate start/end boundary before external alignment.
    """
    if len(ids) != len(probabilities) or not ids:
        return []
    spans = []
    current = None
    for index, ident in enumerate(ids):
        if ident == blank:
            current = None
            continue
        token = tokenizer.convert_ids_to_tokens(int(ident))
        if not isinstance(token, str) or token in (
            "<unk>", "<pad>", "<s>", "</s>", "<ctc>", "|", "[UNK]", "[PAD]"
        ):
            current = None
            continue
        if current is not None and current["token"] == token and current["_id"] == ident:
            current["end_s"] = round((index + 1) * duration_s / len(ids), 3)
            current["_prob"].append(float(probabilities[index]))
        else:
            current = {"token":token, "_id":ident, "_prob":[float(probabilities[index])],
                       "start_s":round(index * duration_s / len(ids), 3),
                       "end_s":round((index+1) * duration_s / len(ids), 3)}
            spans.append(current)
    for item in spans:
        item["model_posterior_mean"] = round(sum(item["_prob"]) / len(item["_prob"]), 4)
        item.pop("_prob")
        # Note: do not confuse a posterior with teacher-calibrated confidence.
        item.pop("_id")
    # The caller uses these tokens only as unverified acoustic observations.
    return spans[:300]


@app.get("/healthz")
def healthz():
    # Does not expose whether a secret or cached model has been configured.
    return {"status": "up", "model_loaded": _model.cache_info().currsize > 0}


@app.post("/v1/phonemes")
async def phonemes(request: Request, authorization: str | None = Header(default=None)):
    if not _authenticated(authorization):
        raise HTTPException(status_code=401, detail="Unauthorised")
    if request.headers.get("content-type", "").split(";")[0] != "audio/wav":
        raise HTTPException(status_code=415, detail="Upload a PCM WAV")
    # Stream a bounded request body. Never read arbitrary audio uploads into
    # memory simply because Content-Length is missing or forged.
    try:
        length = int(request.headers.get("content-length", "0") or 0)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid body size")
    if length > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio too large")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio too large")
        body.extend(chunk)
    try:
        samples, rate = parse_wav(bytes(body))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        import torch
        model, processor, device = _model()
        inputs = processor(samples, sampling_rate=rate, return_tensors="pt",
                           padding=False)
        with torch.inference_mode():
            logits = model(input_values=inputs.input_values.to(device)).logits[0]
            probs, ids = torch.softmax(logits, dim=-1).max(dim=-1)
        frame_ids = ids.cpu().tolist()
        frame_probs = probs.cpu().tolist()
        observed = ctc_spans(frame_ids, frame_probs, processor.tokenizer,
                             len(samples)/rate, (model.config.pad_token_id if model.config.pad_token_id is not None else processor.tokenizer.pad_token_id))
        return {
            "engine": "wav2vec2-ctc", "model_id": MODEL_ID,
            "revision": os.environ.get("PHONEME_MODEL_REVISION", "main"),
            "sample_rate": rate, "audio_duration_s": round(len(samples)/rate, 3),
            "observed_phonemes": observed, "status": "unverified_acoustic_observation",
            "meaning": "Model-predicted sound symbols, not Tajweed grades or verified exact vowel timing",
            "supported": ["phone_identity_hypotheses", "vowel_hypotheses",
                          "geminated_consonant_hypotheses"],
            "not_validated": ["makharij_accuracy", "madd_duration", "ghunnah_accuracy",
                              "tajweed_correctness", "verified_per_phoneme_timestamps"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        # Never echo upstream model errors, paths, audio, or credentials.
        raise HTTPException(status_code=503,
                            detail="Phoneme inference service unavailable") from exc
