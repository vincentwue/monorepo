import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { subscribeEditSession } from "../editEvents";
import { useTreeActions, useTreeState } from "../hooks";
import type { TreeActions, TreeInlineCreateState } from "../types";
import { ThemedTreeNode } from "./TreeNode";

const CONTAINER_STYLE: CSSProperties = {
  minHeight: "100vh",
  background: "#050b1b",
  padding: "32px",
};

interface ThemedTreeViewProps {
  className?: string;
  style?: CSSProperties;
}

export function ThemedTreeView({ className, style }: ThemedTreeViewProps) {
  const { tree, selectedId, inlineCreate, expandedIds } = useTreeState();
  const actions = useTreeActions();
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    const unsubscribe = subscribeEditSession((id) => setEditingId(id));
    return unsubscribe;
  }, []);

  const expandedSet = useMemo(() => new Set(expandedIds), [expandedIds]);

  return (
    <div className={className} style={{ ...CONTAINER_STYLE, ...style }}>
      {tree.map((node) => (
        <ThemedTreeNode
          key={node._id}
          node={node}
          depth={0}
          selectedId={selectedId}
          inlineCreate={inlineCreate}
          actions={actions}
          editingId={editingId}
          expandedSet={expandedSet}
          onEditingComplete={() => setEditingId(null)}
        />
      ))}
    </div>
  );
}
