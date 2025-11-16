import type { NodeTreeNode } from "../internal/buildNodeTree";
import type { TreeActions, TreeInlineCreateState } from "../types";
import { InlineCreateRow } from "./InlineCreateRow";
import { InlineEditRow } from "./InlineEditRow";
import { getDepthBackground, getDepthGuideColor, getIndentStyle } from "./nodeStyle";
import { TreeNodeSurface } from "./TreeNodeSurface";

interface ThemedTreeNodeProps {
  node: NodeTreeNode;
  depth: number;
  selectedId: string | null;
  inlineCreate: TreeInlineCreateState | null;
  actions: TreeActions;
  editingId: string | null;
  expandedSet: Set<string>;
  onEditingComplete: () => void;
}

export function ThemedTreeNode({
  node,
  depth,
  selectedId,
  inlineCreate,
  actions,
  editingId,
  expandedSet,
  onEditingComplete,
}: ThemedTreeNodeProps) {
  const inlineActive = inlineCreate?.tempId === node._id && node.isPlaceholder;

  if (editingId === node._id) {
    return (
      <InlineEditRow
        node={node}
        depth={depth}
        actions={actions}
        onComplete={() => {
          onEditingComplete();
        }}
      />
    );
  }

  if (inlineActive && inlineCreate) {
    return <InlineCreateRow node={node} depth={depth} inlineCreate={inlineCreate} actions={actions} />;
  }

  const isSelected = selectedId === node._id;
  const isExpanded = node._id ? expandedSet.has(node._id) : false;
  const color = getDepthBackground(depth, isSelected);
  const borderColor = getDepthGuideColor(depth);
  const indentStyle = getIndentStyle(depth);

  return (
    <div style={{ marginTop: 12, ...indentStyle }}>
      <TreeNodeSurface
        node={node}
        actions={actions}
        color={color}
        borderColor={borderColor}
        isSelected={isSelected}
        isExpanded={isExpanded}
        indentStyle={indentStyle}
      />
      {isExpanded &&
        (node.children ?? []).map((child) => (
          <ThemedTreeNode
            key={child._id}
            node={child}
            depth={depth + 1}
            selectedId={selectedId}
            inlineCreate={inlineCreate}
            actions={actions}
            editingId={editingId}
            expandedSet={expandedSet}
            onEditingComplete={onEditingComplete}
          />
        ))}
    </div>
  );
}
