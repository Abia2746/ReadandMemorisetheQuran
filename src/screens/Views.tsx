import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useAppStore } from '../store';
import { MicButton, Waveform, AyahSurface } from '../components/Layout';

type RecitationWord = { ar: string; matched?: boolean };

// Keep this independent of browser-specific SpeechRecognition TypeScript types.
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

function highlightHeardWords(words: RecitationWord[], transcript: string): RecitationWord[] {
  const heard = normaliseArabic(transcript).split(' ').filter(Boolean);
  let cursor = 0;
  return words.map((word) => {
    const expected = normaliseArabic(word.ar).replace(/\s/g, '');
    let found = false;
    // Permit a small recognition variation, but only match near the current word
    // so repeated words do not light up out of order.
    for (let i = cursor; i < Math.min(cursor + 3, heard.length); i += 1) {
      const candidate = heard[i];
      if (candidate === expected || (candidate.length >= 3 && expected.startsWith(candidate))) {
        cursor = i + 1;
        found = true;
        break;
      }
    }
    return { ...word, matched: word.matched || found };
  });
}

export const Recite: React.FC = () => {
  const { currentSurah, currentAyahIndex, quranCache, addStreakCredit } = useAppStore();
  const ayahData = quranCache[currentSurah]?.ayahs?.[currentAyahIndex];
  const targetText = ayahData?.text || '';
  const words = useMemo<RecitationWord[]>(() => {
    const source = ayahData?.words?.length
      ? ayahData.words
      : targetText.split(/\s+/).filter(Boolean).map((ar: string) => ({ ar, matched: false }));
    return source.map((word: RecitationWord) => ({ ...word, matched: false }));
  }, [ayahData, targetText]);

  const [isListening, setIsListening] = useState(false);
  const [alignedWords, setAlignedWords] = useState<RecitationWord[]>(words);
  const [status, setStatus] = useState('Tap the microphone to start reciting.');
  const [transcript, setTranscript] = useState('');
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const listeningRef = useRef(false);
  const receivedSpeechRef = useRef(false);

  useEffect(() => {
    setAlignedWords(words);
    setTranscript('');
    setStatus('Tap the microphone to start reciting.');
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
        ? 'Recitation stopped. Highlighted words are based on browser speech recognition.'
        : 'No speech was recognised. Check microphone permission and try again.');
      if (receivedSpeechRef.current) addStreakCredit();
      return;
    }

    const speechWindow = window as SpeechWindow;
    const Recognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setStatus('Live highlighting is not supported by this browser. Try Chrome or Edge.');
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
      setAlignedWords((current) => highlightHeardWords(current, text));
      setStatus('Listening and matching your recitation…');
    };
    recognition.onerror = (event) => {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        listeningRef.current = false;
        setIsListening(false);
        setStatus('Microphone access was blocked. Allow microphone access in your browser, then try again.');
      } else if (event.error !== 'aborted' && event.error !== 'no-speech') {
        setStatus(`Speech recognition stopped (${event.error}). Try starting again.`);
      }
    };
    recognition.onend = () => {
      if (listeningRef.current) {
        // Some browsers end recognition after a pause; resume while the mic is active.
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
      setStatus('Listening for Arabic recitation…');
    } catch {
      listeningRef.current = false;
      recognitionRef.current = null;
      setStatus('Could not start speech recognition. Check microphone permission and try again.');
    }
  };

  return (
    <div className="flex flex-col p-4 space-y-6 max-w-xl mx-auto items-center">
      <div className="w-full text-center p-5 border border-zinc-200 rounded-xl bg-zinc-50/50 backdrop-blur mt-4">
        <span className="text-xs uppercase tracking-widest text-amber-600 font-bold">Surah {currentSurah} • Ayah {currentAyahIndex + 1}</span>
        <div className="mt-4 dir-rtl">
          <AyahSurface words={alignedWords} />
        </div>
        <p className="mt-2 text-sm text-zinc-600" role="status" aria-live="polite">{status}</p>
        {transcript && <p className="mt-2 text-xs text-zinc-500 dir-rtl" lang="ar" aria-label="Recognised recitation">{transcript}</p>}
      </div>
      <div className="py-8 flex flex-col items-center">
        {isListening && <Waveform />}
        <MicButton isActive={isListening} onClick={handleToggleListening} />
        <p className="mt-3 text-xs text-center text-zinc-500">Words highlight as the browser recognises them. Recognition may vary by device and accent.</p>
      </div>
      <aside className="w-full rounded-xl border border-amber-200 bg-amber-50/70 p-4 text-sm text-zinc-700" aria-label="Teacher availability">
        <p className="font-semibold text-amber-800">Teacher: AI study assistant</p>
        <p className="mt-1">This app does not connect you to a live human teacher. AI feedback is automated and is not a substitute for a qualified Quran teacher.</p>
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
