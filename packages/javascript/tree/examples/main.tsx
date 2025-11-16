import {
  TreeKeyboardShortcuts,
  TreeProvider,
  useTreeActions,
  useTreeState,
} from "../src";
import { createRoot } from "react-dom/client";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

function ExampleApp() {
  return (
    <TreeProvider
      treeKey="demo"
      nodes={[
        { _id: "1", parent_id: null, title: "Root", rank: 100 },
        { _id: "2", parent_id: "1", title: "Child", rank: 200 },
      ]}
    >
      <TreeKeyboardShortcuts treeKey="demo">
        <TreeView />
      </TreeKeyboardShortcuts>
    </TreeProvider>
  );
}

type ExampleTreeState = ReturnType<typeof useTreeState>;
type ExampleTreeActions = ReturnType<typeof useTreeActions>;
type TreeViewNode = ExampleTreeState["tree"][number];

function TreeView() {
  const { tree, selectedId, inlineCreate } = useTreeState();
  const actions = useTreeActions();

  return (
    <div style={{ fontFamily: "sans-serif", padding: 8 }}>
      {tree.map((node) => (
        <TreeNode
          key={node._id}
          node={node}
          depth={0}
          selectedId={selectedId}
          actions={actions}
          inlineCreate={inlineCreate}
        />
      ))}
    </div>
  );
}

interface TreeNodeProps {
  node: TreeViewNode;
  depth: number;
  selectedId: string | null;
  actions: ExampleTreeActions;
  inlineCreate: ExampleTreeState["inlineCreate"];
}

function TreeNode({
  node,
  depth,
  selectedId,
  actions,
  inlineCreate,
}: TreeNodeProps) {
  const handleSelect = () => actions.select(node._id);
  const inlineActive =
    inlineCreate?.tempId === node._id && node.isPlaceholder;
  if (inlineActive && inlineCreate) {
    return (
      <InlineCreateRow
        node={node}
        depth={depth}
        inlineCreate={inlineCreate}
        actions={actions}
      />
    );
  }

  return (
    <div style={{ marginLeft: depth * 20, marginTop: 4 }}>
      <div
        onClick={handleSelect}
        style={{
          cursor: "pointer",
          fontWeight: selectedId === node._id ? "bold" : "normal",
          background: selectedId === node._id ? "#eef" : "transparent",
          borderRadius: 4,
          padding: "2px 4px",
        }}
      >
        {node.title}
      </div>
      <div style={{ marginLeft: 4 }}>
        <button onClick={() => actions.indent(node._id)}>→</button>
        <button onClick={() => actions.outdent(node._id)}>←</button>
        <button onClick={() => actions.moveUp(node._id)}>↑</button>
        <button onClick={() => actions.moveDown(node._id)}>↓</button>
        <button onClick={() => actions.delete(node._id)}>🗑</button>
      </div>
      {node.children?.map((child) => (
        <TreeNode
          key={child._id}
          node={child}
          depth={depth + 1}
          selectedId={selectedId}
          actions={actions}
          inlineCreate={inlineCreate}
        />
      ))}
    </div>
  );
}

interface InlineCreateRowProps {
  node: TreeViewNode;
  depth: number;
  inlineCreate: ExampleTreeState["inlineCreate"];
  actions: ExampleTreeActions;
}

function InlineCreateRow({
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

  if (!inlineCreate?.tempId) return null;

  const tempId = inlineCreate.tempId;

  const handleConfirm = () => {
    const title = value.trim() || "Untitled node";
    actions.rename(node._id, title);
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
        marginLeft: depth * 20,
        marginTop: 4,
        borderRadius: 4,
        padding: "2px 4px",
        background: "#111",
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
          padding: "4px 6px",
          fontSize: 14,
          borderRadius: 4,
          border: "1px solid #ccc",
        }}
      />
      <div style={{ fontSize: 12, color: "#999", marginTop: 2 }}>
        Enter to confirm · Esc to cancel
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<ExampleApp />);
