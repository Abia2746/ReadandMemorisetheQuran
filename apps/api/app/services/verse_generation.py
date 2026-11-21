"""Canonical Qur'an/tafsir source loading and schema-checked AI generations.

- Quran Foundation v4 is the source for verse tokens; no fabricated Uthmani text.
- Third-party tafsir transcriptions are never labelled as critical editions.
- Model JSON is schema-checked but NOT automatically scholar-certified.
"""
from __future__ import annotations

import html
import asyncio
import time
import json
import os
import re
import unicodedata
from typing import Any

import httpx
from fastapi import HTTPException

from app.prompts.verse import (
    PROMPT_VERSION, build_study_drills_prompt, build_tafsir_prompt,
)
from app.schemas.verse import (
    QuranVerse, VerseWord, VerseStudyDrillsResponse, VerseTafsirResponse,
)

QURAN_BASES = {"production": "https://apis.quran.foundation/content/api/v4", "prelive": "https://apis-prelive.quran.foundation/content/api/v4"}
QURAN_AUTH_BASES = {"production": "https://oauth2.quran.foundation", "prelive": "https://prelive-oauth2.quran.foundation"}
_token_cache: dict[str, Any] = {"value": None, "expires": 0.0}
_token_lock = asyncio.Lock()
TAFSIR_BASE = "https://cdn.jsdelivr.net/gh/spa5k/tafsir_api@main/tafsir"
TAFSIR_EDITS = (
    ("ibn_kathir", "Ibn Kathir", "Tafsir al-Qur'an al-'Azim", "ar-tafsir-ibn-kathir"),
    ("al_tabari", "Al-Tabari", "Jami' al-Bayan", "ar-tafsir-al-tabari"),
    ("al_qurtubi", "Al-Qurtubi", "Al-Jami' li-Ahkam al-Qur'an", "ar-tafseer-al-qurtubi"),
)


def _plain_text(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


async def _quran_client_token(client: httpx.AsyncClient) -> tuple[str, str]:
    """Use server-only OAuth client_credentials, renew before expiration."""
    client_id = os.environ.get("QURAN_FOUNDATION_CLIENT_ID") or os.environ.get("QF_CLIENT_ID")
    static_token = os.environ.get("QURAN_FOUNDATION_ACCESS_TOKEN")
    if static_token and client_id:
        return static_token, client_id
    secret = os.environ.get("QURAN_FOUNDATION_CLIENT_SECRET") or os.environ.get("QF_CLIENT_SECRET")
    if not client_id or not secret:
        raise HTTPException(503, "Qur'an content credentials not configured on this server")
    if time.monotonic() < _token_cache["expires"] and _token_cache["value"]:
        return _token_cache["value"], client_id
    async with _token_lock:
        if time.monotonic() < _token_cache["expires"] and _token_cache["value"]:
            return _token_cache["value"], client_id
        env = os.environ.get("QF_ENV", "production")
        if env not in QURAN_AUTH_BASES:
            raise HTTPException(503, "Quran Foundation API environment invalid")
        scope = os.environ.get("QF_CONTENT_SCOPES", "content.quran.read content.translations.read")
        try:
            response = await client.post(
                QURAN_AUTH_BASES[env] + "/oauth2/token",
                data={"grant_type": "client_credentials", "scope": scope},
                auth=httpx.BasicAuth(client_id, secret),
                headers={"User-Agent": "AlMuallim-QuranStudy/1.0"},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            token = str(data["access_token"])
            ttl = int(data.get("expires_in", 3600))
            if not token or ttl < 60:
                raise ValueError("OAuth token was missing or short-lived")
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise HTTPException(503, "Qur'an content authentication temporarily unavailable")
        _token_cache["value"] = token
        _token_cache["expires"] = time.monotonic() + max(1, ttl - 60)
        return token, client_id


async def canonical_verse(
    client: httpx.AsyncClient, surah: int, ayah: int, lang: str,
):
    token, client_id = await _quran_client_token(client)
    env = os.environ.get("QF_ENV", "production")
    if env not in QURAN_BASES:
        raise HTTPException(503, "Qur'an content environment unavailable")
    url = f"{QURAN_BASES[env]}/verses/by_key/{surah}:{ayah}"
    response = await client.get(
        url,
        params={
            "words": "true", "fields": "text_uthmani",
            "word_fields": "text_uthmani", "language": "en",
            "translations": "131",
        },
        headers={"x-auth-token": token, "x-client-id": client_id},
        timeout=14,
    )
    if response.status_code == 404:
        raise HTTPException(404, "Verse not found")
    if response.status_code != 200:
        raise HTTPException(503, "Qur'an source unavailable")
    data = response.json().get("verse") or {}
    words = [
        w for w in data.get("words", [])
        if w.get("text_uthmani") and w.get("char_type_name") == "word"
    ]
    if not words:
        raise HTTPException(503, "Canonical word list unavailable")
    ordered = []
    for index, token_data in enumerate(words, 1):
        ordered.append(VerseWord(
            word_id=f"{surah}:{ayah}:{index}", index=index,
            arabic_uthmani=token_data["text_uthmani"],
            literal_gloss=_plain_text(
                (token_data.get("translation") or {}).get("text") or "Meaning pending"
            ),
            transliteration=_plain_text(
                (token_data.get("transliteration") or {}).get("text") or ""
            ) or None,
            root=None,
            root_state="not_applicable" if token_data["text_uthmani"].startswith("وَإِذِ")
                       else "needs_review",
            grammar=("conjunction + temporal adverbial noun"
                     if token_data["text_uthmani"].startswith("وَإِذِ") else None),
        ))
    translation_data = (data.get("translations") or [{}])[0]
    translation = _plain_text(translation_data.get("text") or "")
    if not translation:
        raise HTTPException(503, "Canonical English translation unavailable")
    verse = QuranVerse(
        surah=surah, ayah=ayah,
        arabic_uthmani=data.get("text_uthmani") or " ".join(w.arabic_uthmani for w in ordered),
        text_source="Quran Foundation content API v4 (Uthmani)",
        translation=translation,
        translation_attribution="Quran Foundation translation resource 131",
        translation_language="en",
    )
    return verse, ordered


async def retrieved_tafsir(
    client: httpx.AsyncClient, surah: int, ayah: int,
) -> list[dict[str, Any]]:
    async def one(key: str, author: str, title: str, edition: str):
        url = f"{TAFSIR_BASE}/{edition}/{surah}/{ayah}.json"
        try:
            response = await client.get(url, timeout=8)
            response.raise_for_status()
            value = response.json().get("text")
            if not isinstance(value, str) or not value.strip():
                return None
            return {
                "source_id": key,
                "author": author,
                "title": title,
                "verse": f"{surah}:{ayah}",
                "url": url,
                "text": _plain_text(value)[:8500],
                "provenance": "third_party_transcription",
                "edition_verified": False,
            }
        except (httpx.HTTPError, ValueError, AttributeError):
            return None
    import asyncio
    sources = await asyncio.gather(*(one(*args) for args in TAFSIR_EDITS))
    return [item for item in sources if item]


def public_sources(sources: list[dict]) -> list[dict]:
    return [
        {key: item[key] for key in (
            "source_id", "author", "title", "verse", "url",
            "provenance", "edition_verified",
        )}
        for item in sources
    ]


async def _gemini_json(client: httpx.AsyncClient, system: str, user: str):
    key = os.environ.get("GEMINI_API_KEY")
    model = os.environ.get("GEMINI_MODEL")
    if not key or not model or "/" in model or ":" in model:
        raise HTTPException(503, "Tafsir generation model is not configured")
    response = await client.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": user}]}],
            "systemInstruction": {"parts": [{"text": system}]},
            "generationConfig": {
                "temperature": 0.1, "responseMimeType": "application/json",
                "maxOutputTokens": 8192,
            },
        },
        timeout=70,
    )
    if response.status_code != 200:
        raise HTTPException(503, "Study generation temporarily unavailable")
    try:
        candidate = response.json()["candidates"][0]
        if candidate.get("finishReason") not in ("STOP", None):
            raise ValueError("Incomplete generation")
        answer = "".join(part.get("text", "") for part in candidate["content"]["parts"])
        return json.loads(answer)
    except (KeyError, IndexError, ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(503, "Study generation did not finish reliably")


def _normalized_arabic(value: str) -> str:
    """Compare quote text after harmless Arabic harakah and spacing variation."""
    text = unicodedata.normalize("NFKC", str(value))
    return "".join(
        c for c in text if not unicodedata.combining(c)
    ).replace("ـ", "").replace("\u200d", "").replace("\u200c", "").strip()


def _verify_verbatim_claims(raw: dict, sources: list[dict], verse: QuranVerse) -> None:
    source_by_id = {s["source_id"]: s.get("text", "") for s in sources}
    for section in raw.get("sections", []):
        for claim in section.get("claims", []):
            if not claim.get("is_verbatim"):
                continue
            quote = claim.get("quote_arabic")
            if not isinstance(quote, str) or not quote.strip():
                raise ValueError("Verbatim quotations need actual Arabic source text")
            speaker = str(claim.get("speaker") or "").lower()
            if any(name in speaker for name in
                   ("prophet muhammad", "messenger of allah", "رسول الله", "النبي")):
                raise ValueError("Prophetic quotations need separate hadith certification")
            normalized = _normalized_arabic(quote)
            references = claim.get("source_ids", [])
            canonical = _normalized_arabic(verse.arabic_uthmani)
            matches_quran = (
                claim.get("kind") == "quran_text" and normalized in canonical
            )
            matches_tafsir = any(
                normalized in _normalized_arabic(source_by_id.get(source_id, ""))
                for source_id in references
            )
            if not (matches_quran or matches_tafsir):
                raise ValueError("Arabic quotation absent from cited source text")
            # Source transcription evidence does NOT certify chain authenticity.
            if not matches_quran:
                claim["evidence_state"] = "needs_review"


async def generate_tafsir(
    client: httpx.AsyncClient,
    verse: QuranVerse,
    sources: list[dict],
):
    prompt = build_tafsir_prompt(verse.model_dump(mode="json"), sources)
    raw = await _gemini_json(client, prompt.system, prompt.user)
    raw["verse"] = verse.model_dump(mode="json")
    raw["sources"] = public_sources(sources)
    raw["prompt_version"] = PROMPT_VERSION
    raw["schema_version"] = "1.0"
    _verify_verbatim_claims(raw, sources, verse)
    # Metadata-only citation checks cannot establish semantic reliability.
    # Never mark a model's unsupervised paraphrases as independently verified.
    for section in raw.get("sections", []):
        for claim in section.get("claims", []):
            if not claim.get("is_verbatim"):
                claim["evidence_state"] = "needs_review"
    return VerseTafsirResponse.model_validate(raw).model_dump(mode="json")


async def generate_drills(
    client: httpx.AsyncClient,
    verse: QuranVerse,
    words: list[VerseWord],
    sources: list[dict],
):
    prompt = build_study_drills_prompt(
        verse.model_dump(mode="json"),
        [item.model_dump(mode="json") for item in words],
        [], sources,
    )
    raw = await _gemini_json(client, prompt.system, prompt.user)
    # Part A is canonical and not model-generated. Root metadata remains
    # pending until a vetted Arabic lexicon is attached to the service.
    # Reject Tafsir vocabulary that does not occur in the attributed retrieval.
    # Exact transcription matching is deliberately stricter than semantic
    # similarity: a model must not invent purported classical terms.
    known_sources = {item["source_id"]: item.get("text", "") for item in sources}
    for entry in raw.get("tafsir_vocabulary", []):
        word = _normalized_arabic(entry.get("arabic", ""))
        if not word or not any(
            word in _normalized_arabic(known_sources.get(ref, ""))
            for ref in entry.get("source_ids", [])
        ):
            raise ValueError("Tafsir vocabulary is not present in its cited source")
    raw["quran_vocabulary"] = [item.model_dump(mode="json") for item in words]
    raw["surah"] = verse.surah
    raw["ayah"] = verse.ayah
    raw["sources"] = public_sources(sources)
    raw["schema_version"] = "1.0"
    raw["prompt_version"] = PROMPT_VERSION
    return VerseStudyDrillsResponse.model_validate(raw).model_dump(mode="json")
