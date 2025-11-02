import { RootState } from "@monorepo/store";

export const selectIsPaletteOpen = (state: RootState) => state.ui?.isPaletteOpen;
export const selectPaletteQuery = (state: RootState) => state.ui?.paletteQuery ?? "";
export const selectPaletteSelection = (state: RootState) => state.ui?.paletteSelection ?? 0;
export const selectSearchHistory = (state: RootState) => state.ui?.searchHistory ?? [];
export const selectFocus = (state: RootState) => state.ui?.focus ?? null;
export const selectActiveTreeKey = (state: RootState) => state.ui?.activeTreeKey ?? null;
