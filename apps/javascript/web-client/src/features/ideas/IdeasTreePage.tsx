import { useMemo } from "react";
import {
  IdeasApiClient,
  useIdeasTree,
  type IdeaNodeView,
  type ReorderDirection,
} from "@ideas/tree-client";

import { useMediaQuery } from "../../hooks/useMediaQuery";

interface TreeShellProps {
  nodes: IdeaNodeView[];
  parentId: string | null;
  loading: boolean;
  error: string | null;
  onOpenNode: (id: string) => void;
  onCreateChild: (parentId: string | null, title: string) => Promise<void>;
  onMoveNode: (nodeId: string, newParentId: string | null) => Promise<void>;
  onReorderNode: (nodeId: string, direction: ReorderDirection) => Promise<void>;
}

function DesktopTreeShell(props: TreeShellProps) {
  const { nodes, loading, error, onOpenNode, onReorderNode } = props;

  return (
    <div className="flex flex-1 flex-col gap-2 p-3">
      <header className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-200">Ideas (Desktop)</h2>
      </header>
      {loading && <p className="text-xs text-slate-400">Loading…</p>}
      {error && <p className="text-xs text-red-400">{error}</p>}
      <ul className="space-y-1 text-sm">
        {nodes.map((node) => (
          <li
            key={node.id}
            className="flex items-center justify-between rounded-md border border-slate-800/70 bg-slate-900/80 px-2 py-1"
          >
            <button
              className="text-left text-slate-100"
              onClick={() => onOpenNode(node.id)}
            >
              {node.title}
            </button>
            <div className="flex items-center gap-1 text-xs">
              <button
                className="rounded border border-slate-700 px-1"
                onClick={() => onReorderNode(node.id, "up")}
              >
                ?
              </button>
              <button
                className="rounded border border-slate-700 px-1"
                onClick={() => onReorderNode(node.id, "down")}
              >
                ?
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MobileTreeShell(props: TreeShellProps) {
  const { nodes, loading, error, onOpenNode } = props;

  return (
    <div className="flex flex-1 flex-col gap-2 p-3">
      <header className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-200">Ideas (Mobile)</h2>
      </header>
      {loading && <p className="text-xs text-slate-400">Loading…</p>}
      {error && <p className="text-xs text-red-400">{error}</p>}
      <ul className="divide-y divide-slate-800 text-sm">
        {nodes.map((node) => (
          <li key={node.id}>
            <button
              className="flex w-full items-center justify-between px-2 py-2 text-left"
              onClick={() => onOpenNode(node.id)}
            >
              <span>{node.title}</span>
              <span className="text-xs text-slate-500">›</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function IdeasTreePage() {
  const isMobile = useMediaQuery("(max-width: 768px)");

  const apiBaseUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
  const client = useMemo(
    () => new IdeasApiClient({ baseUrl: apiBaseUrl }),
    [apiBaseUrl]
  );

  const parentId: string | null = null;

  const { nodes, loading, error, createChild, moveNode, reorderNode } =
    useIdeasTree(parentId, client);

  const onOpenNode = (id: string) => {
    console.log("[IdeasTreePage] open node", id);
  };

  const shellProps: TreeShellProps = {
    nodes,
    parentId,
    loading,
    error: error ? (typeof error === "string" ? error : String(error)) : null,
    onOpenNode,
    onCreateChild: createChild,
    onMoveNode: moveNode,
    onReorderNode: reorderNode,
  };

  return isMobile ? (
    <MobileTreeShell {...shellProps} />
  ) : (
    <DesktopTreeShell {...shellProps} />
  );
}

export default IdeasTreePage;
