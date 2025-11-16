import { useCallback, useState } from "react";
import {
  useMobileTreeNavigator,
  type BreadcrumbItem,
  type MobileTreeNode,
} from "../hooks/useMobileTreeNavigator";
import "../styles.css";
import { BreadcrumbBar } from "./BreadcrumbBar";
import { NodeList } from "./NodeList";

/**
 * Example usage:
 *
 * ```tsx
 * import { MobileTreeNavigator } from "@monorepo/mobile-tree-ui";
 *
 * export function IdeasScreen() {
 *   return <MobileTreeNavigator nodes={myNodes} onCreateChild={handleCreate} />;
 * }
 * ```
 */
export interface MobileTreeNavigatorProps {
  nodes: MobileTreeNode[];
  initialNodeId?: string | null;
  className?: string;
  onPathChange?: (path: BreadcrumbItem[]) => void;
  onCreateChild?: (parentId: string | null, title: string) => Promise<void> | void;
  onRenameNode?: (id: string, title: string) => Promise<void> | void;
  onDeleteNode?: (id: string) => Promise<void> | void;
  onReorderChildren?: (parentId: string | null, orderedIds: string[]) => Promise<void> | void;
  disabled?: boolean;
  errorMessage?: string | null;
}

export const MobileTreeNavigator = ({
  nodes,
  initialNodeId = null,
  className,
  onPathChange,
  onCreateChild,
  onRenameNode,
  onDeleteNode,
  onReorderChildren,
  disabled,
  errorMessage,
}: MobileTreeNavigatorProps) => {
  const {
    currentNode,
    currentNodeId,
    path,
    children,
    selectedChildId,
    selectChild,
    goToNode,
    getChildCount,
  } = useMobileTreeNavigator({ nodes, initialNodeId, onPathChange });

  const [renameTargetId, setRenameTargetId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState<string>("");
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createValue, setCreateValue] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const combinedClass = ["mtu-container", className].filter(Boolean).join(" ");
  const canCreate = typeof onCreateChild === "function" && !disabled;
  const canRename = typeof onRenameNode === "function" && !disabled;
  const canDelete = typeof onDeleteNode === "function" && !disabled;
  const canReorder = typeof onReorderChildren === "function" && !disabled;

  const handleCreate = useCallback(async () => {
    if (!onCreateChild) return;
    const title = createValue.trim() || "Untitled";
    setPending(true);
    setActionError(null);
    try {
      await onCreateChild(currentNodeId ?? null, title);
      setCreateValue("");
      setCreateModalOpen(false);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to create item");
    } finally {
      setPending(false);
    }
  }, [onCreateChild, createValue, currentNodeId]);

  const handleRename = useCallback(async () => {
    if (!onRenameNode || !renameTargetId) return;
    const title = renameValue.trim() || "Untitled";
    setPending(true);
    setActionError(null);
    try {
      await onRenameNode(renameTargetId, title);
      setRenameTargetId(null);
      setRenameValue("");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to rename item");
    } finally {
      setPending(false);
    }
  }, [onRenameNode, renameTargetId, renameValue]);

  const handleDelete = useCallback(async () => {
    if (!onDeleteNode || !deleteTargetId) return;
    setPending(true);
    setActionError(null);
    try {
      await onDeleteNode(deleteTargetId);
      setDeleteTargetId(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to delete item");
    } finally {
      setPending(false);
    }
  }, [onDeleteNode, deleteTargetId]);

  const handleReorder = useCallback(
    async (nextOrder: string[]) => {
      if (!onReorderChildren) return;
      setPending(true);
      setActionError(null);
      try {
        await onReorderChildren(currentNodeId ?? null, nextOrder);
      } catch (err) {
        setActionError(err instanceof Error ? err.message : "Failed to reorder items");
      } finally {
        setPending(false);
      }
    },
    [onReorderChildren, currentNodeId],
  );

  return (
    <div className="mtu-root">
      <div className={combinedClass}>
        <header className="mtu-header">
          <p className="mtu-header__subtitle">Navigate your nested content</p>
          <h1 className="mtu-header__title">{currentNode?.title ?? "All items"}</h1>
        </header>

        <BreadcrumbBar path={path} onNavigate={goToNode} />
        {(errorMessage || actionError) && (
          <p className="px-4 text-sm text-red-500">{errorMessage ?? actionError}</p>
        )}

        <div className="mtu-content">
          <NodeList
            childrenNodes={children}
            selectedId={selectedChildId}
            onSelect={selectChild}
            onCreate={
              canCreate
                ? () => {
                    setCreateValue("");
                    setCreateModalOpen(true);
                  }
                : undefined
            }
            onOpen={goToNode}
            onReorder={canReorder ? handleReorder : undefined}
            onRename={
              canRename
                ? (id, currentTitle) => {
                    setRenameTargetId(id);
                    setRenameValue(currentTitle);
                  }
                : undefined
            }
            onDelete={canDelete ? (id) => setDeleteTargetId(id) : undefined}
            getChildCount={getChildCount}
          />
        </div>
      </div>

      {canRename && renameTargetId && (
        <div className="mtu-modal">
          <div className="mtu-modal__card">
            <h3>Rename item</h3>
            <input
              className="mtu-input"
              value={renameValue}
              onChange={(event) => setRenameValue(event.target.value)}
              disabled={pending}
            />
            <div className="mtu-modal__actions">
              <button
                type="button"
                className="mtu-btn mtu-btn--ghost"
                onClick={() => setRenameTargetId(null)}
                disabled={pending}
              >
                Cancel
              </button>
              <button
                type="button"
                className="mtu-btn mtu-btn--primary"
                onClick={handleRename}
                disabled={pending}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {canDelete && deleteTargetId && (
        <div className="mtu-modal">
          <div className="mtu-modal__card">
            <h3>Delete item?</h3>
            <p className="mtu-modal__subtitle">This will remove the item and all nested children.</p>
            <div className="mtu-modal__actions">
              <button
                type="button"
                className="mtu-btn mtu-btn--ghost"
                onClick={() => setDeleteTargetId(null)}
                disabled={pending}
              >
                Cancel
              </button>
              <button
                type="button"
                className="mtu-btn mtu-btn--danger"
                onClick={handleDelete}
                disabled={pending}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {canCreate && createModalOpen && (
        <div className="mtu-modal">
          <div className="mtu-modal__card">
            <h3>Add new item</h3>
            <input
              className="mtu-input"
              placeholder="Enter title"
              value={createValue}
              onChange={(event) => setCreateValue(event.target.value)}
              disabled={pending}
            />
            <div className="mtu-modal__actions">
              <button
                type="button"
                className="mtu-btn mtu-btn--ghost"
                onClick={() => setCreateModalOpen(false)}
                disabled={pending}
              >
                Cancel
              </button>
              <button
                type="button"
                className="mtu-btn mtu-btn--primary"
                onClick={handleCreate}
                disabled={pending}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
