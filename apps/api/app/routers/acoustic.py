"""Opt-in acoustic analysis: 16 kHz mono PCM16, capped and never stored."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request, Depends
from app.routers.billing import current_user
from app.services.acoustic_model import decode_pcm16, audio_quality, analyse, load_approved_model
from app.services.phoneme_alignment import align_approved_verse

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
async def analyse_audio(request: Request, _user=Depends(current_user)):
    # Require octet-stream: prevents accidental text-transcript substitution.
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/octet-stream":
        raise HTTPException(415, "16 kHz mono PCM16 microphone audio required")
    try:
        declared_length = int(request.headers.get("content-length", "0"))
    except ValueError:
        raise HTTPException(400, "Invalid audio length header")
    if declared_length > 256_000:
        raise HTTPException(413, "Audio window exceeds 8 seconds")
    chunks = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > 256_000:
            raise HTTPException(413, "Audio window exceeds 8 seconds")
        chunks.append(chunk)
    audio = b"".join(chunks)
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
    verse_ref = request.headers.get("x-quran-verse", "")
    if verse_ref:
        try:
            surah_str, ayah_str = verse_ref.split(":")
            surah, ayah = int(surah_str), int(ayah_str)
            _, registry = load_approved_model()
            result["alignment"] = align_approved_verse(registry, surah, ayah, result["phones"])
        except (ValueError, KeyError):
            raise HTTPException(422, "Invalid Qur’an verse reference")
    return {**result, "audio_quality": quality}
