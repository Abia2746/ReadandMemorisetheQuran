import React, { useMemo } from 'react';
import { useAppStore } from '../store';
import { MicButton, Waveform, AyahSurface } from '../components/Layout';
import { useLiveRecitation } from '../live';

type QuranWord = { ar: string; matched?: boolean; active?: boolean };

export const Recite: React.FC = () => {
  const { currentSurah, currentAyahIndex, quranCache } = useAppStore();
  const ayahData = quranCache[currentSurah]?.ayahs?.[currentAyahIndex];
  const text = ayahData?.text || '';
  const words = useMemo<QuranWord[]>(() => {
    const source = Array.isArray(ayahData?.words) && ayahData.words.length
      ? ayahData.words
      : text.split(/\s+/).filter(Boolean).map((ar: string) => ({ ar }));
    return source
      .map((word: QuranWord) => ({ ar: word.ar, matched: false, active: false }))
      .filter((word: QuranWord) => Boolean(word.ar));
  }, [ayahData, text]);
  const controls = useLiveRecitation(words.map((word) => word.ar));
  const displayedWords = words.map((word, index) => ({
    ...word,
    matched: controls.states[index] === 'correct' || controls.states[index] === 'close',
    active: controls.activeIndex === index,
  }));

  return (
    <div className="flex flex-col p-4 space-y-5 max-w-xl mx-auto items-center">
      <section className="w-full text-center p-5 border border-zinc-200 rounded-xl bg-zinc-50/70 backdrop-blur mt-4" aria-label="Current ayah">
        <span className="text-xs uppercase tracking-widest text-amber-700 font-bold">
          Surah {currentSurah} · Ayah {currentAyahIndex + 1}
        </span>
        <div className="mt-4 dir-rtl">
          <AyahSurface words={displayedWords} />
        </div>
        <p className="mt-2 text-sm text-zinc-700" role="status" aria-live="polite">{controls.statusMessage}</p>
        {controls.transcript && (
          <p className="mt-2 rounded-lg bg-white/70 p-3 text-sm text-zinc-600 dir-rtl" lang="ar" aria-label="Recognized Arabic transcript">
            {controls.transcript}
          </p>
        )}
        {controls.status === 'listening' && (
          <p className="mt-2 text-xs text-zinc-500">Matched {controls.matched} of {words.length} ayah words · current position {Math.min(controls.cursor + 1, words.length)} of {words.length}</p>
        )}
        {controls.status === 'error' && (
          <button type="button" className="mt-3 rounded-full border border-amber-700 px-4 py-2 text-sm font-semibold text-amber-900" onClick={controls.start}>Retry recognition</button>
        )}
      </section>

      <div className="flex flex-col items-center py-4">
        {controls.listening && <Waveform />}
        <MicButton isActive={controls.listening} onClick={controls.listening ? controls.stop : controls.start} />
        <p className="mt-3 max-w-sm text-center text-xs text-zinc-600">Engine: {controls.engine === 'browser-speech' ? 'browser speech recognition' : 'unavailable in this browser'}. No permanent API key or unverified transcript is used on this page.</p>
      </div>

      <aside className="w-full rounded-xl border border-amber-200 bg-amber-50/70 p-4 text-sm text-zinc-700" aria-label="AI teacher connection status">
        <p className="font-semibold text-amber-900">AI voice teacher: not connected in this page</p>
        <p className="mt-1">This React page has no persistent Gemini Live connection. The separate Streamlit classroom supports submitted, turn-by-turn AI voice/chat responses, not a continuously connected tutor. A true live tutor needs a secure server to issue short-lived session credentials; a permanent API key must not be put in browser code.</p>
      </aside>
    </div>
  );
};

export const Listen: React.FC = () => (
  <div className="text-center p-8 mt-12">
    <h2 className="text-2xl font-bold">Audio Player</h2>
    <p className="text-xs text-zinc-500 mt-2">Audio range playback is not connected in this React screen yet. Use the Streamlit classroom for the existing listening and lesson tools.</p>
  </div>
);

export const Plan: React.FC = () => (
  <div className="text-center p-8 mt-12">
    <h2 className="text-2xl font-bold">Hifz Milestone Roadmap</h2>
    <p className="text-xs text-zinc-500 mt-2">Plan wizard integration is not connected in this React screen. The existing Streamlit app contains the plan wizard.</p>
  </div>
);
