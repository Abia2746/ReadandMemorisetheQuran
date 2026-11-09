import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useAppStore } from '../store';
import { MicButton, Waveform } from '../components/Layout';

type RecitationWord = { ar: string; matched?: boolean; active?: boolean };

type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: { results: ArrayLike<{ 0: { transcript: string } }> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechWindow = Window & {
  SpeechRecognition?: new () => SpeechRecognitionLike;
  webkitSpeechRecognition?: new () => SpeechRecognitionLike;
};

const normaliseArabic = (value: string) => value
  .replace(/[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]/g, '')
  .replace(/[إأآٱ]/g, 'ا')
  .replace(/ى/g, 'ي')
  .replace(/ة/g, 'ه')
  .replace(/[^\u0621-\u064A\s]/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();

function isLikelyMatch(expected: string, heard: string): boolean {
  if (expected === heard) return true;
  // Interim speech results often end in a partial word. Match only a reasonably
  // long prefix so short particles do not light up by accident.
  if (heard.length >= 2 && expected.startsWith(heard)) return true;
  if (Math.abs(expected.length - heard.length) > 1 || Math.min(expected.length, heard.length) < 3) return false;

  let previous = Array.from({ length: heard.length + 1 }, (_, index) => index);
  for (let i = 1; i <= expected.length; i += 1) {
    const current = [i];
    for (let j = 1; j <= heard.length; j += 1) {
      current[j] = Math.min(
        previous[j] + 1,
        current[j - 1] + 1,
        previous[j - 1] + (expected[i - 1] === heard[j - 1] ? 0 : 1),
      );
    }
    previous = current;
  }
  return previous[heard.length] <= 1;
}

function alignRecitation(words: RecitationWord[], transcript: string): RecitationWord[] {
  const heard = normaliseArabic(transcript).split(' ').filter(Boolean);
  let heardCursor = 0;
  let lastMatched = -1;
  const currentMatches = words.map((word) => {
    const expected = normaliseArabic(word.ar).replace(/\s/g, '');
    let foundAt = -1;
    for (let i = heardCursor; i < Math.min(heardCursor + 3, heard.length); i += 1) {
      if (isLikelyMatch(expected, heard[i])) {
        foundAt = i;
        break;
      }
    }
    if (foundAt >= 0) {
      heardCursor = foundAt + 1;
      lastMatched += 1;
    }
    return foundAt >= 0;
  });

  // Keep confirmed words lit when interim recognition revises earlier text;
  // move the subtle pulse to the newest word currently being recognised.
  const activeIndex = currentMatches.lastIndexOf(true);
  return words.map((word, index) => ({
    ...word,
    matched: Boolean(word.matched || currentMatches[index]),
    active: index === activeIndex,
  }));
}

const RecitationSurface: React.FC<{ words: RecitationWord[] }> = ({ words }) => (
  <div className="recitation-surface flex flex-wrap flex-row-reverse justify-center gap-x-2 gap-y-3 px-2 py-5" dir="rtl" lang="ar">
    {words.map((word, index) => (
      <span
        key={`${index}-${word.ar}`}
        className={`recitation-word ${word.matched ? 'is-matched' : ''} ${word.active ? 'is-active' : ''}`}
      >
        {word.ar}
      </span>
    ))}
  </div>
);

export const Recite: React.FC = () => {
  const { currentSurah, currentAyahIndex, quranCache, addStreakCredit } = useAppStore();
  const ayahData = quranCache[currentSurah]?.ayahs?.[currentAyahIndex];
  const targetText = ayahData?.text || '';
  const words = useMemo<RecitationWord[]>(() => {
    const source = ayahData?.words?.length
      ? ayahData.words
      : targetText.split(/\s+/).filter(Boolean).map((ar: string) => ({ ar }));
    return source.map((word: RecitationWord) => ({ ar: word.ar, matched: false, active: false }));
  }, [ayahData, targetText]);

  const [isListening, setIsListening] = useState(false);
  const [alignedWords, setAlignedWords] = useState<RecitationWord[]>(words);
  const [status, setStatus] = useState('Tap the microphone to begin.');
  const [transcript, setTranscript] = useState('');
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const listeningRef = useRef(false);
  const receivedSpeechRef = useRef(false);

  useEffect(() => {
    setAlignedWords(words);
    setTranscript('');
    setStatus('Tap the microphone to begin.');
    receivedSpeechRef.current = false;
  }, [words]);

  useEffect(() => () => {
    listeningRef.current = false;
    recognitionRef.current?.stop();
  }, []);

  const handleToggleListening = () => {
    if (isListening) {
      listeningRef.current = false;
      recognitionRef.current?.stop();
      recognitionRef.current = null;
      setIsListening(false);
      setStatus(receivedSpeechRef.current
        ? 'Recitation stopped. Gold highlights show words recognised by your browser.'
        : 'No recitation was recognised. Check microphone access and try again.');
      if (receivedSpeechRef.current) addStreakCredit();
      return;
    }

    const speechWindow = window as SpeechWindow;
    const Recognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setStatus('Live word highlighting is not available in this browser. Try Chrome or Edge.');
      return;
    }

    const recognition = new Recognition();
    recognition.lang = 'ar-SA';
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onresult = (event) => {
      const text = Array.from(event.results).map((result) => result[0].transcript).join(' ').trim();
      if (!text) return;
      receivedSpeechRef.current = true;
      setTranscript(text);
      setAlignedWords((current) => alignRecitation(current, text));
      setStatus('Listening · matching words as you recite');
    };
    recognition.onerror = (event) => {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        listeningRef.current = false;
        setIsListening(false);
        setStatus('Microphone access was blocked. Allow it in your browser, then try again.');
      } else if (event.error !== 'aborted' && event.error !== 'no-speech') {
        setStatus(`Speech recognition stopped (${event.error}). Try starting again.`);
      }
    };
    recognition.onend = () => {
      if (listeningRef.current) {
        try { recognition.start(); } catch { /* browser is already restarting */ }
      } else {
        setIsListening(false);
      }
    };

    try {
      receivedSpeechRef.current = false;
      setTranscript('');
      setAlignedWords(words);
      listeningRef.current = true;
      recognitionRef.current = recognition;
      recognition.start();
      setIsListening(true);
      setStatus('Listening · Arabic speech recognition is on');
    } catch {
      listeningRef.current = false;
      recognitionRef.current = null;
      setStatus('Could not start speech recognition. Check microphone access and try again.');
    }
  };

  return (
    <div className="flex flex-col p-4 space-y-5 max-w-xl mx-auto items-center">
      <section className="recitation-card w-full text-center rounded-2xl border border-amber-200/70 bg-white/70 p-5 backdrop-blur mt-4 shadow-sm">
        <span className="text-xs uppercase tracking-[0.18em] text-amber-700 font-bold">Surah {currentSurah} · Ayah {currentAyahIndex + 1}</span>
        <RecitationSurface words={alignedWords} />
        <p className="mt-1 text-sm text-zinc-600" role="status" aria-live="polite">{status}</p>
        {transcript && <p className="recognised-transcript mt-3 rounded-xl bg-white/70 px-3 py-2 text-sm text-zinc-600" dir="rtl" lang="ar" aria-label="Recognised recitation">{transcript}</p>}
      </section>

      <div className="flex flex-col items-center py-2">
        {isListening && <Waveform />}
        <MicButton isActive={isListening} onClick={handleToggleListening} />
        <p className="mt-3 max-w-xs text-center text-xs text-zinc-500">Live highlights use your browser’s Arabic speech recognition. Accuracy and delay vary by device.</p>
      </div>

      <aside className="w-full rounded-xl border border-amber-200 bg-amber-50/70 p-4 text-sm text-zinc-700" aria-label="Teacher availability">
        <p className="font-semibold text-amber-800">AI study assistant · not a live human teacher</p>
        <p className="mt-1">The live feature listens for words to highlight; it does not provide live Tajweed assessment. AI feedback is automated and should be checked with a qualified Quran teacher.</p>
      </aside>
    </div>
  );
};

export const Listen: React.FC = () => (
  <div className="text-center p-8 mt-12">
    <h2 className="text-2xl font-bold">Audio Player</h2>
    <p className="text-xs text-zinc-400 mt-2">Tap Recite tab below to use the microphone workspace.</p>
  </div>
);

export const Plan: React.FC = () => (
  <div className="text-center p-8 mt-12">
    <h2 className="text-2xl font-bold">Hifz Milestone Roadmap</h2>
    <p className="text-xs text-zinc-400 mt-2">Milestone tracking engine loaded.</p>
  </div>
);
