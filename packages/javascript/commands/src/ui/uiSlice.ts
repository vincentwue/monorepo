import { createSlice, PayloadAction } from "@reduxjs/toolkit";

// -----------------------------------------------------------------------------
// 🎛️ State
// -----------------------------------------------------------------------------
interface PaletteHistoryEntry {
  query: string;
  timestamp: number;
}

interface UiState {
  isPaletteOpen: boolean;
  paletteQuery: string;
  paletteSelection: number;
  searchHistory: PaletteHistoryEntry[];
}

const initialState: UiState = {
  isPaletteOpen: false,
  paletteQuery: "",
  paletteSelection: 0,
  searchHistory: [],
};

// -----------------------------------------------------------------------------
// 🧩 Slice
// -----------------------------------------------------------------------------
const uiSlice = createSlice({
  name: "ui",
  initialState,
  reducers: {
    openCommandPalette(state) {
      state.isPaletteOpen = true;
    },
    closeCommandPalette(state) {
      state.isPaletteOpen = false;
    },
    resetPalette(state) {
      state.paletteQuery = "";
      state.paletteSelection = 0;
    },
    setPaletteQuery(state, action: PayloadAction<string>) {
      state.paletteQuery = action.payload;
      state.paletteSelection = 0;
    },
    setPaletteSelection(state, action: PayloadAction<number>) {
      state.paletteSelection = action.payload;
    },
    addSearchHistory(state, action: PayloadAction<string>) {
      const entry = { query: action.payload, timestamp: Date.now() };
      state.searchHistory.unshift(entry);
      state.searchHistory = state.searchHistory.slice(0, 10);
    },
  },
});

export const {
  openCommandPalette,
  closeCommandPalette,
  resetPalette,
  setPaletteQuery,
  setPaletteSelection,
  addSearchHistory,
} = uiSlice.actions;

export default uiSlice.reducer;
