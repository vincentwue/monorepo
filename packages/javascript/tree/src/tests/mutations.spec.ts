import { describe, expect, it } from "vitest";
import {
  indentNode,
  outdentNode,
  moveNode,
  beginInlineCreate,
  addInlineCreatePlaceholder,
  confirmInlineCreate,
} from "../mutations";
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

  it("supports inline create repeatedly and keeps placeholder selected", () => {
    const initial = createInitialTreeState(nodes);
    const firstSession = beginInlineCreate(initial, {
      tempId: "temp-one",
      sourceId: "1",
    });
    expect(firstSession?.inlineCreate?.tempId).toBe("temp-one");
    const firstPlaceholder = addInlineCreatePlaceholder(firstSession!, {
      afterId: "1",
      node: { _id: "temp-one", title: "New node", parent_id: null },
    });
    expect(firstPlaceholder.selectedId).toBe("temp-one");
    expect(firstPlaceholder.inlineCreate?.tempId).toBe("temp-one");
    const confirmed = confirmInlineCreate(firstPlaceholder, {
      tempId: "temp-one",
      nodeId: "1.1",
    });
    expect(confirmed?.inlineCreate).toBeNull();
    expect(confirmed?.selectedId).toBe("1.1");

    const secondSession = beginInlineCreate(confirmed!, {
      tempId: "temp-two",
      sourceId: "2",
    });
    const secondPlaceholder = addInlineCreatePlaceholder(secondSession!, {
      afterId: "2",
      node: { _id: "temp-two", title: "Another node", parent_id: null },
    });
    expect(secondPlaceholder.selectedId).toBe("temp-two");
    expect(secondPlaceholder.inlineCreate?.tempId).toBe("temp-two");
  });
});
