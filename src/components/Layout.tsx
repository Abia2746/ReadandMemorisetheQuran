import React from 'react';
import { useAppStore } from '../store';

export const Waveform: React.FC = () => (
  <div className="flex items-center justify-center space-x-1 h-8 my-2">
    {[1, 2, 3, 4, 5].map((i) => (
      <div key={i} className="w-1 bg-amber-500 rounded-full animate-noor-bar" style={{ animationDelay: `${i * 0.15}s` }} />
    ))}
  </div>
);

interface MicProps { isActive: boolean; onClick: () => void; }
export const MicButton: React.FC<MicProps> = ({ isActive, onClick }) => (
  <button onClick={onClick} className={`w-20 h-20 rounded-full flex items-center justify-center transition-all shadow-lg ${isActive ? 'bg-red-500 ring-4 ring-red-200' : 'bg-amber-500 hover:bg-amber-600'}`}>
    <span className="text-xl">{isActive ? "🛑" : "🎙️"}</span>
  </button>
);

export const TabBar: React.FC = () => {
  const { activeTab, setActiveTab } = useAppStore();
  const tabs = [{ id: 'recite', label: 'Recite' }, { id: 'listen', label: 'Listen' }, { id: 'plan', label: 'Plan' }] as const;
  return (
    <div className="fixed bottom-0 left-0 right-0 border-t border-zinc-200 bg-[#FAF6EC]/95 backdrop-blur px-4 py-3 flex justify-around items-center">
      {tabs.map((tab) => (
        <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={`text-xs uppercase font-bold tracking-wider ${activeTab === tab.id ? 'text-amber-600 scale-105' : 'text-zinc-400'}`}>
          {tab.label}
        </button>
      ))}
    </div>
  );
};

export const AyahSurface: React.FC<{ words: any[] }> = ({ words }) => (
  <div className="flex flex-wrap flex-row-reverse justify-center gap-x-3 gap-y-4 px-2 py-4">
    {words.map((word, idx) => (
      <span key={idx} className={`px-1.5 py-0.5 rounded text-3xl font-bold transition-all ${word.matched ? 'text-amber-600 bg-amber-50' : 'text-zinc-800'}`}>
        {word.ar}
      </span>
    ))}
  </div>
);
