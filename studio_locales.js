// Localize the entire studio shell, including dynamically created panels.
// Never translate Qur'an Arabic, published translations, user input or recitation.
const STUDIO_LOCALES = {
fa:{"Your learning companion":"همراه یادگیری شما","Your selected passage":"بخش انتخاب‌شده","How practice works":"روش تمرین","Your practice session":"جلسه تمرین شما","Live recitation":"تلاوت زنده","Listen · Repeat · Reflect":"گوش بده · تکرار کن · تأمل کن","Verses":"آیات","Words":"کلمات","Reciter":"قاری","Progress":"پیشرفت","Listen":"گوش بده","Recall":"به یاد بیاور","Recite":"تلاوت کن","Review":"مرور کن","Close":"بستن","Play this ayah":"پخش این آیه","Show hints":"نمایش راهنما","Hide hints":"پنهان کردن راهنما","Tajweed signs":"نشانه‌های تجوید","Start listening":"شروع شنیدن","Stop listening":"توقف شنیدن","Analyse repeats":"بررسی تکرارها","Follow repeated phrases":"دنبال کردن عبارت‌های تکراری","My journey":"مسیر من","Prayer Room":"اتاق نماز","Day":"روز","Night":"شب","Settings":"تنظیمات","Your Qur'an companion":"همراه قرآنی شما","Read":"بخوان","Memorise":"حفظ کن","Listen and follow":"گوش بده و دنبال کن","The Noble Qur'an":"قرآن کریم"},
ar:{"Your learning companion":"رفيقك في التعلم","Your selected passage":"المقطع المختار","How practice works":"طريقة التدريب","Your practice session":"جلسة التدريب","Live recitation":"تلاوة مباشرة","Verses":"آيات","Words":"كلمات","Reciter":"القارئ","Progress":"التقدم","Listen":"استمع","Recall":"استرجع","Recite":"اتلُ","Review":"راجع","Close":"إغلاق","Play this ayah":"تشغيل هذه الآية","Show hints":"إظهار التلميحات","Hide hints":"إخفاء التلميحات","Tajweed signs":"علامات التجويد","Start listening":"ابدأ الاستماع","Stop listening":"أوقف الاستماع","Analyse repeats":"تحليل التكرار","Follow repeated phrases":"متابعة العبارات المكررة","My journey":"رحلتي","Prayer Room":"غرفة الصلاة","Day":"نهار","Night":"ليل","Settings":"الإعدادات"},
ur:{"Your learning companion":"آپ کا تعلیمی ساتھی","Your selected passage":"منتخب حصہ","How practice works":"مشق کا طریقہ","Your practice session":"آپ کی مشق","Live recitation":"براہ راست تلاوت","Verses":"آیات","Words":"الفاظ","Reciter":"قاری","Progress":"پیش رفت","Listen":"سنیں","Recall":"یاد کریں","Recite":"تلاوت کریں","Review":"دہرائیں","Close":"بند کریں","Play this ayah":"یہ آیت چلائیں","Show hints":"اشارے دکھائیں","Tajweed signs":"تجوید کی علامات","Start listening":"سننا شروع کریں","Stop listening":"سننا بند کریں","My journey":"میرا سفر","Prayer Room":"نماز کا کمرہ","Day":"دن","Night":"رات","Settings":"ترتیبات"},
fr:{"Your learning companion":"Votre compagnon d'apprentissage","Your selected passage":"Passage sélectionné","How practice works":"Comment pratiquer","Your practice session":"Votre séance","Live recitation":"Récitation en direct","Verses":"Versets","Words":"Mots","Reciter":"Récitateur","Progress":"Progression","Listen":"Écouter","Recall":"Se rappeler","Recite":"Réciter","Review":"Réviser","Close":"Fermer","Play this ayah":"Écouter ce verset","Show hints":"Afficher les indices","Tajweed signs":"Signes de tajwid","Start listening":"Commencer l'écoute","Stop listening":"Arrêter l'écoute","My journey":"Mon parcours","Prayer Room":"Salle de prière","Day":"Jour","Night":"Nuit","Settings":"Paramètres"},
es:{"Your learning companion":"Tu compañero de aprendizaje","Your selected passage":"Pasaje seleccionado","How practice works":"Cómo practicar","Your practice session":"Tu sesión","Live recitation":"Recitación en directo","Verses":"Versículos","Words":"Palabras","Reciter":"Recitador","Progress":"Progreso","Listen":"Escuchar","Recall":"Recordar","Recite":"Recitar","Review":"Repasar","Close":"Cerrar","Play this ayah":"Reproducir este versículo","Show hints":"Mostrar pistas","Tajweed signs":"Signos de tajwid","Start listening":"Empezar a escuchar","Stop listening":"Dejar de escuchar","My journey":"Mi recorrido","Prayer Room":"Sala de oración","Day":"Día","Night":"Noche","Settings":"Ajustes"},
de:{"Your learning companion":"Dein Lernbegleiter","Your selected passage":"Ausgewählter Abschnitt","How practice works":"So funktioniert das Üben","Your practice session":"Deine Übungseinheit","Live recitation":"Live-Rezitation","Verses":"Verse","Words":"Wörter","Reciter":"Rezitator","Progress":"Fortschritt","Listen":"Anhören","Recall":"Erinnern","Recite":"Rezitiere","Review":"Wiederholen","Close":"Schließen","Play this ayah":"Diesen Vers abspielen","Show hints":"Hinweise anzeigen","Tajweed signs":"Tajwid-Zeichen","Start listening":"Zuhören starten","Stop listening":"Zuhören beenden","My journey":"Mein Weg","Prayer Room":"Gebetsraum","Day":"Tag","Night":"Nacht","Settings":"Einstellungen"},
tr:{"Your learning companion":"Öğrenme arkadaşınız","Your selected passage":"Seçilen bölüm","How practice works":"Çalışma yöntemi","Your practice session":"Çalışma oturumunuz","Live recitation":"Canlı tilavet","Verses":"Ayetler","Words":"Kelimeler","Reciter":"Kâri","Progress":"İlerleme","Listen":"Dinle","Recall":"Hatırla","Recite":"Oku","Review":"Tekrar et","Close":"Kapat","Play this ayah":"Bu ayeti çal","Show hints":"İpuçlarını göster","Tajweed signs":"Tecvid işaretleri","Start listening":"Dinlemeye başla","Stop listening":"Dinlemeyi durdur","My journey":"Yolculuğum","Prayer Room":"Namaz odası","Day":"Gündüz","Night":"Gece","Settings":"Ayarlar"},
id:{"Your learning companion":"Pendamping belajar Anda","Your selected passage":"Bagian yang dipilih","How practice works":"Cara berlatih","Your practice session":"Sesi latihan Anda","Live recitation":"Tilawah langsung","Verses":"Ayat","Words":"Kata","Reciter":"Qari","Progress":"Kemajuan","Listen":"Dengarkan","Recall":"Ingat kembali","Recite":"Baca","Review":"Ulangi","Close":"Tutup","Play this ayah":"Putar ayat ini","Show hints":"Tampilkan petunjuk","Tajweed signs":"Tanda tajwid","Start listening":"Mulai mendengarkan","Stop listening":"Berhenti mendengarkan","My journey":"Perjalananku","Prayer Room":"Ruang salat","Day":"Siang","Night":"Malam","Settings":"Pengaturan"},
ru:{"Your learning companion":"Ваш помощник в обучении","Your selected passage":"Выбранный отрывок","How practice works":"Как заниматься","Your practice session":"Ваше занятие","Live recitation":"Чтение в реальном времени","Verses":"Аяты","Words":"Слова","Reciter":"Чтец","Progress":"Прогресс","Listen":"Слушать","Recall":"Вспомнить","Recite":"Читать","Review":"Повторить","Close":"Закрыть","Play this ayah":"Воспроизвести аят","Show hints":"Показать подсказки","Tajweed signs":"Знаки таджвида","Start listening":"Начать прослушивание","Stop listening":"Остановить прослушивание","My journey":"Мой путь","Prayer Room":"Молитвенная комната","Day":"День","Night":"Ночь","Settings":"Настройки"}
};
// Complete Persian labels visible in the reader, audio player and teacher panels.
Object.assign(STUDIO_LOCALES.fa,{
"A moment with the Qur'an":"لحظه‌ای با قرآن",
"Listen · Repeat · Reflect":"گوش بده · تکرار کن · تأمل کن",
"Begin with a little, recite steadily, and review what needs attention. I can guide your practice, but detailed pronunciation should be checked against clear audio.":"با بخشی کوتاه شروع کنید، آرام و پیوسته تلاوت کنید و قسمت‌های نیازمند تمرین را مرور کنید. برای تلفظ دقیق، با صدای معتبر مقایسه کنید.",
"Ready to practise. Tap the microphone to start.":"آمادهٔ تمرین هستید. برای شروع روی میکروفون بزنید.",
"Follow the teacher's recitation at your own pace.":"با سرعت مناسب خود، تلاوت قاری را دنبال کنید.",
"Repeat-aware following uses local Qur'an speech recognition when supported. Source-matched word timings remain the fallback.":"در صورت پشتیبانی، پیگیری تکرارها از تشخیص گفتار قرآن روی دستگاه استفاده می‌کند؛ در غیر این صورت زمان‌بندی واژه‌ها به کار می‌رود.",
"Follow the word as you recite. In Memorise mode, a word is revealed only after the listener moves to the next word; this confirms progress, not correct vowels or Tajweed. Detailed phoneme verification requires a different model.":"هنگام تلاوت، واژه‌ها را دنبال کنید. در حالت حفظ، واژه پس از تشخیص واژهٔ بعدی آشکار می‌شود؛ این فقط پیشرفت را نشان می‌دهد، نه درستی حرکات و تجوید. بررسی دقیق آواها به مدل دیگری نیاز دارد.",
"Beta · word following":"آزمایشی · پیگیری واژه‌ها",
"01 · Listen":"۰۱ · گوش بده","02 · Recall":"۰۲ · به یاد بیاور","03 · Recite":"۰۳ · تلاوت کن","04 · Review":"۰۴ · مرور کن",
"Hear the ayah from your selected reciter":"آیه را با صدای قاری انتخاب‌شده گوش دهید",
"Use English clues in Memorise mode":"در حالت حفظ از راهنمای معنی استفاده کنید",
"Follow the live speech indicator when supported":"در صورت پشتیبانی، نشانگر زندهٔ گفتار را دنبال کنید",
"Record a passage below for AI-assisted feedback":"برای دریافت بازخورد کمکی هوش مصنوعی، تلاوت خود را در پایین ضبط کنید",
"✓ I repeated this passage":"✓ این بخش را تکرار کردم",
"Small, consistent repetition is more useful than rushing through verses.":"تکرار کوتاه و منظم از شتاب‌زدگی در آیات سودمندتر است.",
"Follow repeated phrases":"عبارت‌های تکراری را دنبال کن",
"Analyse repeats":"تکرارها را بررسی کن",
"Start listening":"شروع شنیدن",
"Live recitation":"تلاوت زنده",
"Quran-specific model · on-device beta":"مدل ویژهٔ قرآن · آزمایشی روی دستگاه",
"Listen to the reciter":"به تلاوت قاری گوش دهید",
"LISTEN TO THE RECITER":"به تلاوت قاری گوش دهید",
"Your selected passage":"بخش انتخاب‌شده",
"Your practice session":"جلسهٔ تمرین شما",
"Your learning companion":"همراه یادگیری شما",
"How practice works":"روش تمرین",
"Your Qur'an companion":"همراه قرآنی شما",
"Show hints":"نمایش راهنما",
"Tajweed signs":"نشانه‌های تجوید",
"0 repetitions":"۰ بار تکرار",
"English clues":"راهنمای معنی",
"Share":"اشتراک‌گذاری",
"Prayer Room":"اتاق نماز",
"Recitation practice":"تمرین تلاوت",
"Surah":"سوره","Ayahs":"آیات","words":"واژه","words reviewed":"واژه مرورشده",
"Start over":"شروع دوباره",
"Listening":"در حال شنیدن",
"Preparing Qur’an recognition SDK…":"در حال آماده‌سازی تشخیص گفتار قرآن…"
});
Object.assign(STUDIO_LOCALES.fa,{
"Follow the teacher's recitation at your own pace.":"تلاوت قاری را با سرعت مناسب خود دنبال کنید.",
"Repeat-aware following uses local Qur'an speech recognition when supported. Source-matched word timings remain the fallback.":"برای دنبال‌کردن تکرارها، در صورت پشتیبانی از تشخیص گفتار قرآن روی دستگاه استفاده می‌شود؛ در غیر این صورت زمان‌بندی واژه‌ها جایگزین است.",
"Listen to the reciter · Yasser Al-Dosari":"به تلاوت قاری گوش دهید · یاسر الدوسری",
"Follow repeated phrases":"دنبال‌کردن عبارت‌های تکراری",
"Analyse repeats":"بررسی تکرارها",
"Ready to practise. Tap the microphone to start.":"آمادهٔ تمرین هستید. برای شروع میکروفون را لمس کنید.",
"Follow the word as you recite. In Memorise mode, a word is revealed only after the listener moves to the next word; this confirms progress, not correct vowels or Tajweed. Detailed phoneme verification requires a different model.":"هنگام تلاوت، واژه‌ها را دنبال کنید. در حالت حفظ، واژه پس از رسیدن به واژهٔ بعدی آشکار می‌شود؛ این تنها نشان‌دهندهٔ پیشرفت است، نه صحت حرکات یا تجوید. بررسی دقیق آواها به مدل دیگری نیاز دارد.",
"Beta · word following":"آزمایشی · دنبال‌کردن واژه‌ها",
"Quran-specific model · on-device beta":"مدل ویژهٔ قرآن · نسخهٔ آزمایشی روی دستگاه",
"Listen deeply. Improve gently.":"با دقت گوش دهید و آرام‌آرام پیشرفت کنید.",
"Your practice session":"جلسهٔ تمرین شما",
"Your selected passage":"بخش انتخاب‌شده",
"How practice works":"روش تمرین",
"01 · Listen":"۰۱ · گوش‌دادن",
"02 · Recall":"۰۲ · یادآوری",
"03 · Recite":"۰۳ · تلاوت",
"04 · Review":"۰۴ · مرور",
"Use English clues in Memorise mode":"در حالت حفظ از راهنمای معنی استفاده کنید",
"Record a passage below for AI-assisted feedback":"برای دریافت بازخورد کمکی هوش مصنوعی، تلاوت خود را در پایین ضبط کنید",
"Hear the ayah from your selected reciter":"آیه را با صدای قاری انتخاب‌شده بشنوید",
"Follow the live speech indicator when supported":"در صورت پشتیبانی، نشانگر زندهٔ گفتار را دنبال کنید",
"0 words reviewed":"۰ واژه مرورشده",
"4 words":"۴ واژه",
"Play":"پخش",
"Pause":"مکث",
"Stop":"توقف",
"Start listening":"شروع شنیدن",
"Listen · Repeat · Reflect":"گوش بده · تکرار کن · تأمل کن",
"Begin with a little, recite steadily, and review what needs attention. I can guide your practice, but detailed pronunciation should be checked against clear audio.":"با بخشی کوتاه آغاز کنید، پیوسته تلاوت کنید و قسمت‌های نیازمند تمرین را مرور کنید. تلفظ دقیق باید با تلاوت روشن و معتبر سنجیده شود."
});
const STUDIO_PREFIX_FA={
"LISTEN TO THE RECITER · ":"به تلاوت قاری گوش دهید · ",
"Playing ":"در حال پخش ",
"Ayahs ":"آیات ",
"Surah ":"سورهٔ ",
" · 4 words · ":" · ۴ واژه · ",
" · 0 words reviewed":" · ۰ واژه مرورشده"
};
function localizeStudioShell(root,language){
 const dictionary=STUDIO_LOCALES[language]||{};
 if(!Object.keys(dictionary).length)return;
 const skipSelector=".am-mushaf,.am-translations,.am-ar-title,.am-basmala,.am-translation-ayah,[lang=ar],[contenteditable]";
 // Localize only interface chrome; never change the Quran or user-entered text.
 if(["fa","ar","ur"].includes(language)){
   root.setAttribute("dir","rtl");
   root.style.textAlign="start";
 } else {
   root.setAttribute("dir","ltr");
 }
 const normalize=t=>t.replace(/\\s+/g," ").trim();
 const translateText=original=>{
   const trimmed=normalize(original);
   if(!trimmed)return null;
   if(dictionary[trimmed])return original.replace(trimmed,dictionary[trimmed]);
   if(language==="fa"){
     for(const [prefix,replacement] of Object.entries(STUDIO_PREFIX_FA)){
       if(trimmed.startsWith(prefix))return original.replace(trimmed,replacement+trimmed.slice(prefix.length));
     }
     const prefixes={"LISTEN TO THE RECITER":"به تلاوت قاری گوش دهید","Ayahs":"آیات","Surah":"سوره","0 words reviewed":"۰ واژه مرورشده"};
     for(const [prefix,replacement] of Object.entries(prefixes)){
       if(trimmed.startsWith(prefix+" ")||trimmed.startsWith(prefix+" ·"))return original.replace(prefix,replacement);
     }
   }
   return null;
 };
 const apply=()=>{
   const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
   let node;
   while((node=walker.nextNode())){
     if(!node.parentElement||node.parentElement.closest(skipSelector))continue;
     const original=node.textContent;
     const trimmed=original.trim();
     if(!trimmed)continue;
     const translated=translateText(original);
     if(translated!==null && translated!==original)node.textContent=translated;
   }
   // Labels, placeholders, accessibility and title attributes need localization too.
   for(const el of root.querySelectorAll("button,select,option,[title],[aria-label],[placeholder]")){
     if(el.matches(".am-mushaf *,[lang=ar] *"))continue;
     for(const attr of ["title","aria-label","placeholder"]){
       const value=el.getAttribute(attr);
       if(value){
         const translated=translateText(value);
         if(translated!==null && translated!==value)el.setAttribute(attr,translated);
       }
     }
   }
 };
 apply();
 const observer=new MutationObserver(()=>{observer.disconnect();apply();observer.observe(root,{subtree:true,childList:true,characterData:true})});
 observer.observe(root,{subtree:true,childList:true,characterData:true});
 return ()=>observer.disconnect();
}
