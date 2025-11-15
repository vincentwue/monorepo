import { useEffect, useMemo, useRef, useState } from "react"
export interface MobileTreeNode {
    id: string
    parentId: string | null
    title: string
    rank: number
}

export interface BreadcrumbItem {
    id: string | null
    title: string
}

export interface MobileTreeNavigatorProps {
    /**
     * Optional initial node id. If omitted, start at the root level.
     */
    initialNodeId?: string | null
    /**
     * Optional className to style the outer container.
     */
    className?: string
    /**
     * Optional custom dataset for the navigator.
     */
    initialNodes?: MobileTreeNode[]
    /**
     * Called whenever the current node changes so host apps can sync routing/history.
     */
    onPathChange?: (path: BreadcrumbItem[]) => void
}

interface UseMobileTreeNavigatorOptions {
    initialNodeId?: string | null
    initialNodes?: MobileTreeNode[]
    onPathChange?: (path: BreadcrumbItem[]) => void
}

const ROOT_CRUMB: BreadcrumbItem = { id: null, title: "All items" }

const seedNodes: MobileTreeNode[] = [
    { id: "ideas", parentId: null, title: "Ideas", rank: 0 },
    { id: "projects", parentId: null, title: "Projects", rank: 1 },
    { id: "inspiration", parentId: null, title: "Inspiration", rank: 2 },
    { id: "idea-health", parentId: "ideas", title: "Health Tracker", rank: 0 },
    { id: "idea-ai", parentId: "ideas", title: "AI Study Buddy", rank: 1 },
    { id: "idea-food", parentId: "ideas", title: "Smart Kitchen", rank: 2 },
    { id: "project-alpha", parentId: "projects", title: "Project Alpha", rank: 0 },
    { id: "project-beta", parentId: "projects", title: "Project Beta", rank: 1 },
    { id: "alpha-research", parentId: "project-alpha", title: "Research", rank: 0 },
    { id: "alpha-design", parentId: "project-alpha", title: "Design", rank: 1 },
]

const normalizeRanks = (list: MobileTreeNode[], parentId: string | null) => {
    const siblings = list
        .filter((node) => node.parentId === parentId)
        .sort((a, b) => a.rank - b.rank)

    if (siblings.length === 0) return list

    const rankMap = new Map<string, number>()
    siblings.forEach((node, index) => rankMap.set(node.id, index))

    return list.map((node) =>
        rankMap.has(node.id)
            ? {
                  ...node,
                  rank: rankMap.get(node.id)!,
              }
            : node,
    )
}

export const useMobileTreeNavigator = (options: UseMobileTreeNavigatorOptions = {}) => {
    const { initialNodeId = null, initialNodes, onPathChange } = options
    const [nodes, setNodes] = useState<MobileTreeNode[]>(initialNodes ?? seedNodes)
    const [currentNodeId, setCurrentNodeId] = useState<string | null>(initialNodeId ?? null)
    const [selectedChildId, setSelectedChildId] = useState<string | null>(null)
    const idCounterRef = useRef(initialNodes?.length ?? seedNodes.length)

    const currentNode = useMemo(() => {
        if (!currentNodeId) return null
        return nodes.find((node) => node.id === currentNodeId) ?? null
    }, [currentNodeId, nodes])

    const path = useMemo(() => {
        const crumbs: BreadcrumbItem[] = []
        let walkerId = currentNodeId

        while (walkerId) {
            const node = nodes.find((n) => n.id === walkerId)
            if (!node) break
            crumbs.unshift({ id: node.id, title: node.title })
            walkerId = node.parentId
        }

        return [ROOT_CRUMB, ...crumbs]
    }, [currentNodeId, nodes])

    useEffect(() => {
        onPathChange?.(path)
    }, [path, onPathChange])

    const children = useMemo(
        () =>
            nodes
                .filter((node) => node.parentId === currentNodeId)
                .sort((a, b) => a.rank - b.rank),
        [nodes, currentNodeId],
    )

    const selectChild = (id: string | null) => {
        setSelectedChildId((prev) => (prev === id ? null : id))
    }

    const goToNode = (id: string | null) => {
        setCurrentNodeId(id)
        setSelectedChildId(null)
    }

    const moveSelected = (direction: "up" | "down") => {
        if (!selectedChildId) return
        setNodes((prev) => {
            const siblings = prev
                .filter((node) => node.parentId === currentNodeId)
                .sort((a, b) => a.rank - b.rank)
            const index = siblings.findIndex((node) => node.id === selectedChildId)
            if (index === -1) return prev
            const targetIndex = direction === "up" ? index - 1 : index + 1
            if (targetIndex < 0 || targetIndex >= siblings.length) return prev

            const siblingA = siblings[index]
            const siblingB = siblings[targetIndex]
            const next = prev.map((node) => {
                if (node.id === siblingA.id) return { ...node, rank: siblingB.rank }
                if (node.id === siblingB.id) return { ...node, rank: siblingA.rank }
                return node
            })
            return normalizeRanks(next, currentNodeId)
        })
    }

    const moveSelectedUp = () => moveSelected("up")
    const moveSelectedDown = () => moveSelected("down")

    const moveSelectedToParent = () => {
        if (!selectedChildId) return
        setNodes((prev) => {
            const selectedNode = prev.find((node) => node.id === selectedChildId)
            if (!selectedNode) return prev
            const parentId = currentNode?.parentId ?? null
            if (selectedNode.parentId === parentId) return prev

            const siblings = prev
                .filter((node) => node.parentId === parentId)
                .sort((a, b) => a.rank - b.rank)

            const nextRank = siblings.length
            const next = prev.map((node) =>
                node.id === selectedNode.id ? { ...node, parentId, rank: nextRank } : node,
            )
            return normalizeRanks(next, parentId)
        })
    }

    const createChild = (title?: string) => {
        const newId = `node-${Date.now()}-${idCounterRef.current++}`
        setNodes((prev) => {
            const siblings = prev
                .filter((node) => node.parentId === currentNodeId)
                .sort((a, b) => a.rank - b.rank)
            const newNode: MobileTreeNode = {
                id: newId,
                parentId: currentNodeId,
                title: title?.trim() || `Untitled ${siblings.length + 1}`,
                rank: siblings.length,
            }
            return [...prev, newNode]
        })
        setSelectedChildId(newId)
        return newId
    }

    const reorderChildren = (nextOrder: string[]) => {
        setNodes((prev) =>
            prev.map((node) => {
                if (node.parentId !== currentNodeId) return node
                const nextRank = nextOrder.indexOf(node.id)
                if (nextRank === -1) return node
                if (node.rank === nextRank) return node
                return { ...node, rank: nextRank }
            }),
        )
    }

    const renameNode = (id: string, newTitle: string) => {
        setNodes((prev) => prev.map((node) => (node.id === id ? { ...node, title: newTitle } : node)))
    }

    const deleteNode = (id: string) => {
        setNodes((prev) => {
            const toDelete = new Set<string>()
            const collect = (targetId: string) => {
                toDelete.add(targetId)
                prev.forEach((node) => {
                    if (node.parentId === targetId) collect(node.id)
                })
            }
            collect(id)
            return prev.filter((node) => !toDelete.has(node.id))
        })
        setSelectedChildId((prev) => (prev === id ? null : prev))
    }

    const getChildCount = (id: string) => nodes.filter((node) => node.parentId === id).length

    return {
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
    }
}
