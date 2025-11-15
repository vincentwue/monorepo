import {
  TreeKeyboardShortcuts, TreeProvider,
  useTreeActions,
  useTreeState
} from "@monorepo/tree";
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
      <TreeKeyboardShortcuts treeKey="demo">
        <TreeView />
      </TreeKeyboardShortcuts>
    </TreeProvider>
  );
}

function TreeView() {
  const { tree, selectedId } = useTreeState();
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
        />
      ))}
    </div>
  );
}

function TreeNode({ node, depth, selectedId, actions }) {
  const handleSelect = () => actions.select(node._id);

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
        />
      ))}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<ExampleApp />);
