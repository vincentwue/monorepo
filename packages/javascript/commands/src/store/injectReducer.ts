import type { Reducer } from "@reduxjs/toolkit";
import { store } from "@monorepo/store";

const injectedReducers: Record<string, boolean> = {};

export function injectReducer(key: string, reducer: Reducer) {
  // @ts-ignore
  const reducerManager = store.reducerManager;
  if (!reducerManager) {
    console.warn("[command-orchestra] store.reducerManager missing");
    return;
  }

  if (injectedReducers[key]) return;
  reducerManager.add(key, reducer);
  injectedReducers[key] = true;
}
