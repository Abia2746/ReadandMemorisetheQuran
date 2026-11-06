import { create } from 'zustand';

interface AppState {
  activeTab: 'recite' | 'listen' | 'lesson' | 'plan';
  theme: 'light' | 'dark';
  streak: number;
  currentSurah: number;
  currentAyahIndex: number;
  preferredTeacher: 'male' | 'female';
  currentPlan: any | null;
  quranCache: Record<number, any>;
  setActiveTab: (tab: 'recite' | 'listen' | 'lesson' | 'plan') => void;
  setTheme: (theme: 'light' | 'dark') => void;
  addStreakCredit: () => void;
  setPlan: (plan: any) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeTab: 'recite',
  theme: 'light',
  streak: 3,
  currentSurah: 1,
  currentAyahIndex: 0,
  preferredTeacher: 'male',
  currentPlan: null,
  quranCache: {
    1: {
      name: "Al-Fātiḥah",
      ayahs: [
        { text: "الحمد لله رب العالمين", words: [{ ar: "الحمد", matched: false }, { ar: "لله", matched: false }, { ar: "رب", matched: false }, { ar: "العالمين", matched: false }] }
      ]
    }
  },
  setActiveTab: (tab) => set({ activeTab: tab }),
  setTheme: (theme) => set({ theme }),
  addStreakCredit: () => set((state) => ({ streak: state.streak + 1 })),
  setPlan: (plan) => set({ currentPlan: plan }),
}));
