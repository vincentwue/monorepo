import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import type { NodeTreeNode } from "../internal/buildNodeTree";
import type { TreeActions } from "../types";

interface InlineEditRowProps {
  node: NodeTreeNode;
  depth: number;
  actions: TreeActions;
  onComplete: () => void;
}

const ROW_INDENT = 30;

export function InlineEditRow({ node, depth, actions, onComplete }: InlineEditRowProps) {
  const [value, setValue] = useState(node.title ?? "");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  useEffect(() => {
    setValue(node.title ?? "");
  }, [node.title]);

  const handleConfirm = () => {
    if (node._id) {
      const title = value.trim() || "Untitled node";
      actions.rename(node._id, title);
    }
    onComplete();
  };

  const handleCancel = () => {
    onComplete();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      handleConfirm();
    }
    if (event.key === "Escape") {
      event.preventDefault();
      handleCancel();
    }
  };

  return (
    <div
      style={{
        marginLeft: depth * ROW_INDENT,
        marginTop: 10,
        borderRadius: 10,
        padding: "8px 16px",
        background: "rgba(17, 21, 43, 0.65)",
        boxShadow: "0 10px 25px rgba(0,0,0,0.45)",
        borderLeft: "4px solid #60a5fa",
      }}
    >
      <input
        ref={inputRef}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Rename node"
        style={{
          width: "100%",
          padding: "6px 8px",
          borderRadius: 8,
          border: "1px solid rgba(90,150,255,0.4)",
          background: "rgba(255,255,255,0.04)",
          color: "#fff",
          fontFamily: '"Source Sans 3", "Inter", system-ui, sans-serif',
        }}
      />
      <div style={{ fontSize: 12, color: "#cbd5f5", marginTop: 6 }}>
        Enter to confirm · Esc to cancel
      </div>
    </div>
  );
}
