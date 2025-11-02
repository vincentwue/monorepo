import { describe, expect, it } from "vitest";
import { treeReducer, createInitialTreeState } from "../treeReducer";

const nodes = [
  { _id: "1", parent_id: null, title: "Root", rank: 100 },
  { _id: "2", parent_id: "1", title: "Child", rank: 200 },
];

describe("treeReducer", () => {
  it("sets nodes correctly", () => {
    const state = createInitialTreeState([]);
    const next = treeReducer(state, { type: "setNodes", nodes });
    expect(next.nodes).toHaveLength(2);
    expect(next.tree[0].children[0].title).toBe("Child");
  });

  it("selects a node", () => {
    const state = createInitialTreeState(nodes);
    const next = treeReducer(state, { type: "select", id: "2" });
    expect(next.selectedId).toBe("2");
  });

  it("toggles expanded ids", () => {
    const state = createInitialTreeState(nodes);
    const next = treeReducer(state, { type: "toggleExpanded", id: "1" });
    expect(next.expandedIds).toContain("1");
  });
});
