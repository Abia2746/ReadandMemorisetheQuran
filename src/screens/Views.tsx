import React, { useState } from 'react';
import { useAppStore } from '../store';
import { MicButton, Waveform, AyahSurface } from '../components/Layout';

export const Recite: React.FC = () => {
  const { currentSurah, currentAyahIndex, quranCache, addStreakCredit } = useAppStore();
  const [isListening, setIsListening] = useState(false);
  const [alignedWords, setAlignedWords] = useState<any[]>([]);
  
  const ayahData = quranCache[currentSurah]?.ayahs?.[currentAyahIndex];
  const targetText = ayahData?.text || '';

  const handleToggleListening = () => {
    if (isListening) {
      setIsListening(false);
      // Fallback matching to light up words on complete
      const words = targetText.split(' ').map(w => ({ ar: w, matched: true }));
      setAlignedWords(words);
      addStreakCredit();
    } else {
      setIsListening(true);
    }
  };

  return (
    <div className="flex flex-col p-4 space-y-6 max-w-xl mx-auto items-center">
      <div className="w-full text-center p-5 border border-zinc-200 rounded-xl bg-zinc-50/50 backdrop-blur mt-4">
        <span className="text-xs uppercase tracking-widest text-amber-600 font-bold">Surah {currentSurah} • Ayah {currentAyahIndex + 1}</span>
        <div className="mt-4 dir-rtl">
          <AyahSurface words={alignedWords.length ? alignedWords : (ayahData?.words || [])} />
        </div>
      </div>
      <div className="py-8">
        {isListening && <Waveform />}
        <MicButton isActive={isListening} onClick={handleToggleListening} />
      </div>
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
