import { configureStore, combineReducers } from "@reduxjs/toolkit";
import { mongoApi } from "@monorepo/mongo-explorer";

// -----------------------------------------------------------------------------
// 🧩 Static Reducers (always loaded)
// -----------------------------------------------------------------------------
const staticReducers = {
  mongoApi: mongoApi.reducer,
};

// -----------------------------------------------------------------------------
// 🧠 Reducer Manager (for dynamic injection)
// -----------------------------------------------------------------------------
function createReducerManager(initialReducers: typeof staticReducers) {
  const reducers = { ...initialReducers };
  let combined = combineReducers(reducers);

  return {
    getReducerMap: () => reducers,
    reduce: (state: any, action: any) => combined(state, action),
    add: (key: string, reducer: any) => {
      if (!key || reducers[key]) return;
      reducers[key] = reducer;
      combined = combineReducers(reducers);
    },
    remove: (key: string) => {
      if (!key || !reducers[key]) return;
      delete reducers[key];
      combined = combineReducers(reducers);
    },
  };
}

// -----------------------------------------------------------------------------
// 🏗️ Create Reducer Manager + Store
// -----------------------------------------------------------------------------
const reducerManager = createReducerManager(staticReducers);

export const store = configureStore({
  reducer: reducerManager.reduce,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(mongoApi.middleware),
  devTools: import.meta.env?.DEV ?? true,
});

// attach reducerManager to the store for runtime injection
// @ts-ignore
store.reducerManager = reducerManager;

// -----------------------------------------------------------------------------
// 🧩 Types
// -----------------------------------------------------------------------------
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
