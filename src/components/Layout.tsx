import React from 'react';
import { useAppStore } from '../store';

export const Waveform: React.FC = () => (
  <div className="flex items-center justify-center space-x-1 h-8 my-2" aria-hidden="true">
    {[1, 2, 3, 4, 5].map((i) => (
      <div key={i} className="w-1 h-6 bg-amber-500 rounded-full animate-noor-bar" style={{ animationDelay: `${i * 0.15}s` }} />
    ))}
  </div>
);

interface MicProps { isActive: boolean; onClick: () => void; }
export const MicButton: React.FC<MicProps> = ({ isActive, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    aria-label={isActive ? 'Stop live recitation recognition' : 'Start live recitation recognition'}
    className={`w-20 h-20 rounded-full flex items-center justify-center transition-all shadow-lg focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-4 focus-visible:outline-amber-800 ${isActive ? 'bg-red-600 ring-4 ring-red-200' : 'bg-amber-600 hover:bg-amber-700'}`}
  >
    <span className="text-xl" aria-hidden="true">{isActive ? '⏹️' : '🎙️'}</span>
  </button>
);

export const TabBar: React.FC = () => {
  const { activeTab, setActiveTab } = useAppStore();
  const tabs = [{ id: 'recite', label: 'Recite' }, { id: 'listen', label: 'Listen' }, { id: 'plan', label: 'Plan' }] as const;
  return (
    <nav aria-label="Main navigation" className="fixed bottom-0 left-0 right-0 border-t border-zinc-300 bg-[#FAF6EC]/95 backdrop-blur px-4 py-3 flex justify-around items-center">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          aria-current={activeTab === tab.id ? 'page' : undefined}
          onClick={() => setActiveTab(tab.id)}
          className={`min-h-11 px-4 text-xs uppercase font-bold tracking-wider focus-visible:outline focus-visible:outline-2 focus-visible:outline-amber-900 ${activeTab === tab.id ? 'text-amber-900 scale-105' : 'text-zinc-700'}`}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
};

export const AyahSurface: React.FC<{ words: Array<{ ar: string; matched?: boolean; active?: boolean }> }> = ({ words }) => (
  <div className="flex flex-wrap flex-row-reverse justify-center gap-x-2 gap-y-3 px-2 py-4" dir="rtl" lang="ar">
    {words.map((word, idx) => (
      <span
        key={`${idx}-${word.ar}`}
        className={`inline-block rounded-lg px-2 py-1 text-3xl font-bold transition-all ${word.active ? 'bg-amber-200 text-amber-950 ring-2 ring-amber-700 shadow-md' : word.matched ? 'bg-amber-100 text-amber-900' : 'text-zinc-900'}`}
        aria-current={word.active ? 'true' : undefined}
      >
        {word.ar}
      </span>
    ))}
  </div>
);
