"""Evidence-aware, 16-topic Tajweed practice rubric.

This is a STUDY CHECKLIST, not a universally standard set of 16 rules and not
a phoneme-level grading engine. LLM suggestions must never be presented as
validated correctness or as a certified Tajweed judgement.
"""
from __future__ import annotations

RULES = [
    ("Consonant identity and makharij", "Articulation of Arabic letters, especially similar sounds such as ص and ض."),
    ("Tafkhim and tarqiq", "Appropriate heavy and light sound quality, including rules for ر and ل."),
    ("Short vowels (harakat)", "Fathah, kasrah and dammah distinguished where audible."),
    ("Sukun and shaddah", "Correct absence of a vowel and doubled consonants."),
    ("Ghunnah", "Nasal resonance for applicable nūn and mīm sounds."),
    ("Izhar halqi", "Clear nūn sākinah or tanwīn before throat letters."),
    ("Idgham with ghunnah", "Assimilation with nasalisation where it applies."),
    ("Idgham without ghunnah", "Assimilation without nasalisation where it applies."),
    ("Iqlab", "Conversion before ب in its appropriate context."),
    ("Ikhfa haqiqi", "Concealment of nūn sākinah or tanwīn where it applies."),
    ("Izhar shafawi", "Clear mīm sākinah where it applies."),
    ("Idgham shafawi", "Lips-based mīm assimilation where it applies."),
    ("Ikhfa shafawi", "Lips-based concealment of mīm sākinah before ب."),
    ("Qalqalah", "Release of the five qalqalah consonants when sākin."),
    ("Madd types and duration", "Natural and secondary elongations appropriate to the reading."),
    ("Waqf and ibtida", "Meaningful stopping and restarting, with appropriate end vowels."),
]
ALLOWED_STATUS = {"possible_issue", "no_clear_issue", "uncertain", "not_applicable"}
MAX_ITEMS = 24


def rubric_for_prompt() -> list:
    return [
        {"id": i + 1, "name": name, "focus": detail}
        for i, (name, detail) in enumerate(RULES)
    ]


def normalize_review(data: dict, words: list, duration_s: float | None = None) -> dict:
    """Normalize and constrain model output; never invent an audio observation."""
    if not isinstance(data, dict):
        data = {}
    findings = data.get("rule_reviews") or []
    by_id = {
        item.get("rule_id"): item for item in findings
        if isinstance(item, dict) and type(item.get("rule_id")) is int
        and 1 <= item["rule_id"] <= len(RULES)
    }
    duration = duration_s if isinstance(duration_s, (int, float)) and duration_s > 0 else None
    rows = []
    observations = []
    for rule_id, (name, description) in enumerate(RULES, start=1):
        item = by_id.get(rule_id, {})
        status = item.get("status", "uncertain")
        if status not in ALLOWED_STATUS:
            status = "uncertain"
        word_i = item.get("word_i", -1)
        if type(word_i) is not int or not 0 <= word_i < len(words):
            word_i = -1
        time_s = item.get("time_s")
        if type(time_s) not in (int, float) or time_s < 0 or (
            duration is not None and time_s > duration + 1
        ):
            time_s = None
        evidence = str(item.get("evidence") or "").strip()[:350]
        correction = str(item.get("correction") or "").strip()[:350]
        # A location, clear evidence and practice guidance are prerequisites
        # for even showing an AI-suggested possible issue.
        if status == "possible_issue" and (
            word_i < 0 or not evidence or not correction or time_s is None
        ):
            status = "uncertain"
            evidence = ""
        if status == "no_clear_issue":
            # Generic audio models cannot certify this rule. A lack of detected
            # errors is NOT a verified correct pronunciation.
            status = "uncertain"
        if status == "possible_issue":
            location = f"{words[word_i]['ayah']} · {words[word_i]['ar']}"
            observations.append({
                "rule_id": rule_id, "rule_name": name, "word_i": word_i,
                "ayah": words[word_i]["ayah"],
                "arabic": words[word_i]["ar"],
                "time_s": round(float(time_s), 1),
                "evidence": evidence, "correction": correction,
                "confidence": "unverified AI suggestion",
            })
        else:
            location = None
        rows.append({
            "rule_id": rule_id, "rule_name": name, "explanation": description,
            "status": status, "location": location,
            "word_i": word_i if status == "possible_issue" else None,
            "time_s": round(float(time_s), 1) if status == "possible_issue" else None,
            "evidence": evidence if status == "possible_issue" else "",
            "correction": correction if status == "possible_issue" else "",
        })
    return {
        "rules": rows,
        "observations": observations[:MAX_ITEMS],
        "summary": str(data.get("feedback") or
            "The AI could not identify supported, specific pronunciation findings.")[:1000],
        "teacher_label": str(data.get("teacher_label") or
            "Review any uncertain sounds with a qualified Tajweed teacher.")[:350],
        "tafsir_summary": str(data.get("tafsir_summary") or "")[:1200],
        "duration_s": duration,
        "disclaimer": (
            "These are AI-assisted practice suggestions, not verified acoustic "
            "or phoneme-level Tajweed assessments. Uncertain means unverified, "
            "not necessarily correct or wrong."
        ),
    }
