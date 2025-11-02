import { describe, expect, it } from "vitest";
import { indentNode, outdentNode, moveNode } from "../mutations";
import { createInitialTreeState } from "../treeReducer";

const nodes = [
  { _id: "1", parent_id: null, title: "Root", rank: 100 },
  { _id: "2", parent_id: null, title: "A", rank: 200 },
  { _id: "3", parent_id: null, title: "B", rank: 300 },
];

describe("mutations", () => {
  it("indents a node under its previous sibling", () => {
    const state = createInitialTreeState(nodes);
    const next = indentNode(state, "2");
    expect(next?.nodes.find(n => n._id === "2")?.parent_id).toBe("1");
  });

  it("outdents a node back to root", () => {
    const state = createInitialTreeState([
      { _id: "1", parent_id: null, title: "Root", rank: 100 },
      { _id: "2", parent_id: "1", title: "Child", rank: 200 },
    ]);
    const next = outdentNode(state, "2");
    expect(next?.nodes.find(n => n._id === "2")?.parent_id).toBe(null);
  });

  it("moves a node down among siblings", () => {
    const state = createInitialTreeState(nodes);
    const next = moveNode(state, "1", 1);
    const ranks = next?.nodes.map(n => n.rank);
    expect(ranks).not.toEqual([100, 200, 300]); // rank order changed
  });
});
