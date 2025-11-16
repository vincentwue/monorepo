import { startEditSession } from "../editEvents";
import {
  type ShortcutHandler,
  type ShortcutRuntime,
  type TreeKeyboardShortcutAction,
} from "./types";

const selectRelative = (
  runtime: ShortcutRuntime,
  direction: "prev" | "next"
) => {
  const ids = runtime.visibleNodeIds;
  if (!ids.length) return;
  const selected = runtime.state.selectedId;
  const delta = direction === "prev" ? -1 : 1;

  if (!selected) {
    runtime.actions.select(delta === -1 ? ids[ids.length - 1] : ids[0]);
    return;
  }

  const index = ids.indexOf(selected);
  const fallbackIndex = delta === -1 ? ids.length - 1 : 0;
  const currentIndex = index === -1 ? fallbackIndex : index;
  const nextIndex = Math.min(Math.max(0, currentIndex + delta), ids.length - 1);
  runtime.actions.select(ids[nextIndex]);
};

const toggleExpand = (runtime: ShortcutRuntime, id: string) => {
  runtime.actions.toggleExpanded(id);
};

export const shortcutHandlers: Record<
  TreeKeyboardShortcutAction,
  ShortcutHandler
> = {
  "tree.selectRelative": ({ runtime, shortcut }) => {
    const direction = shortcut.args?.direction === "prev" ? "prev" : "next";
    selectRelative(runtime, direction);
    return true;
  },
  "tree.expand": ({ runtime }) => {
    const selectedId = runtime.state.selectedId;
    if (!selectedId) return false;
    const node = runtime.nodeMap.get(selectedId);
    if (!node) return false;
    const hasChildren = !!node.children?.length;
    if (!hasChildren) return false;

    if (!runtime.expandedSet.has(selectedId)) {
      toggleExpand(runtime, selectedId);
      return true;
    }
    return false;
  },
  "tree.collapse": ({ runtime }) => {
    const selectedId = runtime.state.selectedId;
    if (!selectedId) return false;
    if (runtime.expandedSet.has(selectedId)) {
      toggleExpand(runtime, selectedId);
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
      toggleExpand(runtime, selectedId);
      return true;
    }
    if (node.parent_id) {
      runtime.actions.select(node.parent_id);
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
    const inlineState = runtime.state.inlineCreate;
    const selectedId = runtime.state.selectedId;
    if (!selectedId) return false;

    if (inlineState) {
      window.dispatchEvent(
        new CustomEvent("tree-inline-edit-focus", {
          detail: inlineState.tempId,
        })
      );
      return true;
    }

    startEditSession(selectedId);
    window.dispatchEvent(
      new CustomEvent("tree-inline-edit-focus", { detail: selectedId })
    );
    return true;
  },
  "tree.inlineCreate": ({ runtime, shortcut }) => {
    const intent = shortcut.args?.intent as
      | "start"
      | "confirm"
      | "cancel"
      | undefined;
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
        afterId, // ← important
        parentId, // ← important
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
        // ⬅ right now you only pass tempId (+ maybe nodeId),
        //    but NOT afterId / parentId
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
