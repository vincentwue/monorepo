import {
  ThemedTreeView,
  TreeKeyboardShortcuts,
  TreeProvider,
} from "../src";
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
        <ThemedTreeView />
      </TreeKeyboardShortcuts>
    </TreeProvider>
  );
}

createRoot(document.getElementById("root")!).render(<ExampleApp />);
