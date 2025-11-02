import { createContext } from "react";
import type { TreeActions, TreeState } from "./types";

export const TreeStateContext = createContext<TreeState | undefined>(undefined);
export const TreeActionsContext = createContext<TreeActions | undefined>(undefined);
