"""Small, cached, on-demand-readable EveryAyah MP3 clips for on-device alignment.

Streamlit browser components cannot always fetch third-party MP3 bytes because
of CORS. This downloads ONLY fixed, trusted EveryAyah paths, with byte caps,
then supplies clips as base64 to the browser for optional local analysis.
The original source URLs remain available for playback when data is omitted.
"""
from concurrent.futures import ThreadPoolExecutor
import base64
import re

import requests
import streamlit as st

ALLOWED_FOLDER = re.compile(r"^(Yasser_Ad-Dussary_128kbps|Alafasy_64kbps)$")
CLIP_LIMIT_BYTES = 750_000
TOTAL_LIMIT_BYTES = 3_000_000
MAX_CLIPS = 10


@st.cache_data(ttl=86400, max_entries=48, show_spinner=False)
def inline_everyayah_clip(surah: int, ayah: int, folder: str) -> str | None:
    if not (1 <= surah <= 114 and 1 <= ayah <= 286):
        return None
    if not ALLOWED_FOLDER.fullmatch(folder):
        return None
    url = f"https://everyayah.com/data/{folder}/{surah:03d}{ayah:03d}.mp3"
    try:
        with requests.get(url, stream=True, timeout=(3, 7)) as response:
            response.raise_for_status()
            content_len = response.headers.get("content-length")
            if content_len and int(content_len) > CLIP_LIMIT_BYTES:
                return None
            chunks = []
            length = 0
            for part in response.iter_content(32768):
                if not part:
                    continue
                length += len(part)
                if length > CLIP_LIMIT_BYTES:
                    return None
                chunks.append(part)
        if length < 512:
            return None
        return base64.b64encode(b"".join(chunks)).decode("ascii")
    except (requests.RequestException, ValueError, OSError):
        return None


def inline_passage_clips(surah: int, first: int, last: int, folder: str) -> list:
    count = last - first + 1
    if count < 1:
        return []
    result = [None] * count
    if count > MAX_CLIPS or not ALLOWED_FOLDER.fullmatch(folder):
        return result
    with ThreadPoolExecutor(max_workers=min(5, count)) as pool:
        futures = {
            pool.submit(inline_everyayah_clip, surah, ayah, folder): i
            for i, ayah in enumerate(range(first, last + 1))
        }
        for future, i in futures.items():
            try:
                result[i] = future.result()
            except Exception:
                result[i] = None
    total = 0
    for i, clip in enumerate(result):
        if not clip:
            continue
        size = len(clip) * 3 // 4
        if total + size > TOTAL_LIMIT_BYTES:
            result[i] = None
        else:
            total += size
    return result
