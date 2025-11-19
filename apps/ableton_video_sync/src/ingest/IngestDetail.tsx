import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import {
  createIngestDevice,
  fetchDiscoveredDevices,
  fetchIngestState,
  startIngestRun,
  previewIngestCounts,
  abortIngestRun,
  type DiscoveredDevice,
  type IngestDevice,
  type IngestRun,
  type IngestPreviewCounts,
} from '../lib/ingestApi'
import { openProjectFolder } from '../lib/systemApi'
import { ANDROID_CAMERA_FOLDERS } from './constants'
import { DirectoryTree } from './DirectoryTree'

type IngestDetailProps = {
  activeProjectPath: string | null
  mainFolder: string | null
  refreshProjects: () => void
  onNavigateToDevices: () => void
}

export function IngestDetail({
  activeProjectPath,
  mainFolder,
  refreshProjects,
  onNavigateToDevices,
}: IngestDetailProps) {
  const [devices, setDevices] = useState<IngestDevice[]>([])
  const [runs, setRuns] = useState<IngestRun[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [runStarting, setRunStarting] = useState(false)
  const [selectedDeviceIds, setSelectedDeviceIds] = useState<string[]>([])
  const [onlyToday, setOnlyToday] = useState(true)
  const [discoveredDevices, setDiscoveredDevices] = useState<DiscoveredDevice[]>([])
  const [dismissedDiscoveryIds, setDismissedDiscoveryIds] = useState<string[]>([])
  const [pendingDiscovery, setPendingDiscovery] = useState<DiscoveredDevice | null>(null)
  const [discoveryForm, setDiscoveryForm] = useState({ name: '', path: '' })
  const [discoverySaving, setDiscoverySaving] = useState(false)
  const [showDiscoveryModal, setShowDiscoveryModal] = useState(false)
  const defaultAndroidPath = ANDROID_CAMERA_FOLDERS[0]
  const [previewCounts, setPreviewCounts] = useState<IngestPreviewCounts>({})

  const loadState = useCallback(async () => {
    setLoading(true)
    try {
      const state = await fetchIngestState()
      setDevices(state.devices ?? [])
      setRuns(state.runs ?? [])
      setSelectedDeviceIds((prev) => prev.filter((id) => state.devices?.some((device) => device.id === id)))
      setError(null)
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Unable to reach ingest server.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadState()
  }, [loadState])

  const fetchDiscovery = useCallback(async () => {
    try {
      const result = await fetchDiscoveredDevices()
      setDiscoveredDevices(result ?? [])
    } catch (err) {
      console.error(err)
    }
  }, [])

  useEffect(() => {
    fetchDiscovery()
    const interval = window.setInterval(fetchDiscovery, 5000)
    return () => window.clearInterval(interval)
  }, [fetchDiscovery])

  const normalizedDevicePaths = useMemo(
    () => devices.map((device) => device.path?.toLowerCase() ?? ''),
    [devices],
  )

  const selectedNewCount = useMemo(() => {
    return selectedDeviceIds.reduce((acc, id) => acc + (previewCounts[id]?.new ?? 0), 0)
  }, [selectedDeviceIds, previewCounts])

  const registeredSerials = useMemo(
    () =>
      devices
        .map((device) => device.adb_serial?.toLowerCase())
        .filter((serial): serial is string => Boolean(serial)),
    [devices],
  )

  const unresolvedDiscovery = useMemo(() => {
    return (
      discoveredDevices.find((device) => {
        const normalizedPath = device.path?.toLowerCase() ?? ''
        const alreadyRegisteredPath = normalizedPath ? normalizedDevicePaths.includes(normalizedPath) : false
        const serial = device.serial?.toLowerCase()
        const alreadyRegisteredSerial = serial ? registeredSerials.includes(serial) : false
        const dismissed = dismissedDiscoveryIds.includes(device.id)
        return !alreadyRegisteredPath && !alreadyRegisteredSerial && !dismissed
      }) ?? null
    )
  }, [discoveredDevices, normalizedDevicePaths, registeredSerials, dismissedDiscoveryIds])

  useEffect(() => {
    if (unresolvedDiscovery && unresolvedDiscovery.id !== pendingDiscovery?.id) {
      setPendingDiscovery(unresolvedDiscovery)
      setDiscoveryForm({
        name: unresolvedDiscovery.label ?? '',
        path:
          unresolvedDiscovery.kind === 'adb'
            ? unresolvedDiscovery.path ?? defaultAndroidPath
            : unresolvedDiscovery.path ?? '',
      })
      setShowDiscoveryModal(true)
    } else if (!unresolvedDiscovery && showDiscoveryModal) {
      setShowDiscoveryModal(false)
      setPendingDiscovery(null)
    }
  }, [pendingDiscovery, unresolvedDiscovery, showDiscoveryModal, defaultAndroidPath])

  const addDismissedDiscovery = (id: string) => {
    setDismissedDiscoveryIds((prev) => (prev.includes(id) ? prev : [...prev, id]))
  }

  const handleOpenOutput = async (device: IngestDevice) => {
    const outputPath = buildOutputPath(device)
    if (!outputPath) {
      setMessage('Select an active project to open output folders.')
      return
    }
    try {
      await openProjectFolder(outputPath)
    } catch (err) {
      console.error(err)
      setMessage(err instanceof Error ? err.message : 'Unable to open output folder.')
    }
  }

  const runsSorted = useMemo(
    () =>
      [...runs].sort(
        (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime(),
      ),
    [runs],
  )
  const loadPreviewCounts = useCallback(async () => {
    if (!activeProjectPath || devices.length === 0) {
      setPreviewCounts({})
      return
    }
    try {
      const response = await previewIngestCounts({
        project_path: activeProjectPath,
        device_ids: devices.map((device) => device.id),
        only_today: onlyToday,
      })
      setPreviewCounts(response.counts ?? {})
    } catch (err) {
      console.error(err)
    }
  }, [activeProjectPath, devices, onlyToday])

  useEffect(() => {
    loadPreviewCounts()
  }, [loadPreviewCounts])

  const buildOutputPath = (device: IngestDevice) => {
    if (!activeProjectPath) return null
    const clean = activeProjectPath.replace(/[\\/]+$/, '')
    const sep = clean.includes('\\') ? '\\' : '/'
    return `${clean}${sep}footage${sep}videos${sep}${device.name}`
  }

  const handleOpenSource = async (device: IngestDevice) => {
    if (device.kind === 'adb') {
      setMessage('Cannot open remote ADB paths.')
      return
    }
    try {
      await openProjectFolder(device.path)
    } catch (err) {
      console.error(err)
      setMessage(err instanceof Error ? err.message : 'Unable to open source folder.')
    }
  }

  const toggleDeviceSelection = (deviceId: string) => {
    setSelectedDeviceIds((prev) =>
      prev.includes(deviceId) ? prev.filter((id) => id !== deviceId) : [...prev, deviceId],
    )
  }

  const handleStartRun = async () => {
    if (!activeProjectPath) {
      setMessage('Select an active project first.')
      return
    }
    if (!selectedDeviceIds.length) {
      setMessage('Choose at least one device to ingest.')
      return
    }

    setRunStarting(true)
    setMessage(null)
    try {
      await startIngestRun({
        project_path: activeProjectPath,
        device_ids: selectedDeviceIds,
        only_today: onlyToday,
      })
      setMessage('Ingest completed. Check your footage folder.')
      refreshProjects()
      loadState()
    } catch (err) {
      console.error(err)
      setMessage(err instanceof Error ? err.message : 'Failed to start ingest.')
    } finally {
      setRunStarting(false)
    }
  }

  const closeDiscoveryModal = (rememberChoice = false) => {
    if (rememberChoice && pendingDiscovery) {
      addDismissedDiscovery(pendingDiscovery.id)
    }
    setShowDiscoveryModal(false)
    setPendingDiscovery(null)
  }

  const handleDiscoveryBrowse = async () => {
    if (pendingDiscovery?.kind === 'adb') {
      setMessage('Enter the folder on your Android device (e.g. /storage/emulated/0/DCIM/Camera).')
      return
    }

    try {
      const result = await window.ipcRenderer.invoke('dialog:choose-directory', {
        title: 'Select device folder',
        defaultPath: discoveryForm.path || mainFolder || undefined,
      })

      if (!result?.canceled && result?.path) {
        setDiscoveryForm((prev) => ({ ...prev, path: result.path }))
      }
    } catch (err) {
      console.error(err)
      setMessage(err instanceof Error ? err.message : 'Unable to open folder chooser.')
    }
  }

  const handleDiscoverySubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!pendingDiscovery) {
      return
    }

    if (!discoveryForm.name.trim()) {
      setMessage('Give the device a name.')
      return
    }

    if (!discoveryForm.path.trim()) {
      setMessage('Choose a folder for this device.')
      return
    }

    setDiscoverySaving(true)
    setMessage(null)
    try {
      await createIngestDevice({
        name: discoveryForm.name.trim(),
        path: discoveryForm.path.trim(),
        kind: pendingDiscovery.kind ?? 'filesystem',
        adb_serial: pendingDiscovery.serial ?? undefined,
      })
      setMessage('Device saved.')
      closeDiscoveryModal(false)
      loadState()
      fetchDiscovery()
    } catch (err) {
      console.error(err)
      setMessage(err instanceof Error ? err.message : 'Unable to save device.')
    } finally {
      setDiscoverySaving(false)
    }
  }

  const handleDiscoverySkip = () => {
    closeDiscoveryModal(true)
  }

  const handleAbortRun = async (runId: string) => {
    try {
      await abortIngestRun(runId)
      setMessage('Ingest run aborted.')
      loadState()
    } catch (err) {
      console.error(err)
      setMessage(err instanceof Error ? err.message : 'Unable to abort run.')
    }
  }

  const disabledStart = !activeProjectPath || selectedDeviceIds.length === 0 || runStarting

  const activeProjectLabel = activeProjectPath ?? 'No active project selected.'

  const formatTimestamp = (value?: string | null) => {
    if (!value) return '—'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return value
    return date.toLocaleString()
  }

  return (
    <section className="ingest-panel">
      <div className="panel-header">
        <div>
          <h2>Ingest</h2>
          <p>
            Active project:{' '}
            <span className={activeProjectPath ? 'text-highlight' : 'text-muted'}>
              {activeProjectLabel}
            </span>
          </p>
        </div>
        <button className="ghost-button" type="button" onClick={loadState} disabled={loading}>
          {loading ? 'Syncing...' : 'Refresh'}
        </button>
      </div>

      {error && <p className="inline-message inline-message--error">{error}</p>}
      {message && !error && <p className="inline-message">{message}</p>}

      <div className="ingest-grid">
        <div className="ingest-card">
          <h3>Start ingest</h3>
          <p>Select which devices to ingest and copy into your active project.</p>

          <div className="ingest-run-options">
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={onlyToday}
                onChange={(event) => setOnlyToday(event.target.checked)}
              />
              <span>Only include clips recorded today</span>
            </label>
            <p className="text-muted">
              Selected devices: <strong>{selectedDeviceIds.length}</strong>
            </p>
            <p className="text-muted">
              Estimated new clips: <strong>{selectedNewCount}</strong>
            </p>
          </div>

          <button
            className="primary-button"
            type="button"
            onClick={handleStartRun}
            disabled={disabledStart}
          >
            {runStarting ? 'Ingesting...' : 'Ingest selected devices'}
          </button>
        </div>

        <div className="ingest-card">
          <h3>Need to add a device?</h3>
          <p>Head to the Devices tab to register new sources or edit existing ones.</p>
          <button className="ghost-button" type="button" onClick={onNavigateToDevices}>
            Go to Devices
          </button>
        </div>
      </div>

      <div className="ingest-card ingest-card--full">
        <h3>Devices</h3>
        {devices.length === 0 ? (
          <div>
            <p className="text-muted">No devices registered yet.</p>
            <button className="ghost-button" type="button" onClick={onNavigateToDevices}>
              Add device
            </button>
          </div>
        ) : (
          <table className="device-table device-table--selectable">
            <thead>
              <tr>
                <th />
                <th>Name</th>
                <th>Source</th>
                <th>Files to copy</th>
                <th>Output</th>
                <th>Last ingested</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {devices.map((device) => (
                <tr key={device.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedDeviceIds.includes(device.id)}
                      onChange={() => toggleDeviceSelection(device.id)}
                    />
                  </td>
                  <td>{device.name}</td>
                  <td>
                    <code className="path-chip">{device.path}</code>
                  </td>
                  <td>
                    <span>
                      {previewCounts[device.id]?.new ?? 0} / {previewCounts[device.id]?.total ?? 0}
                    </span>
                  </td>
                  <td>
                    {activeProjectPath ? (
                      <button
                        type="button"
                        className="ghost-button"
                        onClick={() => handleOpenOutput(device)}
                      >
                        Open output
                      </button>
                    ) : (
                      <span className="text-muted">Select a project</span>
                    )}
                  </td>
                  <td>{formatTimestamp(device.last_ingested_at)}</td>
                  <td>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => handleOpenSource(device)}
                      disabled={device.kind === 'adb'}
                    >
                      Open source
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="ingest-card ingest-card--full">
        <h3>Recent runs</h3>
        {runsSorted.length === 0 ? (
          <p className="text-muted">No ingest runs recorded yet.</p>
        ) : (
          <table className="runs-table">
            <thead>
              <tr>
                <th>Started</th>
                <th>Status</th>
                <th>Devices</th>
                <th>Files copied</th>
                <th>Finished</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {runsSorted.map((run) => (
                <tr key={run.id}>
                  <td>{formatTimestamp(run.started_at)}</td>
                  <td>
                    <span className={`status-badge status-badge--${run.status}`}>
                      {run.status}
                    </span>
                    {run.error && <small className="status-note">{run.error}</small>}
                  </td>
                  <td>{run.device_ids.length}</td>
                  <td>{run.copied_files?.length ?? 0}</td>
                  <td>{formatTimestamp(run.completed_at)}</td>
                  <td>
                    {run.status === 'running' && (
                      <button className="ghost-button" type="button" onClick={() => handleAbortRun(run.id)}>
                        Abort
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showDiscoveryModal && pendingDiscovery && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>New device detected</h3>
            <p>
              We found <strong>{pendingDiscovery.label}</strong>. Pick a folder to link it so future
              ingest runs can use it automatically.
            </p>
            {pendingDiscovery.serial && (
              <p className="text-muted">
                Serial{' '}
                <code className="path-chip">{pendingDiscovery.serial}</code>
              </p>
            )}
            <form className="modal-form" onSubmit={handleDiscoverySubmit}>
              <label>
                <span>Device name</span>
                <input
                  type="text"
                  value={discoveryForm.name}
                  onChange={(event) =>
                    setDiscoveryForm((prev) => ({ ...prev, name: event.target.value }))
                  }
                  placeholder="Camera name"
                />
              </label>
              <label>
                <span>Source folder</span>
                <div className="path-input">
                  <input
                    type="text"
                    value={discoveryForm.path}
                    onChange={(event) =>
                      setDiscoveryForm((prev) => ({ ...prev, path: event.target.value }))
                    }
                    placeholder="Select a folder..."
                  />
                  {pendingDiscovery.kind !== 'adb' && (
                    <button type="button" className="ghost-button" onClick={handleDiscoveryBrowse}>
                      Browse
                    </button>
                  )}
                </div>
              </label>
              <div className="directory-picker">
                <span className="directory-picker__hint">
                  {pendingDiscovery.kind === 'adb' ? 'Browse folders on the device' : 'Or pick from folders below'}
                </span>
                <DirectoryTree
                  selectedPath={discoveryForm.path}
                  initialPath={pendingDiscovery.path || discoveryForm.path || mainFolder || undefined}
                  mode={pendingDiscovery.kind === 'adb' ? 'adb' : 'local'}
                  adbSerial={pendingDiscovery.serial ?? undefined}
                  onSelect={(nextPath) =>
                    setDiscoveryForm((prev) => ({
                      ...prev,
                      path: nextPath,
                    }))
                  }
                />
              </div>
              {pendingDiscovery.kind === 'adb' && (
                <div className="android-path-presets">
                  {ANDROID_CAMERA_FOLDERS.map((folder) => (
                    <button
                      key={folder}
                      type="button"
                      className="ghost-button"
                      onClick={() => setDiscoveryForm((prev) => ({ ...prev, path: folder }))}
                    >
                      {folder}
                    </button>
                  ))}
                </div>
              )}
              <div className="modal-actions">
                <button
                  type="button"
                  className="ghost-button"
                  onClick={handleDiscoverySkip}
                  disabled={discoverySaving}
                >
                  Not now
                </button>
                <button className="primary-button" type="submit" disabled={discoverySaving}>
                  {discoverySaving ? 'Saving...' : 'Save device'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  )
}
