"""Source-matched word timings for EveryAyah recitation playback.

The original per-word alignment was produced by QuranLife/TimingFilesCode,
CC BY 4.0. The cached files in timings/ preserve the start/end milliseconds
but omit sequential word indices to avoid redundant data.

This data is automated alignment, not human-audited and not a Tajweed grade.
Do not interpolate fake word positions when a recording has no usable timing.
"""
from functools import lru_cache
from pathlib import Path
import json

_ROOT = Path(__file__).resolve().parent
_RECITER_TIMINGS = {
    "Yasser_Ad-Dussary_128kbps": "yasser",
    "Alafasy_64kbps": "alafasy64",
}


@lru_cache(maxsize=8)
def _timing_group(source: str, group: int) -> dict:
    path = _ROOT / "timings" / f"quranlife_{source}_group{group}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def matched_word_segments(
    surah: int,
    ayah: int,
    reciter_folder: str,
    expected_word_count: int,
    start_index: int = 0,
) -> list:
    """Return only valid word segments from the same EveryAyah recording.

    Reject incomplete alignments, reordered timings, or mismatched word counts
    so a missing record cannot silently become incorrect word following.
    """
    source = _RECITER_TIMINGS.get(reciter_folder)
    if not source or expected_word_count < 1:
        return []
    group = (int(surah) + 19) // 20
    rows = _timing_group(source, group).get(f"{int(surah)}:{int(ayah)}")
    if not isinstance(rows, list) or len(rows) != expected_word_count:
        return []
    result = []
    previous_start = -1
    for i, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != 2:
            return []
        start_ms, end_ms = row
        if not (isinstance(start_ms, int) and isinstance(end_ms, int)):
            return []
        if start_ms < 0 or end_ms <= start_ms or start_ms < previous_start:
            return []
        if end_ms > 60 * 60 * 1000:
            return []
        result.append({
            "ayah": int(ayah),
            "word_idx": start_index + i,
            "start": start_ms,
            "end": end_ms,
            "source": "QuranLife/EveryAyah automated alignment",
        })
        previous_start = start_ms
    return result


def coverage(surah: int, first: int, last: int, reciter_folder: str, counts: list) -> dict:
    """Summarize timing availability for a selected passage."""
    good = 0
    offset = 0
    total = sum(counts)
    for ayah, count in zip(range(first, last + 1), counts):
        if matched_word_segments(surah, ayah, reciter_folder, count, offset):
            good += count
        offset += count
    return {"aligned_words": good, "total_words": total}
