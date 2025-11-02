export { store, type AppDispatch, type RootState } from "@monorepo/store";

import type { AppDispatch, RootState } from "@monorepo/store";
import { TypedUseSelectorHook, useDispatch, useSelector } from "react-redux";

// typed hooks
export const useAppDispatch: () => AppDispatch = useDispatch;
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
