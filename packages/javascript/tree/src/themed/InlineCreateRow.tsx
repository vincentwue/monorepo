import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import type { NodeTreeNode } from "../internal/buildNodeTree";
import type { TreeActions, TreeInlineCreateState } from "../types";
import { getIndentStyle } from "./nodeStyle";

interface InlineCreateRowProps {
  node: NodeTreeNode;
  depth: number;
  inlineCreate: TreeInlineCreateState;
  actions: TreeActions;
}

export function InlineCreateRow({
  node,
  depth,
  inlineCreate,
  actions,
}: InlineCreateRowProps) {
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

  const indentStyle = getIndentStyle(depth);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        marginTop: 12,
        ...indentStyle,
      }}
    >
      {/* placeholder for +/- button so layout matches TreeNodeSurface */}
      <div style={{ width: 20 }} />

      {/* inline-create "node surface" */}
      <div
        style={{
          flexGrow: 1,
          background: "#101426",
          borderRadius: 10,
          padding: "8px 16px",
          boxShadow: "0 6px 16px rgba(0,0,0,0.35)",
          border: "2px solid rgba(120,200,255,0.9)",
          color: "#f6f3ff",
          fontFamily: '"Source Sans 3", "Inter", system-ui, sans-serif',
          fontSize: 16,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
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
            border: "1px solid rgba(255,255,255,0.25)",
            background: "rgba(255,255,255,0.04)",
            color: "#fff",
            fontFamily: '"Source Sans 3", "Inter", system-ui, sans-serif',
            fontSize: 16,
            outline: "none",
          }}
        />
        <div
          style={{
            fontSize: 12,
            color: "#cbd5f5",
            marginTop: 6,
          }}
        >
          Enter to confirm · Esc to cancel
        </div>
      </div>
    </div>
  );
}
