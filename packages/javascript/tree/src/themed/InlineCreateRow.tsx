import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import type { NodeTreeNode } from "../internal/buildNodeTree";
import type { TreeActions, TreeInlineCreateState } from "../types";

interface InlineCreateRowProps {
  node: NodeTreeNode;
  depth: number;
  inlineCreate: TreeInlineCreateState;
  actions: TreeActions;
}

const ROW_INDENT = 30;

export function InlineCreateRow({ node, depth, inlineCreate, actions }: InlineCreateRowProps) {
  const [value, setValue] = useState(node.title ?? "");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  useEffect(() => {
    setValue(node.title ?? "");
  }, [node.title]);

  const tempId = inlineCreate.tempId;

  const handleConfirm = () => {
    const title = value.trim() || "Untitled node";
    if (node._id) {
      actions.rename(node._id, title);
    }
    actions.confirmInlineCreate({ tempId });
  };

  const handleCancel = () => {
    actions.cancelInlineCreate(tempId);
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
        background: "#101426",
        boxShadow: "0 10px 25px rgba(0,0,0,0.45)",
        borderLeft: "4px solid #ff8a65",
      }}
    >
      <input
        ref={inputRef}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="New node title"
        style={{
          width: "100%",
          padding: "6px 8px",
          borderRadius: 8,
          border: "1px solid rgba(255,255,255,0.2)",
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
