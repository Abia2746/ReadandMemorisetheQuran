"""Opt-in acoustic analysis: 16 kHz mono PCM16, capped and never stored."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request
from app.services.acoustic_model import decode_pcm16, audio_quality, analyse

router = APIRouter(prefix="/api/acoustic", tags=["acoustic"])


@router.get("/capabilities")
async def capabilities():
    """A model can be configured without implying tested Tajweed accuracy."""
    from app.services.acoustic_model import load_approved_model
    try:
        _, registry = load_approved_model()
    except (RuntimeError, ValueError, OSError, ImportError, KeyError):
        return {"available": False, "reason": "No approved trained phoneme model deployed"}
    return {"available": True, "model_id": registry["model_id"],
            "tajweed_verified": False,
            "reason": "Model available for acoustic phone hypotheses, not certified Tajweed"}


@router.post("/analyse")
async def analyse_audio(request: Request):
    # Require octet-stream: prevents accidental text-transcript substitution.
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/octet-stream":
        raise HTTPException(415, "16 kHz mono PCM16 microphone audio required")
    if request.headers.get("content-length") and int(request.headers["content-length"]) > 256_000:
        raise HTTPException(413, "Audio window exceeds 8 seconds")
    audio = await request.body()
    try:
        samples = decode_pcm16(audio)
    except (ValueError, OverflowError) as exc:
        raise HTTPException(422, str(exc)) from exc
    quality = audio_quality(samples)
    if not quality["usable"]:
        return {"status": "uncertain", "audio_quality": quality, "phones": [],
                "tajweed_verified": False, "message": "Microphone quality is insufficient: try again."}
    try:
        result = analyse(samples)
    except (RuntimeError, ValueError, OSError, ImportError, KeyError) as exc:
        # Do not expose filesystem paths or internal model registry metadata.
        raise HTTPException(503, "A validated trained phoneme model is not available on this server") from exc
    return {**result, "audio_quality": quality}
