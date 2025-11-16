import { useEffect, useMemo, useState } from "react";

export interface MobileTreeNode {
  id: string;
  parentId: string | null;
  title: string;
  rank: number;
}

export interface BreadcrumbItem {
  id: string | null;
  title: string;
}

interface UseMobileTreeNavigatorOptions {
  nodes: MobileTreeNode[];
  initialNodeId?: string | null;
  onPathChange?: (path: BreadcrumbItem[]) => void;
}

const ROOT_CRUMB: BreadcrumbItem = { id: null, title: "All items" };

export const useMobileTreeNavigator = ({
  nodes,
  initialNodeId = null,
  onPathChange,
}: UseMobileTreeNavigatorOptions) => {
  const [currentNodeId, setCurrentNodeId] = useState<string | null>(initialNodeId ?? null);
  const [selectedChildId, setSelectedChildId] = useState<string | null>(null);

  useEffect(() => {
    setCurrentNodeId(initialNodeId ?? null);
  }, [initialNodeId]);

  const nodeMap = useMemo(() => {
    const map = new Map<string, MobileTreeNode>();
    nodes.forEach((node) => map.set(node.id, node));
    return map;
  }, [nodes]);

  useEffect(() => {
    if (currentNodeId && !nodeMap.has(currentNodeId)) {
      setCurrentNodeId(null);
    }
  }, [currentNodeId, nodeMap]);

  const currentNode = currentNodeId ? nodeMap.get(currentNodeId) ?? null : null;

  const path = useMemo(() => {
    const crumbs: BreadcrumbItem[] = [];
    let walkerId = currentNodeId;

    while (walkerId) {
      const node = nodeMap.get(walkerId);
      if (!node) break;
      crumbs.unshift({ id: node.id, title: node.title });
      walkerId = node.parentId;
    }

    return [ROOT_CRUMB, ...crumbs];
  }, [currentNodeId, nodeMap]);

  useEffect(() => {
    onPathChange?.(path);
  }, [path, onPathChange]);

  const children = useMemo(
    () =>
      nodes
        .filter((node) => (node.parentId ?? null) === currentNodeId)
        .sort((a, b) => a.rank - b.rank),
    [nodes, currentNodeId],
  );

  const selectChild = (id: string | null) => {
    setSelectedChildId((prev) => (prev === id ? null : id));
  };

  const goToNode = (id: string | null) => {
    setCurrentNodeId(id);
    setSelectedChildId(null);
  };

  const getChildCount = (id: string) => nodes.filter((node) => node.parentId === id).length;

  return {
    currentNode,
    currentNodeId,
    path,
    children,
    selectedChildId,
    selectChild,
    goToNode,
    getChildCount,
  };
};
