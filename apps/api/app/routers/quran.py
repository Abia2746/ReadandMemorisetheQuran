"""FREE Qur'an content and reciter metadata API.

Never routes via billing entitlement; always free. Canonical Uthmani text is
retrieved from the credentialed Quran Foundation service, never generated.
"""
import asyncio
import time
from dataclasses import dataclass

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.services.quran_metadata import AYAHS, SURAHS, valid_verse
from app.services.verse_generation import canonical_verse

router = APIRouter(prefix="/api/quran", tags=["quran-free"])

RECITERS = {
    "dosari": {"id": "dosari", "label": "Yasser Al-Dosari", "folder": "Yasser_Ad-Dussary_128kbps"},
    "alafasy": {"id": "alafasy", "label": "Mishary Alafasy", "folder": "Alafasy_128kbps"},
}


def _audio(surah: int, ayah: int, reciter: str) -> str:
    if not valid_verse(surah, ayah) or reciter not in RECITERS:
        raise HTTPException(422, "Unsupported audio selection")
    return (f"https://everyayah.com/data/{RECITERS[reciter]['folder']}/"
            f"{surah:03d}{ayah:03d}.mp3")


@router.get("/chapters")
async def chapters():
    return {"chapters": [
        {"surah": i, "name": SURAHS[i-1], "ayah_count": AYAHS[i]}
        for i in range(1, 115)
    ], "source": "Hafs 6236-ayah count", "free": True}


@router.get("/reciters")
async def reciters():
    return {"reciters": [
        {"id": entry["id"], "label": entry["label"]}
        for entry in RECITERS.values()
    ], "free": True}


@router.get("/verse/{surah}/{ayah}")
async def verse(
    request: Request, surah: int, ayah: int, lang: str = "en",
    reciter: str = "dosari",
):
    if not valid_verse(surah, ayah):
        raise HTTPException(404, "Verse is not within the Hafs surah limits")
    if reciter not in RECITERS:
        raise HTTPException(422, "Unsupported reciter")
    if lang != "en":
        raise HTTPException(422, "Only the configured, attributed English translation is available")
    key = (surah, ayah, lang)
    cache = request.app.state.quran_reader_cache
    cached = cache.get(key)
    if cached and time.monotonic() - cached["fetched_at"] < 3600:
        item = cached["data"]
    else:
        async with httpx.AsyncClient(follow_redirects=False) as client:
            arabic, words = await canonical_verse(client, surah, ayah, lang)
        item = {
            "surah": surah,
            "ayah": ayah,
            "arabic_uthmani": arabic.arabic_uthmani,
            "translation": arabic.translation,
            "translation_attribution": arabic.translation_attribution,
            "words": [
                {"id": w.word_id, "index": w.index,
                 "arabic": w.arabic_uthmani, "meaning": w.literal_gloss,
                 "transliteration": w.transliteration}
                for w in words
            ],
        }
        if len(cache) > 1000:
            cache.clear()
        cache[key] = {"fetched_at": time.monotonic(), "data": item}
    return {
        **item,
        "audio_url": _audio(surah, ayah, reciter),
        "reciter": RECITERS[reciter]["label"],
        "data_integrity": "Quran Foundation Uthmani verse source and word tokens",
        "free": True,
    }


@router.get("/passage/{surah}/{start}")
async def passage(
    request: Request, surah: int, start: int, end: int | None = None,
    lang: str = "en", reciter: str = "dosari",
):
    end = start if end is None else end
    if not valid_verse(surah, start) or not valid_verse(surah, end):
        raise HTTPException(404, "Invalid verse range")
    if end < start or end-start > 9:
        raise HTTPException(422, "Choose between one and ten consecutive verses")
    semaphore = asyncio.Semaphore(4)
    async def item(n):
        async with semaphore:
            return await verse(request,surah,n,lang,reciter)
    verses = await asyncio.gather(*(item(n) for n in range(start,end+1)))
    return {"surah": surah, "from": start, "to": end,
            "verses": verses, "free": True}
