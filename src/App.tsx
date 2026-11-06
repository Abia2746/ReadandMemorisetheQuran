import React from 'react';
import { useAppStore } from './store';
import { TabBar } from './components/Layout';
import { Recite, Listen, Plan } from './screens/Views';

export const App: React.FC = () => {
  const { activeTab, streak } = useAppStore();
  return (
    <div className="min-h-screen w-full bg-[#FAF6EC] text-[#241C17] flex flex-col font-sans antialiased pb-24">
      <header className="sticky top-0 z-30 w-full px-4 py-3 flex items-center justify-between border-b border-zinc-200/50 bg-[#FAF6EC]/80 backdrop-blur-md">
        <h1 className="text-md font-bold bg-gradient-to-r from-amber-600 to-amber-500 bg-clip-text text-transparent">NoorHifz</h1>
        <div className="bg-amber-50 border border-amber-200/40 px-2.5 py-1 rounded-full text-xs font-semibold text-amber-700">🔥 {streak} Days</div>
      </header>
      <main className="flex-grow w-full overflow-hidden">
        {activeTab === 'recite' && <Recite />}
        {activeTab === 'listen' && <Listen />}
        {activeTab === 'plan' && <Plan />}
      </main>
      <TabBar />
    </div>
  );
};
