"""Automated QuranLife timing data for the exact EveryAyah audio recording.

No interpolated timings. Refuse missing/mismatched rows, and show honest
fallbacks in the UI. Timing dataset attribution: timings/ATTRIBUTION.md.
"""
from functools import lru_cache
from pathlib import Path
import json

# Retain the legacy audio-aligned licensed dataset until copied as an
# explicit asset in the deployment image.
ROOT = Path(__file__).resolve().parents[4]
FILES = {"dosari": "yasser", "alafasy": "alafasy64"}

@lru_cache(maxsize=16)
def _load(group_key: str, group: int):
    path = ROOT / "timings" / f"quranlife_{group_key}_group{group}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def segments(surah: int, ayah: int, reciter: str, expected_count: int) -> list[dict]:
    key = FILES.get(reciter)
    if key is None or expected_count < 1:
        return []
    group = (surah + 19) // 20
    rows = _load(key, group).get(f"{surah}:{ayah}")
    if not isinstance(rows,list) or len(rows)!=expected_count:
        return []
    result = []
    last_start = -1
    for i, row in enumerate(rows):
        if not isinstance(row,list) or len(row)!=2:
            return []
        a,b = row
        if (type(a)!=int or type(b)!=int or a<0 or b<=a
                or a<last_start or b>3600000):
            return []
        result.append({"index": i+1, "start_ms":a, "end_ms":b})
        last_start=a
    return result
