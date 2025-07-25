import { create } from 'zustand';

interface UIState {
  tokenExpiryDialogOpen: boolean;
  showTokenExpiryDialog: () => void;
  hideTokenExpiryDialog: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  tokenExpiryDialogOpen: false,
  showTokenExpiryDialog: () => set({ tokenExpiryDialogOpen: true }),
  hideTokenExpiryDialog: () => set({ tokenExpiryDialogOpen: false }),
}));