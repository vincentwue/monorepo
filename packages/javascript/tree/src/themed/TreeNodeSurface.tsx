import { NodeTreeNode } from "../internal/buildNodeTree";
import { TreeActions } from "../types";
import { getIndentStyle, NODE_MAX_WIDTH } from "./nodeStyle";

interface TreeNodeSurfaceProps {
    node: NodeTreeNode;
    actions: TreeActions;
    color: string;
    borderColor: string;
    isSelected: boolean;
    isExpanded: boolean;
    indentStyle: ReturnType<typeof getIndentStyle>;
}

export function TreeNodeSurface({
    node,
    actions,
    color,
    borderColor,
    isSelected,
    isExpanded,
    indentStyle,
}: TreeNodeSurfaceProps) {
    const handleSelect = () => {
        if (node._id) actions.select(node._id);
    };

    return (
        <div
            style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                ...indentStyle,
            }}
        >
            {/* --- EXPAND/COLLAPSE BUTTON OUTSIDE --- */}
            {node.children?.length ? (
                <div
                    onClick={(e) => {
                        e.stopPropagation();
                        if (node._id) actions.toggleExpanded(node._id);
                    }}
                    style={{
                        width: 20,
                        height: 20,
                        borderRadius: 6,
                        background: "rgba(255,255,255,0.08)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 12,
                        color: "#e5e7eb",
                        cursor: "pointer",
                        userSelect: "none",

                    }}
                >
                    {isExpanded ? "−" : "+"}
                </div>
            ) : (
                <div style={{ width: 20 }} />
            )}

            {/* --- ACTUAL NODE SURFACE --- */}
            <div
                onClick={handleSelect}
                style={{
                    cursor: node._id ? "pointer" : "default",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    flexGrow: 1,
                    background: color,
                    borderRadius: 10,
                    // width: "100px",
                    padding: "8px 16px",
                    color: "#f6f3ff",
                    fontFamily: '"Source Sans 3", "Inter", system-ui, sans-serif',
                    fontSize: 16,
                    boxShadow: "0 6px 16px rgba(0,0,0,0.35)",

                    // selection border
                    border: isSelected
                        ? "2px solid rgba(120,200,255,0.9)"
                        : "2px solid transparent",
                    maxWidth: NODE_MAX_WIDTH,     // <<< ADD THIS
                    width: "100%",                // <<< Ensures consistent filling
                    overflow: "hidden",           // <<< Prevent overflow
                    textOverflow: "ellipsis",     // optional: truncates long text
                }}
            >
                <span>{node.title}</span>

                <span
                    style={{
                        background: "rgba(15, 23, 42, 0.6)",
                        borderRadius: "50%",
                        border: "1px solid rgba(255,255,255,0.25)",
                        padding: "0 7px",
                        fontSize: 12,
                        color: "#f6f3ff",
                    }}
                >
                    {node.children?.length ?? 0}
                </span>
            </div>
        </div>
    );
}
