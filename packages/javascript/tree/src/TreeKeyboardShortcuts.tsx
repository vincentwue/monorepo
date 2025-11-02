import { useEffect, useRef, useState } from "react";
import { useTreeActions, useTreeState } from "./hooks";

export const TreeKeyboardShortcuts = ({
  treeKey,
  active,
}: {
  treeKey: string;
  active?: boolean;
}) => {
  const { selectedId } = useTreeState();
  const actions = useTreeActions();
  const [enabled, setEnabled] = useState(!!active);
  const containerRef = useRef<HTMLDivElement>(null);

  // allow parent to override focus state
  useEffect(() => {
    if (active !== undefined) setEnabled(active);
  }, [active]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!enabled || !selectedId) return;

      // ignore typing
      const target = e.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable
      ) {
        return;
      }

      if (e.key === "Delete") {
        actions.delete(selectedId);
        e.preventDefault();
      }
      if (e.key === "Enter") {
        const tempId = `temp-${Math.random().toString(36).slice(2)}`;
        actions.beginInlineCreate({ tempId, sourceId: selectedId });
        actions.addInlineCreatePlaceholder({
          afterId: selectedId,
          node: { _id: tempId, title: "New node", parent_id: selectedId },
        });
        e.preventDefault();
      }
      if (e.key === "Tab" && !e.shiftKey) {
        actions.indent(selectedId);
        e.preventDefault();
      }
      if (e.key === "Tab" && e.shiftKey) {
        actions.outdent(selectedId);
        e.preventDefault();
      }
      if (e.key === "ArrowUp") {
        actions.moveUp(selectedId);
        e.preventDefault();
      }
      if (e.key === "ArrowDown") {
        actions.moveDown(selectedId);
        e.preventDefault();
      }
      if (e.ctrlKey && e.key.toLowerCase() === "r") {
        const title = prompt("Rename node:");
        if (title) actions.rename(selectedId, title);
        e.preventDefault();
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [enabled, selectedId, actions]);

  // detect focus/blur on container
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const activate = () => setEnabled(true);
    const deactivate = (e: FocusEvent) => {
      if (!container.contains(e.relatedTarget as Node)) setEnabled(false);
    };

    container.addEventListener("focusin", activate);
    container.addEventListener("focusout", deactivate);
    return () => {
      container.removeEventListener("focusin", activate);
      container.removeEventListener("focusout", deactivate);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      tabIndex={0}
      style={{ outline: enabled ? "1px solid #99f" : "none" }}
    >
      {/* children would be the actual tree content */}
    </div>
  );
};
