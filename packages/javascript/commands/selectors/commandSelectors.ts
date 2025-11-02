import type { RootState } from "@monorepo/store";
import { createSelector } from "@reduxjs/toolkit";
import { listCommands } from "../src/commands";

/**
 * Lightweight fuzzy search:
 * Matches if query is a substring of id or title (case-insensitive).
 */
function matchesQuery(cmd: { id: string; title: string }, query: string) {
  if (!query) return true;
  const q = query.toLowerCase();
  return (
    cmd.id.toLowerCase().includes(q) || cmd.title.toLowerCase().includes(q)
  );
}

/**
 * Base selector for palette state
 */
const selectPaletteQuery = (state: RootState) => state.ui?.paletteQuery ?? "";

/**
 * Returns filtered commands and total count.
 */
export const selectFilteredCommands = createSelector(
  [selectPaletteQuery],
  (query) => {
    const all = listCommands();
    const filtered = all.filter((cmd) => matchesQuery(cmd, query));
    const sorted = filtered.sort((a, b) =>
      a.title.localeCompare(b.title, undefined, { sensitivity: "base" })
    );
    return { commands: sorted, total: all.length };
  }
);
