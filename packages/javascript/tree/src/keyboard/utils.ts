import type { NodeTreeNode } from "../internal/buildNodeTree";
import type { TreeState } from "../types";
import type {
  ModifierState,
  NormalizedShortcut,
  ShortcutRuntime,
  TreeKeyboardShortcut,
  TreeShortcutCondition,
} from "./types";

export const parseKeyDescriptor = (
  descriptor: string,
): { modifiers: ModifierState; key: string } => {
  const parts = descriptor
    .split("+")
    .map((part) => part.trim())
    .filter(Boolean);
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

export const normalizeKey = (value: string): string => {
  const normalized = value.toLowerCase();
  if (normalized === " ") return "space";
  if (normalized === "spacebar") return "space";
  return normalized;
};

export const normalizeShortcut = (shortcut: TreeKeyboardShortcut): NormalizedShortcut => {
  const { modifiers, key } = parseKeyDescriptor(shortcut.key);
  return {
    ...shortcut,
    modifiers,
    normalizedKey: key,
  };
};

export const computeVisibleNodeIds = (
  flat: NodeTreeNode[],
  expandedIds: string[],
): string[] => {
  if (!flat.length) return [];
  const expandedSet = new Set(expandedIds);
  const map = new Map(flat.map((node) => [node._id, node]));

  const isVisible = (node: NodeTreeNode): boolean => {
    let parentId = node.parent_id;
    while (parentId) {
      if (!expandedSet.has(parentId)) return false;
      const parent = map.get(parentId);
      parentId = parent?.parent_id ?? null;
    }
    return true;
  };

  return flat.filter(isVisible).map((node) => node._id);
};

export const doesEventMatchShortcut = (
  shortcut: NormalizedShortcut,
  event: KeyboardEvent,
): boolean => {
  if (event.altKey !== shortcut.modifiers.alt) return false;
  if (event.ctrlKey !== shortcut.modifiers.ctrl) return false;
  if (event.metaKey !== shortcut.modifiers.meta) return false;
  if (event.shiftKey !== shortcut.modifiers.shift) return false;
  const eventKey = normalizeKey(event.key);
  return eventKey === shortcut.normalizedKey;
};

export const conditionMatches = (
  shortcut: TreeKeyboardShortcut,
  runtime: ShortcutRuntime,
): boolean => {
  if (!shortcut.when) return true;
  switch (shortcut.when) {
    case "inlineCreateActive":
      return !!runtime.state.inlineCreate;
    default:
      return true;
  }
};
