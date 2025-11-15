import { useEffect, useRef, useState } from "react"
import type { PointerEvent as ReactPointerEvent } from "react"
import type { MobileTreeNode } from "../hooks/useMobileTreeNavigator"

interface NodeListProps {
    childrenNodes: MobileTreeNode[]
    selectedId: string | null
    onSelect: (id: string) => void
    onCreate: () => void
    onOpen: (id: string | null) => void
    onReorder: (nextOrder: string[]) => void
    onRename: (id: string, currentTitle: string) => void
    onDelete: (id: string) => void
    getChildCount: (id: string) => number
    onMoveUp: () => void
    onMoveDown: () => void
}

export const NodeList = ({
    childrenNodes,
    selectedId,
    onSelect,
    onCreate,
    onOpen,
    onReorder,
    onRename,
    onDelete,
    getChildCount,
    onMoveUp,
    onMoveDown,
}: NodeListProps) => {
    const [draggingId, setDraggingId] = useState<string | null>(null)
    const itemRefs = useRef<Map<string, HTMLButtonElement | null>>(new Map())
    const childrenRef = useRef(childrenNodes)
    const moveHandlerRef = useRef<(event: PointerEvent) => void>()
    const upHandlerRef = useRef<(event: PointerEvent) => void>()
    const dragDelayRef = useRef<number | null>(null)

    useEffect(() => {
        childrenRef.current = childrenNodes
    }, [childrenNodes])

    useEffect(() => {
        return () => {
            if (moveHandlerRef.current) window.removeEventListener("pointermove", moveHandlerRef.current)
            if (upHandlerRef.current) {
                window.removeEventListener("pointerup", upHandlerRef.current)
                window.removeEventListener("pointercancel", upHandlerRef.current)
            }
            if (dragDelayRef.current !== null) {
                window.clearTimeout(dragDelayRef.current)
                dragDelayRef.current = null
            }
        }
    }, [])

    const startDrag = (id: string) => {
        setDraggingId(id)
        const handleMove = (moveEvent: PointerEvent) => {
            if (!childrenRef.current.length) return
            const order = childrenRef.current.map((child) => child.id)
            const fromIndex = order.indexOf(id)
            if (fromIndex === -1) return

            const entries = childrenRef.current
                .map((node) => {
                    const element = itemRefs.current.get(node.id)
                    if (!element) return null
                    const rect = element.getBoundingClientRect()
                    return { id: node.id, rect }
                })
                .filter(Boolean) as { id: string; rect: DOMRect }[]

            let targetIndex = entries.length - 1
            for (let i = 0; i < entries.length; i++) {
                const entry = entries[i]
                if (moveEvent.clientY < entry.rect.top + entry.rect.height / 2) {
                    targetIndex = i
                    break
                }
            }

            if (targetIndex === fromIndex) return
            const nextOrder = [...order]
            const [moved] = nextOrder.splice(fromIndex, 1)
            nextOrder.splice(targetIndex, 0, moved)
            onReorder(nextOrder)
        }

        const handleUp = () => {
            setDraggingId(null)
            window.removeEventListener("pointermove", handleMove)
            window.removeEventListener("pointerup", handleUp)
            window.removeEventListener("pointercancel", handleUp)
            moveHandlerRef.current = undefined
            upHandlerRef.current = undefined
        }

        moveHandlerRef.current = handleMove
        upHandlerRef.current = handleUp
        window.addEventListener("pointermove", handleMove)
        window.addEventListener("pointerup", handleUp)
        window.addEventListener("pointercancel", handleUp)
    }

    const beginDrag = (id: string) => (event: ReactPointerEvent<HTMLButtonElement>) => {
        event.preventDefault()
        onSelect(id)

        if (dragDelayRef.current !== null) {
            window.clearTimeout(dragDelayRef.current)
            dragDelayRef.current = null
        }

        const cancelPending = () => {
            if (dragDelayRef.current !== null) {
                window.clearTimeout(dragDelayRef.current)
                dragDelayRef.current = null
            }
            window.removeEventListener("pointerup", cancelPending, true)
            window.removeEventListener("pointercancel", cancelPending, true)
        }

        window.addEventListener("pointerup", cancelPending, true)
        window.addEventListener("pointercancel", cancelPending, true)

        dragDelayRef.current = window.setTimeout(() => {
            cancelPending()
            startDrag(id)
        }, 250)
    }

    if (childrenNodes.length === 0) {
        return (
            <div className="mtu-node-empty">
                <p className="mtu-node-empty__text">No items here yet.</p>
                <button type="button" className="mtu-btn mtu-btn--primary" onClick={onCreate}>
                    Create first item
                </button>
            </div>
        )
    }

    return (
        <div className="mtu-node-list">
            <div className="mtu-node-list__header">
                <p className="mtu-node-list__count">{childrenNodes.length} items</p>
                <button type="button" className="mtu-btn mtu-btn--ghost" onClick={onCreate}>
                    + Add item
                </button>
            </div>
            <ul>
                {childrenNodes.map((node) => {
                    const isSelected = node.id === selectedId
                    return (
                        <li key={node.id}>
                            <button
                                type="button"
                                className={`mtu-node-list__item ${isSelected ? "is-selected" : ""} ${draggingId === node.id ? "is-dragging" : ""}`}
                                onClick={() => onOpen(node.id)}
                                onPointerDown={beginDrag(node.id)}
                                ref={(element) => itemRefs.current.set(node.id, element)}
                            >
                                <div className="mtu-node-list__body">
                                    <div>
                                        <p className="mtu-node-list__title">{node.title}</p>
                                        <p className="mtu-node-list__meta" onClick={(event) => event.stopPropagation()}>
                                            Rank #{node.rank + 1}
                                        </p>
                                    </div>
                                    <div className="mtu-node-list__actions">
                                        <span className="mtu-node-list__badge">{getChildCount(node.id)}</span>
                                        <button
                                            type="button"
                                            className="mtu-icon-btn"
                                            title="Open"
                                            onClick={(event) => {
                                                event.stopPropagation()
                                                onOpen(node.id)
                                            }}
                                            onPointerDown={(event) => event.stopPropagation()}
                                        >
                                            ↗
                                        </button>
                                        <button
                                            type="button"
                                            className="mtu-icon-btn"
                                            title="Move up"
                                            disabled={draggingId !== null || node.id !== selectedId}
                                            onClick={(event) => {
                                                event.stopPropagation()
                                                onMoveUp()
                                            }}
                                            onPointerDown={(event) => event.stopPropagation()}
                                        >
                                            ↑
                                        </button>
                                        <button
                                            type="button"
                                            className="mtu-icon-btn"
                                            title="Move down"
                                            disabled={draggingId !== null || node.id !== selectedId}
                                            onClick={(event) => {
                                                event.stopPropagation()
                                                onMoveDown()
                                            }}
                                            onPointerDown={(event) => event.stopPropagation()}
                                        >
                                            ↓
                                        </button>
                                        <button
                                            type="button"
                                            className="mtu-icon-btn"
                                            title="Rename"
                                            onClick={(event) => {
                                                event.stopPropagation()
                                                onRename(node.id, node.title)
                                            }}
                                            onPointerDown={(event) => event.stopPropagation()}
                                        >
                                            ✎
                                        </button>
                                        <button
                                            type="button"
                                            className="mtu-icon-btn mtu-icon-btn--danger"
                                            title="Delete"
                                            onClick={(event) => {
                                                event.stopPropagation()
                                                onDelete(node.id)
                                            }}
                                            onPointerDown={(event) => event.stopPropagation()}
                                        >
                                            🗑
                                        </button>
                                    </div>
                                </div>
                            </button>
                        </li>
                    )
                })}
            </ul>
        </div>
    )
}
