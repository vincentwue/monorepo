import { useCallback, useEffect, useMemo, useState } from "react";

import type { IdeaTreeUiState, IdeasApiClient } from "@ideas/tree-client";
import type { MobileTreeNavigatorProps } from "@monorepo/mobile-tree-ui";

import {
  arraysEqual,
  buildSettingsKey,
  normalizeExpandedIds,
} from "../utils/treeNodes";

const DEFAULT_TREE_STATE: IdeaTreeUiState = {
  expandedIds: [],
  selectedId: null,
};

interface UseIdeaTreeSettingsResult {
  ideaTreeSettings: IdeaTreeUiState;
  settingsHydrated: boolean;
  settingsSaving: boolean;
  settingsError: string | null;
  settingsKey: string;
  handleExpandedIdsChange: (ids: string[]) => void;
  handleSelectionChange: (selectedId: string | null) => void;
  handleMobilePathChange: NonNullable<MobileTreeNavigatorProps["onPathChange"]>;
}

export function useIdeaTreeSettings(client: IdeasApiClient): UseIdeaTreeSettingsResult {
  const [ideaTreeSettings, setIdeaTreeSettings] =
    useState<IdeaTreeUiState>(DEFAULT_TREE_STATE);
  const [settingsHydrated, setSettingsHydrated] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [settingsDirty, setSettingsDirty] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);

  const applyRemoteSettings = useCallback((next: IdeaTreeUiState) => {
    setIdeaTreeSettings(next);
    setSettingsDirty(false);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadSettings = async () => {
      try {
        const state = await client.getIdeaTreeState();
        if (cancelled) return;
        applyRemoteSettings(state);
        setSettingsHydrated(true);
        setSettingsError(null);
      } catch (err: unknown) {
        if (cancelled) return;
        console.error("[useIdeaTreeSettings] failed to load tree settings", err);
        setSettingsHydrated(true);
        setSettingsError(err instanceof Error ? err.message : "Failed to load tree view");
      }
    };
    void loadSettings();
    return () => {
      cancelled = true;
    };
  }, [client, applyRemoteSettings]);

  useEffect(() => {
    if (!settingsHydrated || !settingsDirty) return;
    const timeout = window.setTimeout(() => {
      setSettingsSaving(true);
      client
        .updateIdeaTreeState(ideaTreeSettings)
        .then((next) => {
          applyRemoteSettings(next);
          setSettingsSaving(false);
          setSettingsError(null);
        })
        .catch((err: unknown) => {
          console.error("[useIdeaTreeSettings] failed to save tree settings", err);
          setSettingsSaving(false);
          setSettingsError(
            err instanceof Error ? err.message : "Failed to save tree view settings",
          );
        });
    }, 600);
    return () => {
      window.clearTimeout(timeout);
    };
  }, [client, ideaTreeSettings, settingsDirty, settingsHydrated, applyRemoteSettings]);

  const updateTreeSettings = useCallback(
    (updater: (prev: IdeaTreeUiState) => IdeaTreeUiState) => {
      let changed = false;
      setIdeaTreeSettings((prev) => {
        const next = updater(prev);
        if (
          next === prev ||
          (next.selectedId === prev.selectedId &&
            arraysEqual(next.expandedIds, prev.expandedIds))
        ) {
          return prev;
        }
        changed = true;
        return next;
      });
      if (changed && settingsHydrated) {
        setSettingsDirty(true);
      }
    },
    [settingsHydrated],
  );

  const handleExpandedIdsChange = useCallback(
    (ids: string[]) => {
      const normalized = normalizeExpandedIds(ids);
      updateTreeSettings((prev) => ({ ...prev, expandedIds: normalized }));
    },
    [updateTreeSettings],
  );

  const handleSelectionChange = useCallback(
    (selectedId: string | null) => {
      updateTreeSettings((prev) => ({ ...prev, selectedId: selectedId ?? null }));
    },
    [updateTreeSettings],
  );

  const handleMobilePathChange = useCallback<
    NonNullable<MobileTreeNavigatorProps["onPathChange"]>
  >(
    (path) => {
      const expandedIds = normalizeExpandedIds(
        path
          .map((crumb) => crumb?.id ?? null)
          .filter((id): id is string => typeof id === "string" && id.length > 0),
      );
      const selectedId = path.length ? path[path.length - 1]?.id ?? null : null;
      updateTreeSettings((prev) => ({
        ...prev,
        expandedIds,
        selectedId: selectedId ?? null,
      }));
    },
    [updateTreeSettings],
  );

  const settingsKey = useMemo(
    () => buildSettingsKey(ideaTreeSettings),
    [ideaTreeSettings],
  );

  return {
    ideaTreeSettings,
    settingsHydrated,
    settingsSaving,
    settingsError,
    settingsKey,
    handleExpandedIdsChange,
    handleSelectionChange,
    handleMobilePathChange,
  };
}
