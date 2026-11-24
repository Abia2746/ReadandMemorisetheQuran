"""Opt-in acoustic analysis: 16 kHz mono PCM16, capped and never stored."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request, Depends
from redis.exceptions import RedisError
from starlette.concurrency import run_in_threadpool
from app.services.quran_metadata import valid_verse
from app.routers.billing import current_user
from app.services.acoustic_model import decode_pcm16, audio_quality, analyse, load_approved_model
from app.services.phoneme_alignment import align_approved_verse

router = APIRouter(prefix="/api/acoustic", tags=["acoustic"])


def parse_verse(value: str) -> tuple[int, int]:
    try:
        surah, ayah = map(int, value.split(":"))
    except ValueError:
        raise HTTPException(422, "Choose a valid Qur’an verse")
    if not valid_verse(surah, ayah):
        raise HTTPException(422, "Choose a valid Qur’an verse")
    return surah, ayah


def reviewed_registry(surah: int, ayah: int):
    _, registry = load_approved_model()
    reference = align_approved_verse(registry, surah, ayah, [])
    if reference["status"] == "reference_unavailable":
        raise ValueError("Missing reviewed verse reference")
    return registry


@router.get("/capabilities")
async def capabilities(verse: str = ""):
    try:
        if verse:
            registry = await run_in_threadpool(reviewed_registry, *parse_verse(verse))
        else:
            _, registry = await run_in_threadpool(load_approved_model)
    except (RuntimeError, ValueError, OSError, ImportError, KeyError):
        return {"available": False, "reason": "Reviewed acoustic model or verse reference unavailable"}
    return {"available": True, "model_id": registry["model_id"],
            "tajweed_verified": False, "reason": "Experimental phone hypotheses only"}


@router.post("/analyse")
async def analyse_audio(request: Request, _user=Depends(current_user)):
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/octet-stream":
        raise HTTPException(415, "16 kHz mono PCM16 microphone audio required")
    try:
        declared_length = int(request.headers.get("content-length", "0"))
    except ValueError:
        raise HTTPException(400, "Invalid audio length header")
    if declared_length > 256_000:
        raise HTTPException(413, "Audio window exceeds 8 seconds")
    surah, ayah = parse_verse(request.headers.get("x-quran-verse", ""))
    redis = request.app.state.redis
    if redis is None:
        raise HTTPException(503, "Acoustic request limiter unavailable")
    try:
        # Atomic across replicas. Only the account ID and a transient count are stored.
        requests = await redis.eval(
            "local n=redis.call('INCR',KEYS[1]); "
            "if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n",
            1, f"acoustic:minute:{_user.id}",
        )
    except (RedisError, OSError):
        raise HTTPException(503, "Acoustic request limiter unavailable")
    if requests > 30:
        raise HTTPException(429, "Pause before continuing acoustic practice", headers={"Retry-After":"60"})
    try:
        registry = await run_in_threadpool(reviewed_registry, surah, ayah)
    except (RuntimeError, ValueError, OSError, ImportError, KeyError):
        raise HTTPException(503, "Reviewed model or verse reference unavailable")
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
        result = await run_in_threadpool(analyse, samples)
    except (RuntimeError, ValueError, OSError, ImportError, KeyError) as exc:
        # Do not expose filesystem paths or internal model registry metadata.
        raise HTTPException(503, "A validated trained phoneme model is not available on this server") from exc
    result["alignment"] = align_approved_verse(registry, surah, ayah, result["phones"])
    return {**result, "audio_quality": quality}
