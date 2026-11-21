"""Read-only, allowlisted primary tafsir retrieval for Al-Mu'allim.

Data is a third-party transcription, not a verified critical edition. The
assistant must never claim an edition, chain, or quotation was independently
authenticated merely because this endpoint returned text.
"""
import html
import re
import requests
from functools import lru_cache

BASE = "https://cdn.jsdelivr.net/gh/spa5k/tafsir_api@main/tafsir"
EDITIONS = {
    "Ibn Kathir": "ar-tafsir-ibn-kathir",
    "Al-Tabari": "ar-tafsir-al-tabari",
    "Al-Qurtubi": "ar-tafseer-al-qurtubi",
    "Al-Sa'di": "ar-tafsir-as-saadi",
}
# A modest context budget avoids overwhelming the model or slow requests.
MAX_CHARS = 8500

def _clean(value):
    value = re.sub(r"<[^>]*>", " ", str(value))
    return re.sub(r"\s+", " ", html.unescape(value)).strip()

@lru_cache(maxsize=512)
def _fetch(edition, surah, ayah):
    if edition not in EDITIONS.values() or not (1 <= surah <= 114 and 1 <= ayah <= 286):
        return None
    url = f"{BASE}/{edition}/{surah}/{ayah}.json"
    try:
        response = requests.get(url, timeout=7, headers={"Accept": "application/json"})
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            # The dataset's per-ayah records expose text; reject unexpected shapes.
            value = data.get("text")
            if not isinstance(value, str) or not value.strip():
                return None
            return {"text": _clean(value)[:MAX_CHARS], "url": url}
    except (requests.RequestException, ValueError, TypeError):
        return None
    return None

def retrieve_tafsir(surah, start_ayah, end_ayah, query):
    """Return actual retrieved excerpts and visible provenance, or an explicit failure.

    Retrieve the user's requested scholar preferentially. Never turn a network
    failure into a simulated citation.
    """
    try:
        surah, start_ayah, end_ayah = int(surah), int(start_ayah), int(end_ayah)
    except (ValueError, TypeError):
        return [], "Invalid verse reference."
    if not (1 <= surah <= 114 and 1 <= start_ayah <= end_ayah <= 286):
        return [], "Invalid verse reference."
    q = str(query).lower()
    selected = [name for name in EDITIONS if name.lower() in q or name.lower().replace("al-", "") in q]
    if "kathir" in q and "Ibn Kathir" not in selected:
        selected.insert(0, "Ibn Kathir")
    if "tabari" in q and "Al-Tabari" not in selected:
        selected.append("Al-Tabari")
    if "qurtubi" in q and "Al-Qurtubi" not in selected:
        selected.append("Al-Qurtubi")
    if not selected:
        selected = ["Ibn Kathir", "Al-Tabari", "Al-Qurtubi"]
    selected = selected[:3]
    # Cap research to three verses per request; do not imply the rest were checked.
    verses = list(range(start_ayah, min(end_ayah, start_ayah + 2) + 1))
    sources = []
    for name in selected:
        for ayah in verses:
            result = _fetch(EDITIONS[name], surah, ayah)
            if result:
                sources.append({"scholar": name, "verse": f"{surah}:{ayah}", **result})
    if not sources:
        return [], "No primary tafsir text could be retrieved. Do not claim any source was checked."
    return sources, (
        f"Retrieved {len(sources)} transcribed tafsir entries for verses "
        f"{', '.join(str(v) for v in verses)}. "
        "These are source transcriptions, not authenticated critical editions. "
        "Missing entries were not verified."
    )

# Verification is performed against the retrieved transcription, not a critical edition.
import unicodedata

def _normalized_arabic(value):
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"[\u064b-\u065f\u0670\u06d6-\u06ed]", "", value)
    value = re.sub(r"[ـ\u200c\u200d]", "", value)
    return re.sub(r"\s+", " ", value).strip()

def audit_tafsir_answer(answer, sources):
    """Remove unsupported Arabic quotation paragraphs before publication.

    Conservative fail-closed audit: an Arabic quotation must occur in at least
    one retrieved source after diacritic/whitespace normalization. No claim
    of edition-level authentication is made. Returns text and audit findings.
    """
    if not isinstance(answer, str):
        return "", ["Model returned an invalid response."]
    verified = [_normalized_arabic(s["text"]) for s in sources]
    findings = []
    output = []
    # Split by paragraphs to avoid publishing a questionable Arabic quotation
    # with surrounding scholarly attribution.
    for paragraph in re.split(r"(\\n\\s*\\n)", answer):
        if not paragraph.strip():
            output.append(paragraph)
            continue
        quoted = re.findall(r"[«“\"]([^»”\"]{12,})[»”\"]", paragraph)
        unsupported = False
        for quote in quoted:
            if len(re.findall(r"[\u0621-\u064a]", quote)) < 9:
                continue
            normalized = _normalized_arabic(quote)
            if not any(normalized in item for item in verified):
                unsupported = True
                findings.append("An Arabic quotation was withheld because it could not be matched to a retrieved tafsir transcription.")
        if unsupported:
            output.append("[Unverified Arabic quotation withheld. Consult the linked source transcription.]")
        else:
            output.append(paragraph)
    return "".join(output), findings
