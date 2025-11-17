// features/ideas/LocalIdeasTreePage.tsx
import type { IdeaNodeView, ReorderDirection } from "@ideas/tree-client";
import { useCallback, useMemo, useState } from "react";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { DesktopIdeasTree } from "./components/DesktopIdeasTree";
import { MobileIdeasTree } from "./components/MobileIdeasTree";
import { buildNodesVersion, mapToMobileNodes, mapToProviderNodes } from "./utils/treeNodes";

export function LocalIdeasTreePage() {
    const isMobile = useMediaQuery("(max-width: 768px)");

    // Start with an empty local tree or some demo data
    const [nodes, setNodes] = useState<IdeaNodeView[]>([
        { id: "ideas", parentId: null, title: "Ideas backlog" },
        { id: "marketing", parentId: "ideas", title: "Marketing" },
        { id: "research", parentId: "ideas", title: "User research" },
        { id: "ai-companion", parentId: "ideas", title: "AI companion" },
        { id: "launch-plan", parentId: "marketing", title: "Launch plan" },
        { id: "email-drips", parentId: "marketing", title: "Email drips" },
    ]);

    const providerNodes = useMemo(() => mapToProviderNodes(nodes), [nodes]);
    const mobileNodes = useMemo(() => mapToMobileNodes(nodes), [nodes]);
    const nodesVersion = useMemo(() => buildNodesVersion(nodes), [nodes]);

    const [creatingIdea, setCreatingIdea] = useState(false);
    const [ideaMutationError, setIdeaMutationError] = useState<string | null>(null);

    const handleCreateIdea = useCallback(
        async (
            parentId: string | null,
            rawTitle: string,
            afterId?: string | null,
        ): Promise<IdeaNodeView> => {
            const title = rawTitle.trim() || "Untitled idea";
            setCreatingIdea(true);
            setIdeaMutationError(null);

            // TODO: implement your local-only ID generation & persistence
            const newNode: IdeaNodeView = {
                id: crypto.randomUUID(),
                parentId,
                title,
                // fill in other required IdeaNodeView fields as needed
            } as IdeaNodeView;

            setNodes((prev) => [...prev, newNode]);
            setCreatingIdea(false);
            return newNode;
        },
        [],
    );

    const handleRenameNode = useCallback(async (nodeId: string, title: string) => {
        setNodes((prev) =>
            prev.map((node) =>
                node.id === nodeId
                    ? {
                        ...node,
                        title,
                    }
                    : node,
            ),
        );
    }, []);

    // TODO: add local reorder / move / delete logic if needed
    const handleReorderNode = useCallback(async (_nodeId: string, _direction: ReorderDirection, _targetIndex: number) => { }, []);
    const handleMoveNode = useCallback(async () => { }, []);
    const handleDeleteNode = useCallback(async () => { }, []);

    const handleCreateRootPrompt = useCallback(async () => {
        const title = window.prompt("Name your new idea", "New idea");
        if (title === null) return;
        await handleCreateIdea(null, title);
    }, [handleCreateIdea]);

    if (isMobile) {
        return (
            <MobileIdeasTree
                componentKey={nodesVersion}
                nodes={mobileNodes}
                loading={false}
                error={ideaMutationError}
                initialSelectedId={null}
                onPathChange={() => { }}
                settingsSaving={false}
                settingsError={null}
                onCreateRoot={handleCreateRootPrompt}
                creatingIdea={creatingIdea}
                mutationError={ideaMutationError}
                onCreateIdea={handleCreateIdea}
                onRenameNode={handleRenameNode}
            />
        );
    }

    return (
        <DesktopIdeasTree
            componentKey={nodesVersion}
            nodes={providerNodes}
            loading={false}
            error={ideaMutationError}
            onReorderNode={handleReorderNode}
            onMoveNode={handleMoveNode}
            onDeleteNode={handleDeleteNode}
            onRenameNode={handleRenameNode}
            initialExpandedIds={[]}
            initialSelectedId={null}
            initialStateKey="local"
            onExpandedChange={() => { }}
            onSelectionChange={() => { }}
            settingsHydrated={true}
            onCreateIdea={handleCreateIdea}
        />
    );
}
