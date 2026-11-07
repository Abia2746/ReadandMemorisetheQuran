"""Better hearing for Al-Mu'allim.

Drop this file next to app.py. app.py needs three one-line edits (see README at the
bottom of this file). It replaces four functions at runtime: boost, analyse,
match_report and feedback_tiles.

What it does
- Cleans the recording before any AI hears it: removes DC and rumble, reduces steady
  background noise, trims silence, converts to 16 kHz mono and normalises loudness.
- Refuses to waste API calls on a recording with no speech in it.
- Uses two independent listeners (a fast model and a stronger one) that transcribe
  WITHOUT being shown the ayah, so neither can "complete it from memory". A word is
  "correct" only if both heard it; if they disagree it is marked "unsure" instead of
  wrongly missed.
- Builds a vowel checklist from the ayah text itself (the expected harakat are known
  exactly) and asks the stronger model to judge each letter against the reference
  recording. The expected vowels are computed; the judgement of what was heard is AI.
All three Gemini calls run in parallel, so it is faster than the old sequence.
"""
import hashlib
import html as _h
import io
import json
import threading
import wave

import numpy as np
import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

G = {}
_ORIG = {}
_STATS = {}
_ASR = {}

MARKS = {
    "\u064E": "fatha", "\u064F": "damma", "\u0650": "kasra", "\u064B": "fathatan",
    "\u064C": "dammatan", "\u064D": "kasratan", "\u0651": "shadda", "\u0652": "sukun",
    "\u0670": "dagger alif", "\u0653": "maddah",
}


def _sha(b):
    return hashlib.sha1(b).hexdigest()


def _cap(d, n=24):
    while len(d) > n:
        d.pop(next(iter(d)))


# ---------------------------------------------------------------- audio cleaning

def _denoise(x, sr=16000, n=512, hop=128):
    """Mild spectral subtraction. The noise floor is the quiet 10th percentile of each
    frequency bin; the 0.15 floor keeps speech from turning metallic."""
    if len(x) < n * 4:
        return x
    win = np.hanning(n).astype(np.float32)
    pad = np.pad(x, (n, n))
    frames = 1 + (len(pad) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(frames)[:, None]
    spec = np.fft.rfft(pad[idx] * win, axis=1)
    mag, phase = np.abs(spec), np.angle(spec)
    noise = np.percentile(mag, 10, axis=0)
    clean = np.maximum(mag - 1.3 * noise, 0.15 * mag)
    clean[:, np.fft.rfftfreq(n, 1 / sr) < 70] = 0  # rumble and handling noise
    frames_out = np.fft.irfft(clean * np.exp(1j * phase), n=n, axis=1) * win
    y = np.zeros(len(pad), dtype=np.float32)
    wsum = np.zeros(len(pad), dtype=np.float32)
    for i in range(frames):
        y[i * hop:i * hop + n] += frames_out[i]
        wsum[i * hop:i * hop + n] += win ** 2
    return (y / np.maximum(wsum, 1e-6))[n:n + len(x)]


def enhance(wav_bytes):
    """Returns (clean 16 kHz mono WAV, stats). Never raises: on any problem the
    original bytes come back with ok=False."""
    try:
        with wave.open(io.BytesIO(wav_bytes)) as w:
            ch, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
            raw = w.readframes(w.getnframes())
        if width != 2 or not raw:
            return wav_bytes, {"ok": False}
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if ch > 1:
            x = x[: len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
        x = x - x.mean()
        peak_before = float(np.percentile(np.abs(x), 99.5)) if x.size else 0.0

        if rate != 16000:
            if rate % 16000 == 0:
                k = rate // 16000
                x = x[: len(x) // k * k].reshape(-1, k).mean(axis=1)
            else:
                n = int(len(x) * 16000 / rate)
                x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
        x = x.astype(np.float32)

        frame = 320  # 20 ms
        nfr = len(x) // frame
        if nfr < 10:
            return wav_bytes, {"ok": False, "no_speech": True, "peak": peak_before}
        rms = np.sqrt((x[: nfr * frame].reshape(nfr, frame) ** 2).mean(axis=1))
        floor = float(np.percentile(rms, 10)) + 1e-6
        top = float(np.percentile(rms, 95)) + 1e-6
        snr = 20 * np.log10(top / floor)

        if snr < 30:  # clean rooms do not need it, and every filter costs some detail
            x = _denoise(x)
            rms = np.sqrt((x[: nfr * frame].reshape(nfr, frame) ** 2).mean(axis=1))
            floor = float(np.percentile(rms, 10)) + 1e-6
            top = float(np.percentile(rms, 95)) + 1e-6

        thr = max(floor * 3.0, top * 0.08)
        speech = rms > thr
        speech_s = float(speech.sum()) * 0.02
        if speech_s < 0.6:
            return wav_bytes, {"ok": False, "no_speech": True, "peak": peak_before,
                               "snr_db": float(snr)}
        hits = np.flatnonzero(speech)
        start = max(0, hits[0] - 15) * frame      # 300 ms of padding either side
        end = min(nfr, hits[-1] + 16) * frame
        x = x[start:end]

        p = float(np.percentile(np.abs(x), 99.5)) + 1e-6
        gain = min(0.9 / p, 300.0)
        y = np.clip(x * gain, -1.0, 1.0)
        out = io.BytesIO()
        with wave.open(out, "wb") as w2:
            w2.setnchannels(1)
            w2.setsampwidth(2)
            w2.setframerate(16000)
            w2.writeframes((y * 32767).astype(np.int16).tobytes())
        data = out.getvalue()
        stats = {"ok": True, "speech_s": round(speech_s, 1), "snr_db": round(float(snr)),
                 "peak": peak_before, "gain": round(gain, 1)}
        _STATS[_sha(data)] = stats
        _cap(_STATS)
        return data, stats
    except Exception:
        return wav_bytes, {"ok": False}


def boost_v2(wav_bytes, gain_cap=400.0):
    data, stats = enhance(wav_bytes)
    if stats.get("no_speech"):
        _STATS[_sha(data)] = stats
        _cap(_STATS)
    return data, float(stats.get("peak", 1.0))


# ------------------------------------------------------------ expected vowels

def units(word):
    """Split an Uthmani word into letter units, each with the marks it carries."""
    out = []
    for ch in word:
        if ch in MARKS:
            if out:
                out[-1]["m"].append(MARKS[ch])
                out[-1]["t"] += ch
        elif "\u0621" <= ch <= "\u064A" or ch == "\u0671":
            out.append({"t": ch, "m": []})
    return out


def _parallel(fns):
    ctx = get_script_run_ctx()
    out = [None] * len(fns)

    def run(i, f):
        try:
            out[i] = f()
        except Exception:
            out[i] = None

    threads = [threading.Thread(target=run, args=(i, f), daemon=True) for i, f in enumerate(fns)]
    for t in threads:
        try:
            add_script_run_ctx(t, ctx)
        except Exception:
            pass
        t.start()
    for t in threads:
        t.join()
    return out


ASR_PROMPT = ("Transcribe this Qur'an recitation exactly as actually spoken, in Arabic script "
              "(diacritics optional). Do NOT correct it and do NOT complete it from memory: write only "
              "the words you actually hear, including mistakes, repeats and skipped words. If there is "
              "no speech output exactly: [inaudible]")


def analyse_v2(verse, ref_mp3, student_wav, reciter, rules, strict, heard):
    stats = _STATS.get(_sha(student_wav), {})
    if stats.get("no_speech"):
        return {}

    expected = []
    for w in verse.split():
        u = units(w)
        if u:
            expected.append({"w": len(expected), "t": w,
                             "u": [{"i": k, "t": x["t"], "m": x["m"]} for k, x in enumerate(u)]})

    prompt = f"""You are an expert Qur'an tajweed teacher. Clip 1 is a reference recitation by {reciter} of this ayah: {verse}
Clip 2 is a student reciting it from memory. Marking strictness: {strict}.
Listen to both and compare. Report only what you can clearly hear; when unsure say so; never invent mistakes. If clip 2 is silent or is not this ayah, set overall_score to 0 and leave every list empty.
VOWEL CHECKLIST: below, each word is split into letter units with the vowel marks each carries. For every word return "codes": a string with exactly one character per unit, in order: o = correct (vowel, sukun, shaddah or length), x = clearly wrong (wrong vowel, wrong length, wrong letter), ? = cannot tell, - = the student skipped the word. Letters without marks (madd letters) are judged on length. For each x add a note giving the unit index, what was expected and what you heard. Use ? rather than x unless the difference is clear.
CHECKLIST: {json.dumps(expected, ensure_ascii=False)}
Also compare breath control (where each reciter breathes or pauses). Judge each of these tajweed categories that occurs, citing roughly where (seconds): {rules}
Write in English; Arabic words in script plus transliteration.
Return JSON only: {{"overall_score":int,"words_vowels":[{{"w":int,"codes":"","notes":[{{"i":int,"expected":"","heard":""}}]}}],"rules_check":[{{"rule":"","word":"","verdict":"correct|partly|missed|unclear","evidence":"","confidence":"high|medium|low"}}],"breath":{{"reference":"","student":"","tip":""}},"spoken_summary":"max 60 words, warm","words":[{{"word":"","status":"good|needs_work","student_did":"","correction":""}}],"practice_tip":""}}"""

    call, part = G["call_gemini"], G["audio_part"]

    def listen(pro):
        return lambda: call([{"text": ASR_PROMPT}, part(student_wav, "audio/wav")], False, pro)

    def judge():
        return call([{"text": prompt}, {"text": "Clip 1 (reference):"}, part(ref_mp3, "audio/mpeg"),
                     {"text": "Clip 2 (student):"}, part(student_wav, "audio/wav")], True, True)

    ta, tb, jr = _parallel([listen(False), listen(True), judge])
    ta = "" if not ta or "[inaudible]" in str(ta).lower() else str(ta).strip()
    tb = "" if not tb or "[inaudible]" in str(tb).lower() else str(tb).strip()
    jr = jr if isinstance(jr, dict) else {}
    heard_text = ta or tb
    if not heard_text and not jr.get("overall_score"):
        return {}

    _ASR[heard_text] = (ta, tb)
    _cap(_ASR)

    result = {k: v for k, v in jr.items() if k != "words_vowels"}
    result["heard_text"] = heard_text
    result["audio_stats"] = stats
    if not jr:
        result.setdefault("overall_score", 0)
        result["spoken_summary"] = ("I could hear you, and the word check below is based on that, but "
                                    "the detailed vowel analysis service was busy. Try once more.")

    by_word = {}
    for d in jr.get("words_vowels") or []:
        if isinstance(d, dict) and str(d.get("w", "")).lstrip("-").isdigit():
            by_word[int(d["w"])] = d
    report = []
    for e in expected:
        d = by_word.get(e["w"], {})
        codes = str(d.get("codes", ""))
        if len(codes) != len(e["u"]):
            codes = "?" * len(e["u"])
        notes = {}
        for n in d.get("notes") or []:
            if isinstance(n, dict) and str(n.get("i", "")).isdigit():
                notes[int(n["i"])] = n
        report.append({"word": e["t"], "units": [
            {"t": u["t"], "c": codes[k], "n": notes.get(k)} for k, u in enumerate(e["u"])]})
    if jr:
        result["vowel_report"] = report
    return result


# ------------------------------------------------------- consensus word states

def _combine(a, b):
    if a == b:
        return a
    if {a, b} == {"correct", "close"}:
        return "close"
    return "unsure"


def match_report_v2(words_ar, heard):
    pair = _ASR.get(heard)
    if not pair:
        return _ORIG["match"](words_ar, heard)
    norm, align = G["norm_ar"], G["nw_align"]
    expected = [w for w in ("".join(norm(x)) for x in words_ar) if w]
    heard_lists = [norm(t) for t in pair]
    if not expected or max((len(h) for h in heard_lists), default=0) < 0.25 * len(expected):
        return None
    runs = [align(expected, h)[0] for h in heard_lists if h]
    if len(runs) == 2:
        states = [_combine(a, b) for a, b in zip(*runs)]
        agree = sum(a == b for a, b in zip(*runs)) / len(expected)
    else:
        states, agree = runs[0], 1.0
    points = sum(1.0 if s == "correct" else 0.5 if s in ("close", "unsure") else 0.0 for s in states)
    longest = max(heard_lists, key=len)
    return {
        "pct": round(100 * points / len(expected)), "states": states,
        "missing": [w for w, s in zip(expected, states) if s == "missed"],
        "extra": align(expected, longest)[1], "n_ok": states.count("correct"),
        "total": len(expected), "unsure": states.count("unsure"), "agree": round(agree * 100),
    }


def feedback_tiles_v2(words, states):
    marks = {"correct": "\u2713", "close": "\u2022", "missed": "\u2715", "unsure": "?"}
    tiles = "".join(
        f'<span class="ft {s}" style="animation-delay:{200 + i * 40}ms'
        + (';background:rgba(128,128,128,.18);box-shadow:inset 0 -3px #8A8A8A' if s == "unsure" else "")
        + f'">{_h.escape(w["ar"])}<small>{marks.get(s, "")}</small></span>'
        for i, (w, s) in enumerate(zip(words, states)))
    return f'<div class="glass ayahbox">{tiles}</div>'


# ------------------------------------------------------------------- display

_CSS = ("<style>.vw{display:inline-block;margin:6px 10px;direction:rtl;white-space:nowrap}"
        ".vu{display:inline-block;margin:2px;padding:0 8px;border-radius:10px;"
        "font-family:'Amiri Quran',serif;font-size:1.7rem;line-height:2}"
        ".vu.o{background:rgba(46,125,91,.22)}.vu.x{background:rgba(192,69,58,.32)}"
        ".vu.q{background:rgba(128,128,128,.22)}.vu.s{background:rgba(192,69,58,.12);"
        "text-decoration:line-through}</style>")


def render_vowels(analysis):
    report = (analysis or {}).get("vowel_report")
    if not report:
        return
    cls = {"o": "o", "x": "x", "?": "q", "-": "s"}
    count = {"o": 0, "x": 0, "?": 0, "-": 0}
    blocks, wrong = [], []
    for w in report:
        spans = []
        for u in w["units"]:
            c = u["c"] if u["c"] in cls else "?"
            count[c] += 1
            title = ""
            if u.get("n"):
                title = f' title="expected {_h.escape(str(u["n"].get("expected", "")))} heard {_h.escape(str(u["n"].get("heard", "")))}"'
                wrong.append((w["word"], u["t"], u["n"]))
            spans.append(f'<span class="vu {cls[c]}"{title}>{_h.escape(u["t"])}</span>')
        blocks.append('<span class="vw">' + "".join(spans) + "</span>")

    st.markdown("#### Vowel by vowel")
    st.markdown(_CSS + "<div style='direction:rtl;text-align:center'>" + "".join(blocks) + "</div>",
                unsafe_allow_html=True)
    total = sum(count.values())
    st.caption(f"{total} letters checked: {count['o']} correct, {count['x']} wrong, "
               f"{count['?']} unclear, {count['-']} in skipped words. Green = correct, red = wrong, "
               "grey = the listener could not tell, struck through = word skipped.")
    for word, unit, n in wrong[:12]:
        st.markdown(f"- **{unit}** in {word}: expected {n.get('expected', '?')}, "
                    f"heard {n.get('heard', '?')}")
    stats = analysis.get("audio_stats") or {}
    if stats.get("ok"):
        st.caption(f"Audio: {stats['speech_s']}s of speech, signal-to-noise about {stats['snr_db']} dB. "
                   "This is an AI listener: it can miss subtle vowels, so check anything important "
                   "with a qualified teacher.")


def install(g):
    """Call once per run, after app.py has defined its own functions."""
    G.clear()
    G.update(g)
    _ORIG["match"] = g["match_report"]
    g["boost"] = boost_v2
    g["analyse"] = analyse_v2
    g["match_report"] = match_report_v2
    g["feedback_tiles"] = feedback_tiles_v2


# README: three one-line edits in app.py
# 1. Immediately above the line that is only `apply_theme()` (just before
#    `if st.session_state.app_phase == "onboarding":`) add these two lines:
#        import hearing
#        hearing.install(globals())
# 2. In the Recite tab, immediately above the line starting
#    `card("What I heard you recite: "` add (same indentation):
#        hearing.render_vowels(analysis)
