import { useState } from "react"
import { useMobileTreeNavigator, type MobileTreeNavigatorProps } from "../hooks/useMobileTreeNavigator"
import "../styles.css"
import { BreadcrumbBar } from "./BreadcrumbBar"
import { NodeList } from "./NodeList"

/**
 * Example usage:
 *
 * ```tsx
 * import { MobileTreeNavigator } from "@monorepo/mobile-tree-ui";
 *
 * export function IdeasScreen() {
 *   return <MobileTreeNavigator initialNodeId={null} />;
 * }
 * ```
 */
export const MobileTreeNavigator = ({
    initialNodeId = null,
    className,
    initialNodes,
    onPathChange,
}: MobileTreeNavigatorProps) => {
    const {
        currentNode,
        path,
        children,
        selectedChildId,
        selectChild,
        goToNode,
        moveSelectedUp,
        moveSelectedDown,
        moveSelectedToParent,
        createChild,
        reorderChildren,
        renameNode,
        deleteNode,
        getChildCount,
    } = useMobileTreeNavigator({ initialNodeId, initialNodes, onPathChange })

    const [renameTargetId, setRenameTargetId] = useState<string | null>(null)
    const [renameValue, setRenameValue] = useState<string>("")
    const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null)
    const [createModalOpen, setCreateModalOpen] = useState(false)
    const [createValue, setCreateValue] = useState("")

    const selectedIndex = children.findIndex((child) => child.id === selectedChildId)
    const disableMoveUp = selectedChildId === null || selectedIndex <= 0
    const disableMoveDown = selectedChildId === null || selectedIndex === children.length - 1
    const disableMoveToParent = selectedChildId === null || (currentNode?.parentId ?? null) === null

    const combinedClass = ["mtu-container", className].filter(Boolean).join(" ")

    return (
        <div className="mtu-root">
            <div className={combinedClass}>
                <header className="mtu-header">
                    <p className="mtu-header__subtitle">Navigate your nested content</p>
                    <h1 className="mtu-header__title">{currentNode?.title ?? "All items"}</h1>
                </header>

                <BreadcrumbBar path={path} onNavigate={goToNode} />

                <div className="mtu-content">
                    <NodeList
                        childrenNodes={children}
                        selectedId={selectedChildId}
                        onSelect={selectChild}
                        onCreate={() => {
                            setCreateValue("")
                            setCreateModalOpen(true)
                        }}
                        onOpen={goToNode}
                        onReorder={reorderChildren}
                        onRename={(id, currentTitle) => {
                            setRenameTargetId(id)
                            setRenameValue(currentTitle)
                        }}
                        onDelete={(id) => setDeleteTargetId(id)}
                        onMoveUp={moveSelectedUp}
                        onMoveDown={moveSelectedDown}
                        getChildCount={getChildCount}
                    />
                </div>
                {/* 
                <NodeActionsBar
                    hasSelection={!!selectedChildId}
                    onGoTo={() => selectedChildId && goToNode(selectedChildId)}
                    onMoveUp={moveSelectedUp}
                    onMoveDown={moveSelectedDown}
                    onMoveToParent={moveSelectedToParent}
                    onCreateChild={() => {
                        setCreateValue("")
                        setCreateModalOpen(true)
                    }}
                    disableMoveUp={disableMoveUp}
                    disableMoveDown={disableMoveDown}
                    disableMoveToParent={disableMoveToParent}
                    showCreateFirst={children.length === 0}
                /> */}
            </div>

            {renameTargetId && (
                <div className="mtu-modal">
                    <div className="mtu-modal__card">
                        <h3>Rename item</h3>
                        <input
                            className="mtu-input"
                            value={renameValue}
                            onChange={(event) => setRenameValue(event.target.value)}
                        />
                        <div className="mtu-modal__actions">
                            <button type="button" className="mtu-btn mtu-btn--ghost" onClick={() => setRenameTargetId(null)}>
                                Cancel
                            </button>
                            <button
                                type="button"
                                className="mtu-btn mtu-btn--primary"
                                onClick={() => {
                                    renameNode(renameTargetId, renameValue.trim() || "Untitled")
                                    setRenameTargetId(null)
                                }}
                            >
                                Save
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {deleteTargetId && (
                <div className="mtu-modal">
                    <div className="mtu-modal__card">
                        <h3>Delete item?</h3>
                        <p className="mtu-modal__subtitle">This will remove the item and all nested children.</p>
                        <div className="mtu-modal__actions">
                            <button type="button" className="mtu-btn mtu-btn--ghost" onClick={() => setDeleteTargetId(null)}>
                                Cancel
                            </button>
                            <button
                                type="button"
                                className="mtu-btn mtu-btn--danger"
                                onClick={() => {
                                    deleteNode(deleteTargetId)
                                    setDeleteTargetId(null)
                                }}
                            >
                                Delete
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {createModalOpen && (
                <div className="mtu-modal">
                    <div className="mtu-modal__card">
                        <h3>Add new item</h3>
                        <input
                            className="mtu-input"
                            placeholder="Enter title"
                            value={createValue}
                            onChange={(event) => setCreateValue(event.target.value)}
                        />
                        <div className="mtu-modal__actions">
                            <button type="button" className="mtu-btn mtu-btn--ghost" onClick={() => setCreateModalOpen(false)}>
                                Cancel
                            </button>
                            <button
                                type="button"
                                className="mtu-btn mtu-btn--primary"
                                onClick={() => {
                                    createChild(createValue)
                                    setCreateModalOpen(false)
                                }}
                            >
                                Save
                            </button>
                            <button
                                type="button"
                                className="mtu-btn mtu-btn--primary"
                                onClick={() => {
                                    createChild(createValue)
                                    setCreateValue("")
                                }}
                            >
                                Save & add another
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
