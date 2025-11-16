// src/TreeKeyboardShortcuts.tsx
import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTreeActions, useTreeState } from "./hooks";
import { DEFAULT_TREE_SHORTCUTS } from "./keyboard/defaultShortcuts";
import { shortcutHandlers } from "./keyboard/handlers";
import {
  type NormalizedShortcut,
  type TreeKeyboardShortcut,
  type TreeKeyboardShortcutAction
} from "./keyboard/types";
import {
  computeVisibleNodeIds,
  conditionMatches,
  doesEventMatchShortcut,
  normalizeShortcut,
} from "./keyboard/utils";

interface TreeKeyboardShortcutsProps {
  treeKey: string;
  children: ReactNode;
  shortcuts?: TreeKeyboardShortcut[];
  shortcutsActive?: boolean;
  /** @deprecated Use shortcutsActive instead. */
  active?: boolean;
}

export const TreeKeyboardShortcuts = ({
  children,
  shortcuts,
  shortcutsActive,
  active,
}: TreeKeyboardShortcutsProps) => {
  const state = useTreeState();
  const actions = useTreeActions();
  const containerRef = useRef<HTMLDivElement>(null);
  const providedActive = shortcutsActive ?? active;
  const isControlled = providedActive !== undefined;
  const [internalActive, setInternalActive] = useState(() =>
    providedActive !== undefined ? !!providedActive : false,
  );
  const [hasFocus, setHasFocus] = useState(false);
  const enabled = isControlled ? !!providedActive : internalActive;

  useEffect(() => {
    if (isControlled) {
      setInternalActive(!!providedActive);
    }
  }, [isControlled, providedActive]);

  useEffect(() => {
    if (isControlled) return;
    if (state.selectedId) {
      setInternalActive(true);
    }
  }, [isControlled, state.selectedId]);

  useEffect(() => {
    if (isControlled) return;
    if (state.inlineCreate === null && state.selectedId) {
      setInternalActive(true);
    }
  }, [isControlled, state.inlineCreate, state.selectedId]);

  const normalizedShortcuts = useMemo(() => {
    const list = shortcuts ?? DEFAULT_TREE_SHORTCUTS;
    return list.map((shortcut) => normalizeShortcut(shortcut));
  }, [shortcuts]);

  const visibleNodeIds = useMemo(
    () => computeVisibleNodeIds(state.flat, state.expandedIds),
    [state.flat, state.expandedIds],
  );

  const nodeMap = useMemo(
    () => new Map(state.flat.map((node) => [node._id, node])),
    [state.flat],
  );

  const expandedSet = useMemo(() => new Set(state.expandedIds), [state.expandedIds]);

  const shortcutsRef = useRef<NormalizedShortcut[]>(normalizedShortcuts);
  useEffect(() => {
    shortcutsRef.current = normalizedShortcuts;
  }, [normalizedShortcuts]);

  const runtimeRef = useRef({
    state,
    actions,
    visibleNodeIds,
    nodeMap,
    expandedSet,
  });

  runtimeRef.current = {
    state,
    actions,
    visibleNodeIds,
    nodeMap,
    expandedSet,
  };

  useEffect(() => {
    if (!enabled) return;
    const handler = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const isEditableTarget =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);

      const shortcutsList = shortcutsRef.current;
      const runtime = runtimeRef.current;
      if (!runtime) return;

      const allowedWhileEditing = new Set<TreeKeyboardShortcutAction>([
        // Only inline-create lifecycle should work inside inputs
        "tree.inlineCreate",
      ]);

      for (const shortcut of shortcutsList) {
        if (isEditableTarget && !allowedWhileEditing.has(shortcut.action)) continue;
        if (isEditableTarget && shortcut.action === "tree.inlineCreate") {
          const intent = shortcut.args?.intent;
          if (intent === "start") continue;
        }
        if (!doesEventMatchShortcut(shortcut, event)) continue;
        if (!conditionMatches(shortcut, runtime)) continue;

        const handlerFn = shortcutHandlers[shortcut.action];
        if (!handlerFn) continue;
        const handled = handlerFn({ runtime, shortcut });
        if (handled) {
          event.preventDefault();
          break;
        }
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [enabled]);

  useEffect(() => {
    if (isControlled) return;
    const container = containerRef.current;
    if (!container) return;

    const activate = () => {
      setInternalActive(true);
      setHasFocus(true);
    };
    const deactivate = (e: FocusEvent) => {
      if (!container.contains(e.relatedTarget as Node)) {
        setInternalActive(false);
        setHasFocus(false);
      }
    };

    container.addEventListener("focusin", activate);
    container.addEventListener("focusout", deactivate);
    return () => {
      container.removeEventListener("focusin", activate);
      container.removeEventListener("focusout", deactivate);
    };
  }, [isControlled]);

  return (
    <div
      ref={containerRef}
      tabIndex={0}
      style={{
        outline: !isControlled && hasFocus ? "2px solid #88f" : "none",
        borderRadius: 4,
        padding: 4,
      }}
    >
      {children}
    </div>
  );
};

export { DEFAULT_TREE_SHORTCUTS } from "./keyboard/defaultShortcuts";
export type {
  TreeKeyboardShortcut,
  TreeKeyboardShortcutAction,
  TreeShortcutCondition
} from "./keyboard/types";

