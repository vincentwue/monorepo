import { useContext } from "react";
import type { TreeActions, TreeState } from "./types";
import { TreeActionsContext, TreeStateContext } from "./context";

export const useTreeState = (): TreeState => {
  const context = useContext(TreeStateContext);
  if (!context) {
    throw new Error("useTreeState must be used within a TreeProvider");
  }
  return context;
};

export const useTreeActions = (): TreeActions => {
  const context = useContext(TreeActionsContext);
  if (!context) {
    throw new Error("useTreeActions must be used within a TreeProvider");
  }
  return context;
};
