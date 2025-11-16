// src/TreeKeyboardShortcuts.tsx
import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { NodeTreeNode } from "./internal/buildNodeTree";
import { useTreeActions, useTreeState } from "./hooks";
import type { TreeActions, TreeState } from "./types";

type ModifierState = {
  alt: boolean;
  ctrl: boolean;
  meta: boolean;
  shift: boolean;
};

export type TreeShortcutCondition = "inlineCreateActive";

export type TreeKeyboardShortcutAction =
  | "tree.selectRelative"
  | "tree.expand"
  | "tree.collapse"
  | "tree.collapseToParent"
  | "tree.move"
  | "tree.indent"
  | "tree.outdent"
  | "tree.editTitle"
  | "tree.inlineCreate"
  | "tree.delete";

export interface TreeKeyboardShortcut {
  key: string;
  action: TreeKeyboardShortcutAction;
  args?: Record<string, any>;
  when?: TreeShortcutCondition;
}

export const DEFAULT_TREE_SHORTCUTS: TreeKeyboardShortcut[] = [
  {
    key: "ArrowUp",
    action: "tree.selectRelative",
    args: { direction: "prev" },
  },
  {
    key: "ArrowDown",
    action: "tree.selectRelative",
    args: { direction: "next" },
  },
  {
    key: "ArrowRight",
    action: "tree.expand",
  },
  {
    key: "ArrowLeft",
    action: "tree.collapse",
  },
  { key: "Alt+ArrowUp", action: "tree.move", args: { direction: "up" } },
  { key: "Alt+ArrowDown", action: "tree.move", args: { direction: "down" } },
  { key: "Alt+ArrowRight", action: "tree.indent" },
  { key: "Alt+ArrowLeft", action: "tree.outdent" },
  { key: "E", action: "tree.editTitle" },
  // inline create lifecycle
  {
    key: "Ctrl+Enter",
    action: "tree.inlineCreate",
    args: { intent: "start" },
  },
  {
    key: "Enter",
    action: "tree.inlineCreate",
    args: { intent: "confirm" },
    when: "inlineCreateActive",
  },
  {
    key: "Escape",
    action: "tree.inlineCreate",
    args: { intent: "cancel" },
    when: "inlineCreateActive",
  },
  { key: "Delete", action: "tree.delete" },
];

interface TreeKeyboardShortcutsProps {
  treeKey: string;
  children: ReactNode;
  shortcuts?: TreeKeyboardShortcut[];
  shortcutsActive?: boolean;
  /** @deprecated Use shortcutsActive instead. */
  active?: boolean;
}

interface NormalizedShortcut extends TreeKeyboardShortcut {
  modifiers: ModifierState;
  normalizedKey: string;
}

interface ShortcutRuntime {
  state: TreeState;
  actions: TreeActions;
  visibleNodeIds: string[];
  nodeMap: Map<string, NodeTreeNode>;
  expandedSet: Set<string>;
}

type ShortcutHandler = (input: {
  runtime: ShortcutRuntime;
  shortcut: TreeKeyboardShortcut;
}) => boolean;

const parseKeyDescriptor = (descriptor: string): {
  modifiers: ModifierState;
  key: string;
} => {
  const parts = descriptor.split("+").map((part) => part.trim()).filter(Boolean);
  const modifiers: ModifierState = { alt: false, ctrl: false, meta: false, shift: false };
  const keyPart = parts.pop() ?? "";

  for (const mod of parts) {
    const normalized = mod.toLowerCase();
    if (normalized === "ctrl" || normalized === "control") modifiers.ctrl = true;
    else if (normalized === "shift") modifiers.shift = true;
    else if (normalized === "alt" || normalized === "option") modifiers.alt = true;
    else if (normalized === "meta" || normalized === "cmd" || normalized === "command")
      modifiers.meta = true;
  }

  return { modifiers, key: normalizeKey(keyPart) };
};

const normalizeKey = (value: string): string => {
  const normalized = value.toLowerCase();
  if (normalized === " ") return "space";
  if (normalized === "spacebar") return "space";
  return normalized;
};

const normalizeShortcut = (shortcut: TreeKeyboardShortcut): NormalizedShortcut => {
  const { modifiers, key } = parseKeyDescriptor(shortcut.key);
  return {
    ...shortcut,
    modifiers,
    normalizedKey: key,
  };
};

const computeVisibleNodeIds = (flat: NodeTreeNode[]): string[] =>
  flat.map((node) => node._id);

const doesEventMatchShortcut = (
  shortcut: NormalizedShortcut,
  event: KeyboardEvent
): boolean => {
  if (event.altKey !== shortcut.modifiers.alt) return false;
  if (event.ctrlKey !== shortcut.modifiers.ctrl) return false;
  if (event.metaKey !== shortcut.modifiers.meta) return false;
  if (event.shiftKey !== shortcut.modifiers.shift) return false;
  const eventKey = normalizeKey(event.key);
  return eventKey === shortcut.normalizedKey;
};

const conditionMatches = (
  shortcut: TreeKeyboardShortcut,
  runtime: ShortcutRuntime
): boolean => {
  if (!shortcut.when) return true;
  switch (shortcut.when) {
    case "inlineCreateActive":
      return !!runtime.state.inlineCreate;
    default:
      return true;
  }
};

const shortcutHandlers: Record<TreeKeyboardShortcutAction, ShortcutHandler> = {
  "tree.selectRelative": ({ runtime, shortcut }) => {
    const direction = shortcut.args?.direction === "prev" ? -1 : 1;
    const ids = runtime.visibleNodeIds;
    if (!ids.length) return false;
    const selected = runtime.state.selectedId;
    if (!selected) {
      runtime.actions.select(direction === -1 ? ids[ids.length - 1] : ids[0]);
      return true;
    }

    const index = ids.indexOf(selected);
    const fallbackIndex = direction === -1 ? ids.length - 1 : 0;
    const currentIndex = index === -1 ? fallbackIndex : index;
    const nextIndex =
      direction === -1
        ? Math.max(0, currentIndex - 1)
        : Math.min(ids.length - 1, currentIndex + 1);

    if (nextIndex !== currentIndex || index === -1) {
      runtime.actions.select(ids[nextIndex]);
      return true;
    }
    return false;
  },
  "tree.expand": ({ runtime }) => {
    const selectedId = runtime.state.selectedId;
    if (!selectedId) return false;
    const node = runtime.nodeMap.get(selectedId);
    if (!node) return false;
    const hasChildren = !!node.children?.length;
    if (!hasChildren) return false;

    if (!runtime.expandedSet.has(selectedId)) {
      runtime.actions.toggleExpanded(selectedId);
      return true;
    }

    const firstChild = node.children?.[0];
    if (firstChild) {
      runtime.actions.select(firstChild._id);
      return true;
    }
    return false;
  },
  "tree.collapseToParent": ({ runtime }) => {
    const selectedId = runtime.state.selectedId;
    if (!selectedId) return false;
    const node = runtime.nodeMap.get(selectedId);
    if (!node) return false;
    if (runtime.expandedSet.has(selectedId)) {
      runtime.actions.toggleExpanded(selectedId);
      return true;
    }
    if (node.parent_id) {
      runtime.actions.select(node.parent_id);
      return true;
    }
    return false;
  },
  "tree.collapse": ({ runtime }) => {
    const selectedId = runtime.state.selectedId;
    if (!selectedId) return false;
    if (runtime.expandedSet.has(selectedId)) {
      runtime.actions.toggleExpanded(selectedId);
      return true;
    }
    return false;
  },

  "tree.move": ({ runtime, shortcut }) => {
    const selectedId = runtime.state.selectedId;
    if (!selectedId) return false;
    const direction = shortcut.args?.direction === "up" ? "up" : "down";
    if (direction === "up") runtime.actions.moveUp(selectedId);
    else runtime.actions.moveDown(selectedId);
    return true;
  },
  "tree.indent": ({ runtime }) => {
    const selectedId = runtime.state.selectedId;
    if (!selectedId) return false;
    runtime.actions.indent(selectedId);
    return true;
  },
  "tree.outdent": ({ runtime }) => {
    const selectedId = runtime.state.selectedId;
    if (!selectedId) return false;
    runtime.actions.outdent(selectedId);
    return true;
  },
  "tree.editTitle": ({ runtime }) => {
    const selectedId = runtime.state.selectedId;
    if (!selectedId) return false;
    const node = runtime.nodeMap.get(selectedId);
    const nextTitle = window.prompt("Rename node:", node?.title ?? "");
    if (!nextTitle) return false;
    const normalized = nextTitle.trim();
    if (!normalized) return false;
    runtime.actions.rename(selectedId, normalized);
    return true;
  },
  "tree.inlineCreate": ({ runtime, shortcut }) => {
    const intent = shortcut.args?.intent as "start" | "confirm" | "cancel" | undefined;
    if (!intent) return false;

    if (intent === "start") {
      const selectedId = runtime.state.selectedId;
      if (!selectedId || runtime.state.inlineCreate) return false;
      const sourceNode = runtime.nodeMap.get(selectedId);
      const tempId =
        shortcut.args?.tempId || `temp-${Math.random().toString(36).slice(2)}`;
      const afterId = shortcut.args?.afterId ?? selectedId;
      const placeholderTitle = shortcut.args?.title ?? "New node";
      const parentId = shortcut.args?.parentId ?? sourceNode?.parent_id ?? null;

      runtime.actions.beginInlineCreate({
        tempId,
        sourceId: selectedId,
        afterId: shortcut.args?.afterId,
        parentId: shortcut.args?.parentId,
      });
      runtime.actions.addInlineCreatePlaceholder({
        afterId,
        node: { _id: tempId, title: placeholderTitle, parent_id: parentId },
      });
      return true;
    }

    const inlineState = runtime.state.inlineCreate;
    if (!inlineState) return false;

    if (intent === "confirm") {
      runtime.actions.confirmInlineCreate({
        tempId: inlineState.tempId,
        nodeId: shortcut.args?.nodeId,
      });
      return true;
    }
    if (intent === "cancel") {
      runtime.actions.cancelInlineCreate(inlineState.tempId);
      return true;
    }
    return false;
  },
  "tree.delete": ({ runtime }) => {
    const selectedId = runtime.state.selectedId;
    if (!selectedId) return false;
    runtime.actions.delete(selectedId);
    return true;
  },
};

export const TreeKeyboardShortcuts = ({
  treeKey,
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
    providedActive !== undefined ? !!providedActive : false
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
    () => computeVisibleNodeIds(state.flat),
    [state.flat]
  );

  const nodeMap = useMemo(
    () => new Map(state.flat.map((node) => [node._id, node])),
    [state.flat]
  );

  const expandedSet = useMemo(
    () => new Set(state.expandedIds),
    [state.expandedIds]
  );

  const shortcutsRef = useRef<NormalizedShortcut[]>(normalizedShortcuts);
  useEffect(() => {
    shortcutsRef.current = normalizedShortcuts;
  }, [normalizedShortcuts]);

  const runtimeRef = useRef<ShortcutRuntime>({
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
        "tree.inlineCreate",
      ]);

      for (const shortcut of shortcutsList) {
        if (
          isEditableTarget &&
          !allowedWhileEditing.has(shortcut.action)
        )
          continue;
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
