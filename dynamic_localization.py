"""Cached, language-agnostic translation of UI chrome, never Quran text.

Uses the existing optional Gemini key. The app remains usable if unavailable;
untranslated controls explicitly fall back to English.
"""
import json
import re
import requests
import streamlit as st

CORE = [
"Your Qur'an companion","A moment with the Qur'an","The Noble Qur'an",
"Read","Memorise","Listen","My journey","Prayer Room","Share",
"Your learning companion","Listen · Repeat · Reflect","Your selected passage",
"How practice works","Your practice session","Live recitation","Tajweed signs",
"Show hints","Hide hints","Ready to practise. Tap the microphone to start.",
"Follow the teacher's recitation at your own pace.",
"Repeat-aware following uses local Qur'an speech recognition when supported. Source-matched word timings remain the fallback.",
"Follow the word as you recite. In Memorise mode, a word is revealed only after the listener moves to the next word; this confirms progress, not correct vowels or Tajweed. Detailed phoneme verification requires a different model.",
"Begin with a little, recite steadily, and review what needs attention. I can guide your practice, but detailed pronunciation should be checked against clear audio.",
"Listen to the reciter","LISTEN TO THE RECITER","Follow repeated phrases",
"Analyse repeats","Start listening","Stop listening","Start new session",
"Quran-specific model · on-device beta","Beta · word following",
"Preparing Qur’an recognition SDK…","Close","Play this ayah",
"Listen deeply. Improve gently.","Review your recitation",
"Review guidance","Your last practice review","Ask your AI teacher",
"Your question","Ask the teacher","Preparing your answer...",
"Record your recitation","Analyse this recording","Entire selected passage",
"Which ayah or passage did you recite?","Choose the ayah you actually recorded, not everything visible in the reader.",
"1. Recite just the chosen passage.","2. Use a quiet place.",
"3. Review uncertain words before attempting the passage again.",
"Speech recognition and language-model feedback cannot certify every vowel, ghunnah or madd duration.",
"Record a short passage below for optional AI-supported review. A qualified Tajweed teacher should confirm subtle pronunciation and articulation.",
"Ask about the selected verses, Qur'anic vocabulary or Tajweed terminology. AI responses can contain mistakes; verify religious rulings and precise recitation with reliable scholars.",
"Choose your Qur'an passage","Select a surah, starting and ending ayah, and reciter. Changes load automatically.",
"Surah","From ayah","To ayah","Reciter","Translation",
"AI teacher","Your practice profile","Recording review sensitivity",
"Begin in English-clue memorisation mode","Switch practice profile",
"Choose a passage and customise your practice.",
"Listen","Recall","Recite","Review","Verses","Words","Progress",
"Settings","Day","Night","Save","Cancel","Continue","Start","Finish",
"Repeat","Pause","Play","Next","Previous","Back","Today","Tomorrow",
"Prayer times","Memorisation plan","Study plan","My progress",
"Begin with a short passage. Listen, repeat and review.",
"Follow the live speech indicator when supported",
"Hear the ayah from your selected reciter",
"Use English clues in Memorise mode",
"Record a passage below for AI-assisted feedback",
"Your progress","Words reviewed","Start over","Show translation",
"Hide translation","Select language","Change reciter","Loading...",
"Please try again","No words recognised. This is a browser limitation, not evidence of a recitation mistake.",
"Tap Play to continue to the next ayah.","Reciter passage finished.",
"On-device Quran recognition active · no recitation audio sent to Gemini.",
"Quran-specific listener · follows word position, omitted/added/wrong words and skipped passages; NOT all vowels, consonant contrasts or Tajweed.",
"AI practice suggestions are not verified Tajweed grades.",
"Possible points to review","16-topic Tajweed practice checklist",
"Start a fresh recording","Reflection and context","Practice suggestion:",
"AI's possible observation:","Possible finding:","How to practise:",
"Location:","Technical details","Your practice session",
"How should your practice profile be labelled?","Your name or nickname",
"Enter the academy","Enter a name to start.",
"A quiet space to read, memorise and understand the Qur'an.",
"Your Qur'an learning journey","Prayer Room","Listen · Repeat · Reflect",
"0 repetitions","✓ I repeated this passage",
"Small, consistent repetition is more useful than rushing through verses.",
]
# Keep duplicates out, retain exact English keys for DOM lookup.
CORE = list(dict.fromkeys(CORE))

@st.cache_data(ttl=604800, show_spinner=False)
def translate_catalogue(language, api_key, existing):
    """Translate UI strings in one cached request per language, not per render."""
    if language == "en":
        return {}
    keys = [s for s in CORE if s not in existing and not re.search(r"[\u0600-\u06ff]", s)]
    if not api_key or not keys:
        return {}
    # Small batches avoid output truncation and permit partial success.
    result = {}
    for offset in range(0, len(keys), 35):
        batch = keys[offset:offset+35]
        prompt = (
            "Translate this JSON array of English software interface strings into "
            f"language code {language}. Return ONLY a JSON array of the exact same "
            "length and order. Preserve placeholders, product names, and technical "
            "accuracy. Use natural native-language UI wording, not transliteration. "
            "Do not translate Quranic Arabic or Quran verses. Input: "
            + json.dumps(batch, ensure_ascii=False)
        )
        try:
            resp = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
                headers={"x-goog-api-key": api_key, "Content-Type":"application/json"},
                json={"contents":[{"parts":[{"text":prompt}]}],
                      "generationConfig":{"temperature":0,"responseMimeType":"application/json","maxOutputTokens":8192}},
                timeout=25)
            resp.raise_for_status()
            body = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            translated = json.loads(body)
            if isinstance(translated,list) and len(translated)==len(batch):
                result.update({k:v for k,v in zip(batch,translated)
                               if isinstance(v,str) and v.strip()})
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
            continue
    return result

def get_ui_translations(language, api_key, built_in):
    return {**translate_catalogue(language, api_key, built_in), **built_in}
