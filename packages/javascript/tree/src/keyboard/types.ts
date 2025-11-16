import type { NodeTreeNode } from "../internal/buildNodeTree";
import type { TreeActions, TreeState } from "../types";

export type ModifierState = {
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

export interface NormalizedShortcut extends TreeKeyboardShortcut {
  modifiers: ModifierState;
  normalizedKey: string;
}

export interface ShortcutRuntime {
  state: TreeState;
  actions: TreeActions;
  visibleNodeIds: string[];
  nodeMap: Map<string, NodeTreeNode>;
  expandedSet: Set<string>;
}

export type ShortcutHandler = (input: {
  runtime: ShortcutRuntime;
  shortcut: TreeKeyboardShortcut;
}) => boolean;
