// src/tests/buildNodeTree.spec.ts
import { describe, expect, it } from "vitest";
import { buildNodeTree } from "../internal/buildNodeTree";

describe("buildNodeTree", () => {
  it("creates proper roots and children", () => {
    const result = buildNodeTree([
      { _id: "1", parent_id: null, rank: 100 },
      { _id: "2", parent_id: "1", rank: 200 },
    ]);
    expect(result.roots).toHaveLength(1);
    expect(result.roots[0].children).toHaveLength(1);
  });
});
