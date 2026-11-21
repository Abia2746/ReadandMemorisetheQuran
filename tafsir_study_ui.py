"""Verse-by-verse Tafsir study module for Streamlit.

Historical manuscript dimensions and the contents of a purported Mushaf Ali
cannot be inferred from the standard Qur'an text or tafsir transcriptions.
"""
import re
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
        instruction = (
            f"Create a complete study module ONLY for Surah {surah}, ayah {verse}. "
            "Begin with an accurate English meaning; the UI already shows verified Arabic, "
            "so do not invent or repeat Arabic Qur'an text. "
            "Use exactly these four headings: "
            "1. نُزُولُ الآيَة — Descent and Context (addressed, objective, clarification); "
            "2. أَحْكَامُ الشَّرِيعَة — Rulings and Ethics (wording, verdict, jurisprudence); "
            "3. مَعْنَى اللَّفْظ — Wording and Early Commentary (precisely attributed "
            "classical reports, distinguishing narrator from compiler); "
            "4. مَقْصِدُ العَمَل — Purpose and Reflection (action and spiritual meaning). "
            "Then include two separate Markdown tables: "
            "Part A: Qur'anic vocabulary (Arabic word, verified root, literal meaning); "
            "Part B: Tafsir vocabulary (Arabic term present in retrieved source, verified "
            "root, literal meaning). Do not invent a three-letter root for particles, "
            "loanwords, or ambiguous forms: write 'not applicable' or 'uncertain'. "
            "Then include three independent Arabic mastery exercises WITH answer keys: "
            "three idafah/prepositional phrases from the actual sourced commentary, "
            "four root-construction examples, and three reverse-translation sentences "
            "clearly labelled 'original practice sentences, not Qur'an or hadith'. "
            "If the source does not contain enough examples, include fewer and state why. "
            "Never invent a Prophetic or Companion quotation. Only quote a hadith "
            "verbatim with verified exact collection/number and text; otherwise omit it. "
            "Add a short 'Manuscript context' note: mention reported traditions "
            "about Mushaf Ali only if supported by retrieved evidence; do not assert "
            "chronological placement, parchment dimensions, script, marginal notes, "
            "or physical density as historical facts without identified manuscript "
            "evidence. If absent, say physical placement cannot be established. "
            "Keep the tone polished, substantial, pedagogically precise, and concise. "
            "Cite retrieved classical sources where available."
        )
        with st.spinner("Researching classical commentary and preparing your study module..."):
            st.session_state[key] = ask_teacher(instruction, surah, verse, verse, language)
    if key in st.session_state:
        result = st.session_state[key]
        if isinstance(result, str):
            st.markdown(result)
            st.download_button("Save study notes", result,
                               file_name=f"tafsir_{surah}_{verse}.md",
                               mime="text/markdown", key=f"save_{key}")
