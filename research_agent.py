"""Evidence research: opt-in web search, source reading, hadith lookup and edition checks.

External services require credentials. A search snippet is never treated as
proof, and a hadith collection reference is not an independent isnad grading.
"""
import os
import re
import html
import ipaddress
import socket
from urllib.parse import urlparse, quote
import requests

TRUSTED_DOMAINS = (
    "quran.ksu.edu.sa", "quran.com", "sunnah.com",
    "dorar.net", "shamela.ws", "islamweb.net",
)
MAX_PAGE = 220000

def _key(name):
    try:
        import streamlit as st
        return str(st.secrets.get(name, "") or os.environ.get(name, "")).strip()
    except Exception:
        return os.environ.get(name, "").strip()

def _safe_url(url):
    try:
        p = urlparse(url)
        if p.scheme != "https" or p.username or p.password or p.port not in (None, 443):
            return False
        host = (p.hostname or "").lower().rstrip(".")
        if not host or not any(host == d or host.endswith("." + d) for d in TRUSTED_DOMAINS):
            return False
        # Resolve to public IPs only; reject DNS resolution failure.
        for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
            ip = ipaddress.ip_address(item[4][0])
            if not ip.is_global:
                return False
        return True
    except (ValueError, OSError):
        return False

def read_page(url):
    """Read allowlisted public HTML, rejecting redirects and oversized responses."""
    if not _safe_url(url):
        return None
    try:
        with requests.get(url, timeout=(4, 10), allow_redirects=False,
                          headers={"User-Agent": "AlMuallimResearch/1.0",
                                   "Accept": "text/html"}, stream=True) as response:
            if response.status_code != 200 or "text/html" not in response.headers.get("Content-Type", ""):
                return None
            chunks, size = [], 0
            for chunk in response.iter_content(chunk_size=8192):
                size += len(chunk)
                if size > MAX_PAGE:
                    return None
                chunks.append(chunk)
            raw = b"".join(chunks).decode(response.encoding or "utf-8", "replace")
        raw = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\\1>", " ", raw)
        raw = re.sub(r"(?s)<[^>]+>", " ", raw)
        text = re.sub(r"\\s+", " ", html.unescape(raw)).strip()
        return text[:12000] if len(text) >= 100 else None
    except requests.RequestException:
        return None

def search_web(query, limit=5):
    """Brave Search API; no key => explicit unavailable status."""
    key = _key("BRAVE_SEARCH_API_KEY")
    if not key:
        return [], "Web discovery unavailable: configure BRAVE_SEARCH_API_KEY."
    try:
        r = requests.get("https://api.search.brave.com/res/v1/web/search",
            params={"q": str(query)[:250], "count": min(8, max(1, limit))},
            headers={"X-Subscription-Token": key, "Accept": "application/json"},
            timeout=9)
        r.raise_for_status()
        results = r.json().get("web", {}).get("results", [])
    except (requests.RequestException, ValueError):
        return [], "Web discovery request failed."
    found = []
    for item in results:
        url = item.get("url", "")
        if _safe_url(url) and url not in [v["url"] for v in found]:
            found.append({"url": url, "title": str(item.get("title", ""))[:180]})
    return found[:limit], "Search completed; only allowlisted sites are eligible for reading."

def research_web(query, surah, ayah):
    search_terms = f"{str(query)[:150]} Quran tafsir {surah}:{ayah} site:quran.ksu.edu.sa OR site:dorar.net OR site:sunnah.com"
    results, status = search_web(search_terms)
    documents = []
    for item in results[:3]:
        body = read_page(item["url"])
        if body:
            documents.append({"scholar": "Web document (unverified)", "verse": f"{surah}:{ayah}",
                              "text": body[:7000], "url": item["url"],
                              "kind": "web", "title": item["title"]})
    return documents, status

def lookup_hadith(query):
    """Lookup by collection and number via the official Sunnah.com API.

    API results may provide a recorded grade, not an independently authenticated
    isnad. Arbitrary keyword searches require separate search infrastructure.
    """
    match = re.search(r"\\b(bukhari|muslim|abudawud|tirmidhi|nasai|ibnmajah)\\s*[:# ]\\s*(\\d{1,5})\\b",
                      str(query).lower().replace("sahih ", ""))
    if not match:
        return [], "Hadith lookup requires a collection and number (e.g. Bukhari 1)."
    key = _key("SUNNAH_API_KEY")
    if not key:
        return [], "Hadith API unavailable: configure SUNNAH_API_KEY."
    collection, number = match.groups()
    url = f"https://api.sunnah.com/v1/hadiths/{collection}:{number}"
    try:
        response = requests.get(url, headers={"x-api-key": key}, timeout=9)
        response.raise_for_status()
        record = response.json()
        if not isinstance(record, dict):
            raise ValueError("Invalid record")
        arabic = str(record.get("hadithArabic", ""))[:4500]
        english = str(record.get("hadithEnglish", ""))[:4500]
        grades = record.get("grades", [])
        text = f"Arabic: {arabic}\\nEnglish: {english}\\nReported grading metadata: {str(grades)[:700]}"
        return [{"scholar": f"Hadith collection: {collection}", "verse": number,
                 "text": text, "url": url, "kind": "hadith"}], (
            "Hadith record retrieved; collection metadata is not independent chain verification."
        )
    except (requests.RequestException, ValueError):
        return [], "Hadith lookup failed or record unavailable."

def edition_status():
    """Do not mislabel a web transcription as a critical edition."""
    return ("Critical-edition validation unavailable: no licensed, edition-identified "
            "scholarly corpus with page-level provenance is configured. "
            "Never claim edition-level verification.")
