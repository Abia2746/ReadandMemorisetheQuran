"""Quran.com-supported language and verse-translation catalogue.

Arabic Uthmani text never changes. Translation is sourced from published
Quran.com resources, not generated or silently presented as authoritative.
"""
import re
import requests
import streamlit as st

API = "https://api.quran.com/api/v4"
FALLBACK_LANGUAGES = {"en": "English", "ar": "العربية", "fa": "فارسی", "ur": "اردو", "fr": "Français", "de": "Deutsch", "es": "Español", "tr": "Türkçe", "id": "Bahasa Indonesia", "bn": "বাংলা", "hi": "हिन्दी", "ru": "Русский", "pt": "Português", "zh": "中文", "ms": "Bahasa Melayu", "sw": "Kiswahili"}

@st.cache_data(ttl=86400, show_spinner=False)
def available_translations():
    """Return (language labels, preferred translation IDs); never fabricate resources."""
    labels = dict(FALLBACK_LANGUAGES)
    resources = {}
    try:
        response = requests.get(f"{API}/resources/translations", timeout=12)
        response.raise_for_status()
        for row in response.json().get("translations", []):
            code = str(row.get("language_name") or "").strip().lower()
            # Quran.com translations use language_name (e.g. 'english')
            # and occasionally language ISO codes in nested metadata.
            iso = str(row.get("language_code") or row.get("iso_code") or "").strip().lower()
            if not iso:
                iso = LANGUAGE_NAMES.get(code, "")
            if not re.fullmatch(r"[a-z]{2,3}(?:-[a-z]{2,4})?", iso):
                continue
            labels.setdefault(iso, str(row.get("language_name") or iso).title())
            try:
                resource_id = int(row["id"])
            except (KeyError, TypeError, ValueError):
                continue
            if iso not in resources or row.get("is_default"):
                resources[iso] = resource_id
    except (requests.RequestException, ValueError, TypeError):
        pass
    try:
        response = requests.get(f"{API}/resources/languages", timeout=12)
        response.raise_for_status()
        for row in response.json().get("languages", []):
            iso = str(row.get("iso_code") or "").strip().lower()
            if re.fullmatch(r"[a-z]{2,3}(?:-[a-z]{2,4})?", iso):
                labels[iso] = str(row.get("native_name") or row.get("name") or labels.get(iso, iso))
    except (requests.RequestException, ValueError, TypeError):
        pass
    labels["en"] = "English"
    return labels, resources

LANGUAGE_NAMES = {
    "english":"en","arabic":"ar","persian":"fa","farsi":"fa",
    "urdu":"ur","french":"fr","german":"de","spanish":"es",
    "turkish":"tr","indonesian":"id","bengali":"bn","hindi":"hi",
    "russian":"ru","portuguese":"pt","chinese":"zh","malay":"ms",
    "swahili":"sw","italian":"it","dutch":"nl","japanese":"ja",
    "korean":"ko","tamil":"ta","telugu":"te","punjabi":"pa",
    "somali":"so","uzbek":"uz","azerbaijani":"az","bosnian":"bs",
    "albanian":"sq","kurdish":"ku","thai":"th","vietnamese":"vi",
    "amharic":"am","hausa":"ha","yoruba":"yo","malayalam":"ml",
    "marathi":"mr","nepali":"ne","sindhi":"sd","pashto":"ps",
}

@st.cache_data(ttl=3600, show_spinner=False)
def translated_verses(surah, first, last, translation_id):
    if not translation_id:
        return {}
    output = {}
    for ayah in range(first, last + 1):
        try:
            response = requests.get(
                f"{API}/verses/by_key/{surah}:{ayah}",
                params={"translations": int(translation_id)}, timeout=12)
            response.raise_for_status()
            entries = response.json().get("verse", {}).get("translations") or []
            matching = next((x for x in entries if int(x.get("resource_id", -1)) == int(translation_id)), None)
            if matching and matching.get("text"):
                output[ayah] = re.sub(r"<[^>]*>", "", str(matching["text"])).strip()
        except (requests.RequestException, ValueError, TypeError):
            continue
    return output

UI_STRINGS = {
 "en":{"read":"Read","cover":"Memorise","listen":"Listen","journey":"My journey","quran":"The Noble Qur'an","memorise":"Memorise with meaning","follow":"Listen and follow","hints":"Show hints","reset":"Start over","translation":"Translation","unavailable":"No published translation is available for this selection. English meanings remain available.","practice":"Your Qur'an companion"},
 "ar":{"read":"اقرأ","cover":"احفظ","listen":"استمع","journey":"رحلتي","quran":"القرآن الكريم","memorise":"الحفظ مع المعنى","follow":"استمع وتابع","hints":"إظهار المساعدة","reset":"ابدأ من جديد","translation":"الترجمة","unavailable":"الترجمة غير متاحة؛ تُعرض المعاني الإنجليزية.","practice":"رفيقك مع القرآن"},
 "fa":{"read":"بخوان","cover":"حفظ کن","listen":"گوش بده","journey":"مسیر من","quran":"قرآن کریم","memorise":"حفظ با معنا","follow":"گوش بده و دنبال کن","hints":"نمایش راهنما","reset":"شروع دوباره","translation":"ترجمه","unavailable":"ترجمه در دسترس نیست؛ معانی انگلیسی نمایش داده می‌شود.","practice":"همراه قرآنی شما"},
 "ur":{"read":"پڑھیں","cover":"حفظ کریں","listen":"سنیں","journey":"میرا سفر","quran":"قرآن مجید","memorise":"معنی کے ساتھ حفظ","follow":"سنیں اور ساتھ پڑھیں","hints":"اشارے دکھائیں","reset":"دوبارہ شروع","translation":"ترجمہ","unavailable":"ترجمہ دستیاب نہیں؛ انگریزی معنی دکھائے جائیں گے۔","practice":"آپ کا قرآنی ساتھی"},
 "fr":{"read":"Lire","cover":"Mémoriser","listen":"Écouter","journey":"Mon parcours","quran":"Le Noble Coran","memorise":"Mémoriser avec le sens","follow":"Écouter et suivre","hints":"Afficher les indices","reset":"Recommencer","translation":"Traduction","unavailable":"Traduction indisponible ; les sens anglais restent affichés.","practice":"Votre compagnon du Coran"},
 "es":{"read":"Leer","cover":"Memorizar","listen":"Escuchar","journey":"Mi recorrido","quran":"El Noble Corán","memorise":"Memorizar con significado","follow":"Escuchar y seguir","hints":"Mostrar pistas","reset":"Empezar de nuevo","translation":"Traducción","unavailable":"Traducción no disponible; se muestran significados en inglés.","practice":"Tu compañero del Corán"},
 "de":{"read":"Lesen","cover":"Auswendig lernen","listen":"Anhören","journey":"Mein Weg","quran":"Der edle Koran","memorise":"Mit Bedeutung lernen","follow":"Hören und folgen","hints":"Hinweise anzeigen","reset":"Neu beginnen","translation":"Übersetzung","unavailable":"Keine Übersetzung verfügbar; englische Bedeutungen bleiben sichtbar.","practice":"Dein Koranbegleiter"},
 "tr":{"read":"Oku","cover":"Ezberle","listen":"Dinle","journey":"Yolculuğum","quran":"Kur'an-ı Kerim","memorise":"Anlamıyla ezberle","follow":"Dinle ve takip et","hints":"İpuçlarını göster","reset":"Baştan başla","translation":"Meal","unavailable":"Çeviri mevcut değil; İngilizce anlamlar gösterilir.","practice":"Kur'an yol arkadaşınız"},
 "id":{"read":"Baca","cover":"Hafalkan","listen":"Dengarkan","journey":"Perjalananku","quran":"Al-Qur'an","memorise":"Hafalkan dengan makna","follow":"Dengarkan dan ikuti","hints":"Tampilkan petunjuk","reset":"Mulai ulang","translation":"Terjemahan","unavailable":"Terjemahan tidak tersedia; makna bahasa Inggris ditampilkan.","practice":"Teman Al-Qur'an Anda"},
 "ru":{"read":"Читать","cover":"Заучивать","listen":"Слушать","journey":"Мой путь","quran":"Священный Коран","memorise":"Заучивать со смыслом","follow":"Слушать и следить","hints":"Показать подсказки","reset":"Начать заново","translation":"Перевод","unavailable":"Перевод недоступен; показаны английские значения.","practice":"Ваш спутник в изучении Корана"},
}
