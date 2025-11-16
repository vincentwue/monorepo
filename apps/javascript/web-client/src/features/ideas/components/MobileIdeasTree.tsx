import type { IdeaNodeView } from "@ideas/tree-client";
import {
  MobileTreeNavigator,
  type MobileTreeNavigatorProps,
  type MobileTreeNode,
} from "@monorepo/mobile-tree-ui";

export interface MobileIdeasTreeProps {
  componentKey: string;
  nodes: MobileTreeNode[];
  loading: boolean;
  error: string | null;
  initialSelectedId: string | null;
  onPathChange?: MobileTreeNavigatorProps["onPathChange"];
  settingsSaving: boolean;
  settingsError: string | null;
  onCreateRoot: () => Promise<void> | void;
  creatingIdea: boolean;
  mutationError: string | null;
  onCreateIdea: (parentId: string | null, title: string) => Promise<IdeaNodeView>;
}

export function MobileIdeasTree({
  componentKey,
  nodes,
  loading,
  error,
  initialSelectedId,
  onPathChange,
  settingsSaving,
  settingsError,
  onCreateRoot,
  creatingIdea,
  mutationError,
  onCreateIdea,
}: MobileIdeasTreeProps) {
  return (
    <div className="flex flex-1 flex-col gap-2 p-3">
      <header className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-200">Ideas (Mobile)</h2>
        <div className="flex items-center gap-2 text-xs">
          {settingsSaving ? (
            <span className="text-slate-400">Saving view...</span>
          ) : settingsError ? (
            <span className="text-red-400">{settingsError}</span>
          ) : null}
          <button
            type="button"
            className="rounded-full border border-slate-600 px-2 py-1 text-xs text-slate-100 disabled:opacity-50"
            onClick={() => {
              void onCreateRoot();
            }}
            disabled={creatingIdea}
          >
            {creatingIdea ? "Creating..." : "New idea"}
          </button>
        </div>
      </header>
      {mutationError && <p className="text-xs text-red-400">{mutationError}</p>}
      {loading && <p className="text-xs text-slate-400">Loading tree...</p>}
      {error && <p className="text-xs text-red-400">{error}</p>}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {loading ? (
          <p className="p-3 text-sm text-slate-400">Preparing mobile tree...</p>
        ) : (
          <MobileTreeNavigator
            key={`mobile-${componentKey}`}
            nodes={nodes}
            className="shadow-none"
            initialNodeId={initialSelectedId ?? null}
            onPathChange={onPathChange}
            onCreateChild={async (parentId, title) => {
              await onCreateIdea(parentId, title);
            }}
            disabled={creatingIdea}
            errorMessage={mutationError}
          />
        )}
      </div>
    </div>
  );
}
