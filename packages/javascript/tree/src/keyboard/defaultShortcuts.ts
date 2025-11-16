import type { TreeKeyboardShortcut } from "./types";

export const DEFAULT_TREE_SHORTCUTS: TreeKeyboardShortcut[] = [
  { key: "ArrowUp", action: "tree.selectRelative", args: { direction: "prev" } },
  { key: "ArrowDown", action: "tree.selectRelative", args: { direction: "next" } },
  { key: "ArrowRight", action: "tree.expand" },
  { key: "ArrowLeft", action: "tree.collapse" },
  { key: "Alt+ArrowUp", action: "tree.move", args: { direction: "up" } },
  { key: "Alt+ArrowDown", action: "tree.move", args: { direction: "down" } },
  { key: "Alt+ArrowRight", action: "tree.indent" },
  { key: "Alt+ArrowLeft", action: "tree.outdent" },
  { key: "E", action: "tree.editTitle" },
  { key: "Ctrl+Enter", action: "tree.inlineCreate", args: { intent: "start" } },
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
