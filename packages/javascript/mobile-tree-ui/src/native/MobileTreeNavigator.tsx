import type { ReactNode } from "react";
import React, { useCallback, useMemo, useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleProp,
  StyleSheet,
  Text,
  TextInput,
  View,
  ViewStyle,
} from "react-native";
import type { PressableStateCallbackType } from "react-native";
import DraggableFlatList, {
  type DragEndParams,
  type RenderItemParams,
} from "react-native-draggable-flatlist";
import { uiTheme } from "@monorepo/ui-theme";
import {
  type BreadcrumbItem,
  type MobileTreeNode,
  useMobileTreeNavigator,
} from "../hooks/useMobileTreeNavigator";

export interface MobileTreeNavigatorNativeProps {
  nodes: MobileTreeNode[];
  initialNodeId?: string | null;
  style?: StyleProp<ViewStyle>;
  onPathChange?: (path: BreadcrumbItem[]) => void;
  onCreateChild?: (parentId: string | null, title: string) => Promise<void> | void;
  onRenameNode?: (id: string, title: string) => Promise<void> | void;
  onDeleteNode?: (id: string) => Promise<void> | void;
  onReorderChildren?: (parentId: string | null, orderedIds: string[]) => Promise<void> | void;
  disabled?: boolean;
  errorMessage?: string | null;
}

export const MobileTreeNavigatorNative = ({
  nodes,
  initialNodeId = null,
  style,
  onPathChange,
  onCreateChild,
  onRenameNode,
  onDeleteNode,
  onReorderChildren,
  disabled,
  errorMessage,
}: MobileTreeNavigatorNativeProps) => {
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

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createValue, setCreateValue] = useState("");
  const [renameTargetId, setRenameTargetId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const allowReorder = typeof onReorderChildren === "function";
  const canCreate = typeof onCreateChild === "function" && !disabled;
  const canRename = typeof onRenameNode === "function" && !disabled;
  const canDelete = typeof onDeleteNode === "function" && !disabled;

  const selectedIndex = useMemo(() => {
    if (!selectedChildId) return -1;
    return children.findIndex((child) => child.id === selectedChildId);
  }, [children, selectedChildId]);

  const handleGoToSelected = () => {
    if (selectedChildId) {
      goToNode(selectedChildId);
    }
  };

  const handleMove = (direction: "up" | "down") => {
    if (!allowReorder || !onReorderChildren || selectedIndex === -1) return;
    const nextIndex = direction === "up" ? selectedIndex - 1 : selectedIndex + 1;
    if (nextIndex < 0 || nextIndex >= children.length) return;
    const order = children.map((child) => child.id);
    const [moved] = order.splice(selectedIndex, 1);
    order.splice(nextIndex, 0, moved);
    onReorderChildren(currentNodeId ?? null, order);
  };

  const handleDragEnd = useCallback(
    ({ data, from, to }: DragEndParams<MobileTreeNode>) => {
      if (!allowReorder || !onReorderChildren) return;
      if (from === to) return;
      onReorderChildren(
        currentNodeId ?? null,
        data.map((node) => node.id),
      );
    },
    [allowReorder, currentNodeId, onReorderChildren],
  );

  const handleMoveToParent = () => {
    if (!currentNode) return;
    goToNode(currentNode.parentId ?? null);
  };

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

  const renderChild = useCallback(
    ({ item, drag, isActive }: RenderItemParams<MobileTreeNode>) => {
      const isSelected = item.id === selectedChildId;
      return (
        <Pressable
          onPress={() => selectChild(item.id)}
          onLongPress={() => {
            if (!allowReorder || disabled) return;
            selectChild(item.id);
            drag();
          }}
          delayLongPress={200}
          disabled={disabled}
          style={({ pressed }: PressableStateCallbackType) => [
            styles.nodeRow,
            isSelected && styles.nodeRowSelected,
            (pressed || isActive) && styles.nodeRowPressed,
            isActive && styles.nodeRowDragging,
          ]}
        >
          {allowReorder && (
            <View style={styles.dragHandle}>
              <View style={styles.dragHandleDot} />
              <View style={styles.dragHandleDot} />
              <View style={styles.dragHandleDot} />
            </View>
          )}
          <View style={styles.nodeRowBody}>
            <Text style={styles.nodeRowTitle}>{item.title}</Text>
            <Text style={styles.nodeRowMeta}>
              Rank #{item.rank + 1} • {getChildCount(item.id)} children
            </Text>
          </View>
          <View style={styles.nodeRowRight}>
            <Pressable
              style={styles.nodeOpenButton}
              onPress={() => goToNode(item.id)}
              disabled={disabled}
            >
              <Text style={styles.nodeOpenButtonText}>Open</Text>
            </Pressable>
            {canRename && (
              <Pressable
                style={styles.nodeActionButton}
                onPress={() => {
                  setRenameTargetId(item.id);
                  setRenameValue(item.title);
                }}
                disabled={disabled}
              >
                <Text style={styles.nodeActionText}>Rename</Text>
              </Pressable>
            )}
            {canDelete && (
              <Pressable
                style={[styles.nodeActionButton, styles.nodeActionDanger]}
                onPress={() => setDeleteTargetId(item.id)}
                disabled={disabled}
              >
                <Text style={styles.nodeActionDangerText}>Delete</Text>
              </Pressable>
            )}
          </View>
        </Pressable>
      );
    },
    [
      allowReorder,
      canDelete,
      canRename,
      disabled,
      getChildCount,
      goToNode,
      selectChild,
      selectedChildId,
    ],
  );

  return (
    <View style={[styles.container, style]}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.breadcrumbs}
      >
        {path.map((crumb, index) => {
          const isLast = index === path.length - 1;
          return (
            <View key={crumb.id ?? "root"} style={styles.breadcrumbItem}>
              {isLast ? (
                <Text style={styles.breadcrumbCurrent}>{crumb.title}</Text>
              ) : (
                <Pressable onPress={() => goToNode(crumb.id)} disabled={disabled}>
                  <Text style={styles.breadcrumbButton}>{crumb.title}</Text>
                </Pressable>
              )}
              {!isLast && <Text style={styles.breadcrumbDivider}>/</Text>}
            </View>
          );
        })}
      </ScrollView>

      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>{currentNode?.title ?? "All items"}</Text>
        <Text style={styles.sectionSubtitle}>{children.length} items</Text>
      </View>

      <DraggableFlatList
        data={children}
        keyExtractor={(item) => item.id}
        style={styles.list}
        contentContainerStyle={children.length === 0 ? styles.emptyListContainer : undefined}
        renderItem={renderChild}
        onDragEnd={handleDragEnd}
        activationDistance={allowReorder ? 8 : undefined}
        extraData={selectedChildId}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Text style={styles.emptyStateTitle}>No items here yet.</Text>
            {canCreate && (
              <ActionButton
                label="Create first item"
                onPress={() => setCreateModalOpen(true)}
                variant="primary"
                disabled={pending}
              />
            )}
          </View>
        }
      />

      <View style={styles.actions}>
        <ActionButton
          label="Go to selected"
          onPress={handleGoToSelected}
          disabled={!selectedChildId || disabled}
          variant="primary"
        />
        <View style={styles.actionsGrid}>
          <ActionButton
            label="Move up"
            onPress={() => handleMove("up")}
            disabled={!allowReorder || selectedIndex <= 0 || disabled}
          />
          <ActionButton
            label="Move down"
            onPress={() => handleMove("down")}
            disabled={
              !allowReorder || selectedIndex === -1 || selectedIndex === children.length - 1 || disabled
            }
          />
          <ActionButton
            label="To parent"
            onPress={handleMoveToParent}
            disabled={!currentNode || disabled}
          />
          {canCreate && (
            <ActionButton
              label="New item"
              onPress={() => {
                setCreateValue("");
                setCreateModalOpen(true);
              }}
              disabled={pending}
            />
          )}
        </View>
      </View>

      {(errorMessage || actionError) && (
        <Text style={styles.errorText}>{errorMessage ?? actionError}</Text>
      )}

      {canCreate && (
        <FormModal visible={createModalOpen} onRequestClose={() => setCreateModalOpen(false)}>
          <ModalContent
            title="Add new item"
            primaryLabel="Save"
            secondaryLabel="Cancel"
            onPrimary={handleCreate}
            onSecondary={() => setCreateModalOpen(false)}
            disabled={pending}
          >
            <TextInput
              value={createValue}
              onChangeText={setCreateValue}
              placeholder="Enter title"
              placeholderTextColor={uiTheme.colors.textMuted}
              style={styles.input}
              editable={!pending}
            />
          </ModalContent>
        </FormModal>
      )}

      {canRename && renameTargetId && (
        <FormModal visible onRequestClose={() => setRenameTargetId(null)}>
          <ModalContent
            title="Rename item"
            primaryLabel="Save"
            secondaryLabel="Cancel"
            onPrimary={handleRename}
            onSecondary={() => setRenameTargetId(null)}
            disabled={pending}
          >
            <TextInput
              value={renameValue}
              onChangeText={setRenameValue}
              placeholder="Enter new title"
              placeholderTextColor={uiTheme.colors.textMuted}
              style={styles.input}
              editable={!pending}
            />
          </ModalContent>
        </FormModal>
      )}

      {canDelete && deleteTargetId && (
        <FormModal visible onRequestClose={() => setDeleteTargetId(null)}>
          <ModalContent
            title="Delete item?"
            primaryLabel="Delete"
            primaryVariant="danger"
            secondaryLabel="Cancel"
            onPrimary={handleDelete}
            onSecondary={() => setDeleteTargetId(null)}
            disabled={pending}
          >
            <Text style={styles.modalSubtitle}>
              This will remove the item and all nested children.
            </Text>
          </ModalContent>
        </FormModal>
      )}
    </View>
  );
};

interface ActionButtonProps {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  variant?: "default" | "primary" | "danger";
}

const ActionButton = ({ label, onPress, disabled, variant = "default" }: ActionButtonProps) => {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }: PressableStateCallbackType) => [
        styles.actionButton,
        variant === "primary" && styles.actionButtonPrimary,
        variant === "danger" && styles.actionButtonDanger,
        disabled && styles.actionButtonDisabled,
        pressed && !disabled && styles.actionButtonPressed,
      ]}
    >
      <Text
        style={[
          styles.actionButtonLabel,
          variant === "primary" && styles.actionButtonLabelPrimary,
          variant === "danger" && styles.actionButtonLabelPrimary,
          disabled && styles.actionButtonLabelDisabled,
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
};

interface FormModalProps {
  visible: boolean;
  onRequestClose: () => void;
  children: ReactNode;
}

const FormModal = ({ visible, onRequestClose, children }: FormModalProps) => (
  <Modal animationType="fade" transparent visible={visible} onRequestClose={onRequestClose}>
    <View style={styles.modalOverlay}>
      <View style={styles.modalCard}>{children}</View>
    </View>
  </Modal>
);

interface ModalContentProps {
  title: string;
  primaryLabel: string;
  secondaryLabel: string;
  onPrimary: () => void;
  onSecondary: () => void;
  primaryVariant?: "primary" | "danger";
  disabled?: boolean;
  children?: ReactNode;
}

const ModalContent = ({
  title,
  primaryLabel,
  secondaryLabel,
  onPrimary,
  onSecondary,
  primaryVariant = "primary",
  disabled,
  children,
}: ModalContentProps) => (
  <>
    <Text style={styles.modalTitle}>{title}</Text>
    {children}
    <View style={styles.modalActions}>
      <ActionButton label={secondaryLabel} onPress={onSecondary} disabled={disabled} />
      <ActionButton
        label={primaryLabel}
        onPress={onPrimary}
        disabled={disabled}
        variant={primaryVariant}
      />
    </View>
  </>
);

const theme = uiTheme;

const styles = StyleSheet.create({
  container: {
    backgroundColor: theme.colors.card,
    borderRadius: theme.radii.lg,
    padding: theme.spacing.lg,
    gap: theme.spacing.md,
  },
  breadcrumbs: {
    alignItems: "center",
  },
  breadcrumbItem: {
    flexDirection: "row",
    alignItems: "center",
    marginRight: theme.spacing.xs,
  },
  breadcrumbButton: {
    color: theme.colors.brand,
    fontWeight: "600",
  },
  breadcrumbDivider: {
    color: theme.colors.textMuted,
    marginHorizontal: theme.spacing.xs,
  },
  breadcrumbCurrent: {
    color: theme.colors.textPrimary,
    fontWeight: "600",
  },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  sectionTitle: {
    color: theme.colors.textPrimary,
    fontSize: 20,
    fontWeight: "600",
  },
  sectionSubtitle: {
    color: theme.colors.textMuted,
  },
  list: {
    maxHeight: 360,
  },
  emptyListContainer: {
    flexGrow: 1,
    justifyContent: "center",
  },
  nodeRow: {
    backgroundColor: theme.colors.surface,
    borderRadius: theme.radii.md,
    padding: theme.spacing.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: theme.spacing.sm,
  },
  nodeRowPressed: {
    opacity: 0.8,
  },
  nodeRowSelected: {
    borderWidth: theme.borderWidth.hairline,
    borderColor: theme.colors.brand,
  },
  nodeRowDragging: {
    borderWidth: theme.borderWidth.hairline,
    borderColor: theme.colors.brandStrong,
    opacity: 0.95,
  },
  dragHandle: {
    marginRight: theme.spacing.sm,
    height: 24,
    justifyContent: "space-between",
    alignItems: "center",
  },
  dragHandleDot: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: theme.colors.textMuted,
  },
  nodeRowBody: {
    flex: 1,
    marginRight: theme.spacing.sm,
  },
  nodeRowTitle: {
    color: theme.colors.textPrimary,
    fontSize: 16,
    fontWeight: "600",
    marginBottom: theme.spacing.xs,
  },
  nodeRowMeta: {
    color: theme.colors.textMuted,
    fontSize: 13,
  },
  nodeRowRight: {
    flexDirection: "row",
    alignItems: "center",
  },
  nodeOpenButton: {
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: theme.spacing.xs,
    borderRadius: theme.radii.sm,
    borderWidth: theme.borderWidth.hairline,
    borderColor: theme.colors.borderSoft,
    marginLeft: theme.spacing.xs,
  },
  nodeOpenButtonText: {
    color: theme.colors.brand,
    fontWeight: "600",
  },
  nodeActionButton: {
    marginLeft: theme.spacing.xs,
    paddingHorizontal: theme.spacing.xs,
    paddingVertical: theme.spacing.xs,
    borderRadius: theme.radii.sm,
  },
  nodeActionText: {
    color: theme.colors.textMuted,
    fontSize: 13,
  },
  nodeActionDanger: {
    backgroundColor: "transparent",
  },
  nodeActionDangerText: {
    color: theme.colors.error,
    fontSize: 13,
    fontWeight: "600",
  },
  emptyState: {
    alignItems: "center",
    padding: theme.spacing.lg,
    borderRadius: theme.radii.md,
    borderWidth: theme.borderWidth.hairline,
    borderColor: theme.colors.borderSoft,
  },
  emptyStateTitle: {
    color: theme.colors.textMuted,
    marginBottom: theme.spacing.sm,
  },
  actions: {
    gap: theme.spacing.sm,
  },
  actionsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: theme.spacing.sm,
  },
  actionButton: {
    paddingVertical: theme.spacing.sm,
    paddingHorizontal: theme.spacing.md,
    borderRadius: theme.radii.md,
    backgroundColor: theme.colors.surface,
    borderWidth: theme.borderWidth.hairline,
    borderColor: theme.colors.borderSoft,
    minWidth: 120,
    alignItems: "center",
  },
  actionButtonPrimary: {
    backgroundColor: theme.colors.brandStrong,
    borderColor: theme.colors.brandStrong,
  },
  actionButtonDanger: {
    backgroundColor: theme.colors.error,
    borderColor: theme.colors.error,
  },
  actionButtonPressed: {
    opacity: 0.85,
  },
  actionButtonDisabled: {
    opacity: theme.opacity.disabled,
  },
  actionButtonLabel: {
    color: theme.colors.textPrimary,
    fontWeight: "600",
  },
  actionButtonLabelPrimary: {
    color: theme.colors.background,
  },
  actionButtonLabelDisabled: {
    color: theme.colors.textMuted,
  },
  errorText: {
    color: theme.colors.error,
  },
  input: {
    borderWidth: theme.borderWidth.hairline,
    borderColor: theme.colors.borderSoft,
    borderRadius: theme.radii.md,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    color: theme.colors.textPrimary,
    marginBottom: theme.spacing.md,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(2, 6, 23, 0.75)",
    justifyContent: "center",
    padding: theme.spacing.lg,
  },
  modalCard: {
    backgroundColor: theme.colors.card,
    borderRadius: theme.radii.lg,
    padding: theme.spacing.lg,
    gap: theme.spacing.md,
  },
  modalTitle: {
    color: theme.colors.textPrimary,
    fontSize: 18,
    fontWeight: "600",
  },
  modalSubtitle: {
    color: theme.colors.textMuted,
    marginBottom: theme.spacing.md,
  },
  modalActions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: theme.spacing.sm,
  },
});
