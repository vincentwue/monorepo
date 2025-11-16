import type { IdeaNodeView, ReorderDirection } from "@ideas/tree-client";
import { TreeKeyboardShortcuts, TreeProvider } from "@monorepo/tree";

import type { ProviderNode } from "../utils/treeNodes";
import { DesktopTreeContent } from "./DesktopTreeContent";

const DESKTOP_TREE_KEY = "ideas-desktop-tree";

export interface DesktopIdeasTreeProps {
  nodes: ProviderNode[];
  componentKey: string;
  loading: boolean;
  error: string | null;
  onReorderNode: (nodeId: string, direction: ReorderDirection) => Promise<void>;
  onMoveNode: (nodeId: string, newParentId: string | null) => Promise<void>;
  initialExpandedIds: string[];
  initialSelectedId: string | null;
  initialStateKey: string;
  onExpandedChange: (ids: string[]) => void;
  onSelectionChange: (selectedId: string | null) => void;
  settingsHydrated: boolean;
  onCreateIdea: (parentId: string | null, title: string) => Promise<IdeaNodeView>;
}

export function DesktopIdeasTree({
  nodes,
  componentKey,
  loading,
  error,
  onReorderNode,
  onMoveNode,
  initialExpandedIds,
  initialSelectedId,
  initialStateKey,
  onExpandedChange,
  onSelectionChange,
  settingsHydrated,
  onCreateIdea,
}: DesktopIdeasTreeProps) {
  return (
    <div className="flex h-full w-full flex-col p-3">
      {loading && <p className="mb-2 text-xs text-slate-400">Loading tree...</p>}
      {error && <p className="mb-2 text-xs text-red-400">{error}</p>}
      <div className="flex-1 min-h-0 overflow-y-auto">
        <TreeProvider
          key={`${DESKTOP_TREE_KEY}-${componentKey}`}
          treeKey={DESKTOP_TREE_KEY}
          nodes={nodes}
        >
          <TreeKeyboardShortcuts treeKey={DESKTOP_TREE_KEY}>
            <DesktopTreeContent
              onReorderNode={onReorderNode}
              onMoveNode={onMoveNode}
              onCreateIdea={onCreateIdea}
              initialExpandedIds={initialExpandedIds}
              initialSelectedId={initialSelectedId}
              initialStateKey={initialStateKey}
              onExpandedIdsChange={onExpandedChange}
              onSelectionChange={onSelectionChange}
              settingsHydrated={settingsHydrated}
            />
          </TreeKeyboardShortcuts>
        </TreeProvider>
      </div>
    </div>
  );
}
