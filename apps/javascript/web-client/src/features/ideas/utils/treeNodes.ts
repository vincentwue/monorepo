import type { IdeaNodeView, IdeaTreeUiState } from "@ideas/tree-client";
import type { MobileTreeNode } from "@monorepo/mobile-tree-ui";

export interface ProviderNode {
  _id: string;
  parent_id: string | null;
  title: string;
  rank?: number;
}

export const mapToProviderNodes = (list: IdeaNodeView[]): ProviderNode[] =>
  list.map((node) => ({
    _id: node.id,
    parent_id: node.parentId ?? null,
    title: node.title,
    rank: node.rank,
  }));

export const mapToMobileNodes = (list: IdeaNodeView[]): MobileTreeNode[] =>
  list.map((node) => ({
    id: node.id,
    parentId: node.parentId ?? null,
    title: node.title,
    rank: node.rank ?? 0,
  }));

export const buildNodesVersion = (list: IdeaNodeView[]): string =>
  list.length === 0
    ? "empty"
    : list
        .map(
          (node) =>
            `${node.id}:${node.parentId ?? "root"}:${node.rank ?? 0}:${node.title ?? ""}`,
        )
        .join("|");

export const buildSettingsKey = (state: IdeaTreeUiState): string =>
  `${state.selectedId ?? "root"}|${state.expandedIds.join(",")}`;

export const arraysEqual = (a: readonly string[], b: readonly string[]): boolean =>
  a.length === b.length && a.every((value, index) => value === b[index]);

export const normalizeExpandedIds = (ids: string[]): string[] => {
  const seen = new Set<string>();
  const normalized: string[] = [];
  for (const raw of ids) {
    if (typeof raw !== "string") continue;
    const value = raw.trim();
    if (!value || seen.has(value)) continue;
    seen.add(value);
    normalized.push(value);
  }
  return normalized;
};
