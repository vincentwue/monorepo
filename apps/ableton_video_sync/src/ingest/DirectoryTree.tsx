import { useCallback, useEffect, useMemo, useState, type JSX } from 'react'
import { browseDiscoveredDirectories } from '../lib/ingestApi'

type DirectoryEntry = {
  path: string
  name: string
  hasChildren: boolean
}

type DirectoryListingResponse = {
  parent: string | null
  entries: DirectoryEntry[]
  error?: string
}

type DirectoryListingState = {
  entries: DirectoryEntry[]
  loading: boolean
  error: string | null
}

type DirectoryTreeProps = {
  selectedPath?: string | null
  initialPath?: string | null
  onSelect: (nextPath: string) => void
  mode?: 'local' | 'adb'
  adbSerial?: string | null
}

const ROOT_KEY = '__root__'
const isWindowsHost = typeof navigator !== 'undefined' && navigator.userAgent.toLowerCase().includes('windows')

type NormalizeOptions = {
  caseInsensitive?: boolean
  treatDriveLetters?: boolean
}

const normalizePathKey = (value?: string | null, options: NormalizeOptions = {}) => {
  const { caseInsensitive = false, treatDriveLetters = false } = options
  if (!value) {
    return ''
  }

  const replaced = value.replace(/\\/g, '/')

  if (replaced === '/') {
    return '/'
  }

  const driveMatch = treatDriveLetters ? replaced.match(/^[a-zA-Z]:\/?$/) : null
  if (driveMatch) {
    const drive = `${driveMatch[0].slice(0, 2)}`
    return caseInsensitive ? `${drive.toLowerCase()}/` : `${drive}/`
  }

  const trimmed = replaced.replace(/\/+$/, '')
  return caseInsensitive ? trimmed.toLowerCase() : trimmed
}

const toKey = (value?: string | null, options?: NormalizeOptions) =>
  value == null ? ROOT_KEY : normalizePathKey(value, options)

const getRootHint = (value?: string | null, options: NormalizeOptions = {}) => {
  if (!value) {
    return null
  }

  const normalized = value.replace(/\\/g, '/')

  const driveMatch = options.treatDriveLetters ? normalized.match(/^[a-zA-Z]:/) : null
  if (driveMatch) {
    return `${driveMatch[0].slice(0, 2)}/`
  }

  if (normalized.startsWith('/')) {
    return '/'
  }

  return null
}

export function DirectoryTree({
  selectedPath,
  initialPath,
  onSelect,
  mode = 'local',
  adbSerial,
}: DirectoryTreeProps) {
  const caseInsensitive = mode !== 'adb' && isWindowsHost
  const driveAware = mode !== 'adb' && isWindowsHost
  const [expandedKeys, setExpandedKeys] = useState<string[]>([ROOT_KEY])
  const [listings, setListings] = useState<Record<string, DirectoryListingState>>({
    [ROOT_KEY]: { entries: [], loading: false, error: null },
  })

  const selectedKey = useMemo(
    () => normalizePathKey(selectedPath, { caseInsensitive, treatDriveLetters: driveAware }),
    [caseInsensitive, driveAware, selectedPath],
  )

  const fetchListing = useCallback(async (path?: string | null) => {
    const key = toKey(path, { caseInsensitive, treatDriveLetters: driveAware })
    setListings((prev) => ({
      ...prev,
      [key]: {
        entries: prev[key]?.entries ?? [],
        loading: true,
        error: null,
      },
    }))

    try {
      let response: DirectoryListingResponse
      if (mode === 'adb') {
        if (!adbSerial) {
          throw new Error('Missing device connection to list folders.')
        }
        response = await browseDiscoveredDirectories(adbSerial, path ?? undefined)
      } else {
        response = await window.ipcRenderer.invoke('filesystem:list-directories', {
          path: path ?? null,
        })
      }

      setListings((prev) => ({
        ...prev,
        [key]: {
          entries: response.entries ?? [],
          loading: false,
          error: response.error ?? null,
        },
      }))
    } catch (error) {
      setListings((prev) => ({
        ...prev,
        [key]: {
          entries: prev[key]?.entries ?? [],
          loading: false,
          error: error instanceof Error ? error.message : 'Unable to load directories.',
        },
      }))
    }
  }, [adbSerial, caseInsensitive, driveAware, mode])

  useEffect(() => {
    fetchListing(null)
  }, [fetchListing])

  useEffect(() => {
    const hint =
      getRootHint(selectedPath, { treatDriveLetters: driveAware }) ??
      getRootHint(initialPath, { treatDriveLetters: driveAware })
    if (!hint) {
      return
    }

    const key = normalizePathKey(hint, { caseInsensitive, treatDriveLetters: driveAware })
    if (!expandedKeys.includes(key)) {
      setExpandedKeys((prev) => [...prev, key])
    }
    if (!listings[key]) {
      fetchListing(hint)
    }
  }, [driveAware, caseInsensitive, expandedKeys, fetchListing, initialPath, listings, selectedPath])

  const handleToggle = useCallback(
    (path: string) => {
      const nodeKey = toKey(path, { caseInsensitive, treatDriveLetters: driveAware })
      const isExpanded = expandedKeys.includes(nodeKey)

      if (isExpanded) {
        setExpandedKeys((prev) => prev.filter((value) => value !== nodeKey))
        return
      }

      setExpandedKeys((prev) => [...prev, nodeKey])

      if (!listings[nodeKey]) {
        fetchListing(path)
      }
    },
    [caseInsensitive, driveAware, expandedKeys, fetchListing, listings],
  )

  const renderNode = useCallback(
    (entry: DirectoryEntry, depth: number): JSX.Element => {
      const nodeKey = toKey(entry.path, { caseInsensitive, treatDriveLetters: driveAware })
      const isExpanded = expandedKeys.includes(nodeKey)
      const isSelected = selectedKey && selectedKey === nodeKey
      const childListing = listings[nodeKey]

      return (
        <li key={nodeKey}>
          <div
            className={`directory-tree__row${isSelected ? ' directory-tree__row--selected' : ''}`}
            style={{ paddingLeft: `${depth * 0.85}rem` }}
          >
            <button
              type="button"
              className="directory-tree__toggle"
              onClick={() => handleToggle(entry.path)}
              disabled={!entry.hasChildren}
              aria-label={isExpanded ? 'Collapse folder' : 'Expand folder'}
            >
              {entry.hasChildren ? (isExpanded ? '▾' : '▸') : '•'}
            </button>
            <button
              type="button"
              className="directory-tree__label"
              onClick={() => onSelect(entry.path)}
              title={entry.path}
            >
              {entry.name}
            </button>
          </div>
          {entry.hasChildren && isExpanded && (
            <ul className="directory-tree__list" role="group">
              {childListing?.loading && childListing.entries.length === 0 && (
                <li className="directory-tree__status">Loading...</li>
              )}
              {childListing?.error && (
                <li className="directory-tree__status directory-tree__status--error">
                  {childListing.error}
                </li>
              )}
              {!childListing?.loading && childListing?.entries.length === 0 && !childListing?.error && (
                <li className="directory-tree__status directory-tree__status--muted">No subfolders here.</li>
              )}
              {childListing?.entries.map((child) => renderNode(child, depth + 1))}
            </ul>
          )}
        </li>
      )
    },
    [caseInsensitive, driveAware, expandedKeys, handleToggle, listings, onSelect, selectedKey],
  )

  const rootListing = listings[ROOT_KEY] ?? { entries: [], loading: false, error: null }

  return (
    <div className="directory-tree" role="tree">
      {rootListing.loading && rootListing.entries.length === 0 ? (
        <div className="directory-tree__status">Loading folders...</div>
      ) : rootListing.entries.length === 0 && rootListing.error ? (
        <div className="directory-tree__status directory-tree__status--error">
          {rootListing.error}
        </div>
      ) : rootListing.entries.length === 0 ? (
        <div className="directory-tree__status directory-tree__status--muted">
          No folders available here.
        </div>
      ) : (
        <ul className="directory-tree__list">
          {rootListing.entries.map((entry) => renderNode(entry, 0))}
        </ul>
      )}
    </div>
  )
}
