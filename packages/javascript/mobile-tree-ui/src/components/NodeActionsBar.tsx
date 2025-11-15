interface NodeActionsBarProps {
    hasSelection: boolean
    onGoTo: () => void
    onMoveUp: () => void
    onMoveDown: () => void
    onMoveToParent: () => void
    onCreateChild: () => void
    disableMoveUp?: boolean
    disableMoveDown?: boolean
    disableMoveToParent?: boolean
    showCreateFirst?: boolean
}

export const NodeActionsBar = ({
    hasSelection,
    onGoTo,
    onMoveUp,
    onMoveDown,
    onMoveToParent,
    onCreateChild,
    disableMoveDown,
    disableMoveUp,
    disableMoveToParent,
    showCreateFirst,
}: NodeActionsBarProps) => (
    <div className="mtu-actions">
        {showCreateFirst ? (
            <button type="button" className="mtu-btn mtu-btn--primary mtu-actions__full" onClick={onCreateChild}>
                Create first item
            </button>
        ) : (
            <>
                <button
                    type="button"
                    className="mtu-btn mtu-btn--primary mtu-actions__full"
                    disabled={!hasSelection}
                    onClick={onGoTo}
                >
                    Go to selected
                </button>
                <div className="mtu-actions__grid">
                    <button
                        type="button"
                        className="mtu-btn"
                        disabled={!hasSelection || disableMoveUp}
                        onClick={onMoveUp}
                    >
                        ↑ Move up
                    </button>
                    <button
                        type="button"
                        className="mtu-btn"
                        disabled={!hasSelection || disableMoveDown}
                        onClick={onMoveDown}
                    >
                        ↓ Move down
                    </button>
                    <button
                        type="button"
                        className="mtu-btn"
                        disabled={!hasSelection || disableMoveToParent}
                        onClick={onMoveToParent}
                    >
                        ↰ To parent
                    </button>
                    <button type="button" className="mtu-btn" onClick={onCreateChild}>
                        + New item
                    </button>
                </div>
            </>
        )}
    </div>
)
