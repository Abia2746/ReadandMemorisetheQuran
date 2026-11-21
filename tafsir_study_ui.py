"""Verse-by-verse Tafsir study module for Streamlit.

Historical manuscript dimensions and the contents of a purported Mushaf Ali
cannot be inferred from the standard Qur'an text or tafsir transcriptions.
"""
import re


def clean_tafsir_display(value):
    """Remove repeated Arabic header and convert internal markers for readers."""
    if not isinstance(value, str):
        return ""
    value = value.replace("\\n", "\n")
    value = re.sub(r"^\\s*\\*\\*Qur.an \\d+:\\d+\\*\\*\\s*\\n+[^\\n]+\\n*", "", value)
    value = re.sub(r"\\[SOURCE\\s+(\\d+)\\]", r"〔\\1〕", value)
    value = re.sub(r"\\[NOT VERIFIED[^\\]]*\\]", "(verification pending)", value)
    value = re.sub(r"\\bsaqī\\b|\\bsajy\\b", "saqy", value)
    return value.strip()
import streamlit as st

def show_verse_tafsir(surah, start, end, language, fetch_words, ask_teacher):
    st.markdown("### 📜 Verse-by-verse Tafsir & Arabic Mastery")
    st.caption("Explore one ayah at a time: its meaning, classical commentary, vocabulary, and Arabic exercises.")
    end = min(int(end), int(start) + 19)
    verse = st.selectbox("Choose an ayah to study", list(range(int(start), end + 1)),
                         format_func=lambda v: f"Surah {surah} · Ayah {v}",
                         key=f"tafsir_verse_{surah}_{start}_{end}")
    try:
        words = fetch_words(int(surah), int(verse), language)
        arabic = " ".join(str(w.get("ar", "")) for w in words if w.get("ar"))
        if arabic:
            st.markdown(f"<div dir='rtl' style='font-family:serif;font-size:2rem;line-height:2.4;text-align:center;padding:1.1rem'>{arabic}</div>",
                        unsafe_allow_html=True)
        st.caption(f"Al-Qur'an {surah}:{verse} · Uthmani word text from the reader")
    except Exception:
        words = []
        st.warning("Arabic source temporarily unavailable; no verse text will be reconstructed.")
    key = f"tafsir_module_{surah}_{verse}_{language}"
    if st.button("Generate detailed Tafsir & Arabic study", key=f"generate_{key}", type="primary",
                 use_container_width=True):
        tafsir_instruction = (
            f"Explain ONLY Quran {surah}:{verse}. Include a faithful meaning, "
            "revelation context, relevant classical interpretations, legal and "
            "ethical rulings, and practical reflection. Organise under Meaning "
            "and Context, Word Insights, Rulings and Ethics, Purpose and Reflection. "
            "Verify exact narrator names against retrieved Arabic. Avoid made-up "
            "hadith, invented historical manuscript dimensions, and unverifiable "
            "claims. Keep this response under 1700 words. Do NOT generate "
            "flashcards or exercises in this response."
        )
        exercise_instruction = (
            f"Prepare Arabic learning material for Quran {surah}:{verse}. "
            "The Quranic word list below is authoritative for deciding which "
            "words occur in the verse (ignore punctuation and vowel marks): "
            + ", ".join(w.get("ar", "") for w in words if w.get("ar")) +
            ". First produce Part A: Quranic vocabulary, with Arabic word, "
            "root and literal meaning, using only words actually in the supplied "
            "Quranic word list. Include مَشْرَبَهُمْ in Part A if it is in the list. "
            "Exclude inflected forms of Qur\u0027anic roots already in Part A from Part B, " 
            "including العصا, العيون and الحجارة. " 
            "Then Part B: Classical Tafsir vocabulary, using ONLY words present "
            "in the retrieved classical tafsir transcription that are NOT in "
            "the Quranic word list. Never list a Quranic word in Part B. "
            "Treat وَإِذِ as conjunction plus adverbial noun, with no triliteral root. " 
            "Never claim consensus on congregational istisqa prayer: Al-Qurtubi records disagreement. " 
            "For ambiguous or non-triliteral roots write uncertain or not applicable. "
            "Then provide three exercises, each with its complete answer key: "
            "(1) three verified idafah/prepositional phrases, "
            "(2) four root-construction examples, "
            "(3) three original reverse-translation sentences labelled as "
            "practice sentences, NOT quotations from Quran or hadith. "
            "Use correct Arabic and precise transliteration: saqy, "
            "fa-nbajasat, fa-nfajarat, al-inbijas, kullu unasin, "
            "atha yathu. Do not invent commentary quotations. "
            "Finish all three exercises; aim for under 1700 words."
        )
        with st.spinner("Researching the classical Tafsir..."):
            tafsir_result = ask_teacher(tafsir_instruction, surah, verse, verse, language)
        with st.spinner("Building the vocabulary and complete Arabic exercises..."):
            exercise_result = ask_teacher(exercise_instruction, surah, verse, verse, language)
        st.session_state[key] = {"tafsir": tafsir_result, "exercises": exercise_result}
    if key in st.session_state:
        result = st.session_state[key]
        if isinstance(result, dict):
            tabs = st.tabs(["📖 Tafsir & Reflection", "🧠 Vocabulary & Exercises"])
            with tabs[0]:
                st.markdown(clean_tafsir_display(result.get("tafsir", "")))
            with tabs[1]:
                st.markdown(clean_tafsir_display(result.get("exercises", "")))
            notes = "# Tafsir " + str(surah) + ":" + str(verse) + "\\n\\n" + result.get("tafsir", "") + "\\n\\n# Arabic Mastery\\n\\n" + result.get("exercises", "")
            st.download_button("Save complete study notes", notes,
                               file_name=f"tafsir_{surah}_{verse}.md",
                               mime="text/markdown", key=f"save_{key}")
        elif isinstance(result, str):
            st.markdown(result)
