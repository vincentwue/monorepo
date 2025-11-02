// examples/main.tsx
import { TreeProvider, useTreeActions, useTreeState } from "@monorepo/tree";
import { createRoot } from "react-dom/client";

function ExampleApp() {
  return (
    <TreeProvider
      treeKey="demo"
      nodes={[
        { _id: "1", parent_id: null, title: "Root", rank: 100 },
        { _id: "2", parent_id: "1", title: "Child", rank: 200 },
      ]}
    >
      <TreeView />
    </TreeProvider>
  );
}

function TreeView() {
  const { tree, selectedId } = useTreeState();
  const actions = useTreeActions();

  if (!tree.length) return <div>No nodes</div>;

  return (
    <div style={{ fontFamily: "sans-serif", padding: 16 }}>
      {tree.map((node) => (
        <TreeNode key={node._id} node={node} depth={0} actions={actions} selectedId={selectedId} />
      ))}
    </div>
  );
}

function TreeNode({ node, depth, actions, selectedId }) {
  const children = node.children || [];

  const handleSelect = () => actions.select(node._id);

  const handleAdd = () => {
    const tempId = `temp-${Math.random().toString(36).slice(2)}`;
    actions.beginInlineCreate({ tempId, sourceId: node._id });
    actions.addInlineCreatePlaceholder({
      afterId: node._id,
      node: {
        _id: tempId,
        title: "New node",
        parent_id: node._id,
        rank: (node.rank ?? 0) + 100,
      },
    });
  };

  return (
    <div style={{ marginLeft: depth * 20, marginTop: 4 }}>
      <div
        onClick={handleSelect}
        style={{
          cursor: "pointer",
          fontWeight: selectedId === node._id ? "bold" : "normal",
          background: selectedId === node._id ? "#eef" : "transparent",
          padding: "2px 4px",
          borderRadius: 4,
        }}
      >
        {node.title}
      </div>

      <div style={{ marginLeft: 4, marginTop: 2 }}>
        <button onClick={handleAdd}>＋</button>
        <button onClick={() => actions.indent(node._id)}>→</button>
        <button onClick={() => actions.outdent(node._id)}>←</button>
        <button onClick={() => actions.moveUp(node._id)}>↑</button>
        <button onClick={() => actions.moveDown(node._id)}>↓</button>
        <button onClick={() => actions.delete(node._id)}>🗑</button>
      </div>

      {children.length > 0 &&
        children.map((child) => (
          <TreeNode
            key={child._id}
            node={child}
            depth={depth + 1}
            actions={actions}
            selectedId={selectedId}
          />
        ))}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<ExampleApp />);
