import { useCallback, useEffect, useState } from 'react'
import { createIngestDevice, deleteIngestDevice, fetchIngestState, type IngestDevice } from '../lib/ingestApi'
import { openProjectFolder } from '../lib/systemApi'
import { ANDROID_CAMERA_FOLDERS } from './constants'

type DevicesPanelProps = {
  mainFolder: string | null
  activeProjectPath: string | null
}

type DeviceKind = 'filesystem' | 'adb'

const createDeviceForm = () => ({
  name: '',
  path: '',
  kind: 'filesystem' as DeviceKind,
  adbSerial: '',
})

export function DevicesPanel({ mainFolder, activeProjectPath }: DevicesPanelProps) {
  const [devices, setDevices] = useState<IngestDevice[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [form, setForm] = useState(createDeviceForm)
  const [saving, setSaving] = useState(false)
  const isAdbSource = form.kind === 'adb'

  const loadDevices = useCallback(async () => {
    setLoading(true)
    try {
      const state = await fetchIngestState()
      setDevices(state.devices ?? [])
      setError(null)
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Unable to reach ingest server.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDevices()
  }, [loadDevices])

  const handleChoosePath = async () => {
    if (isAdbSource) {
      return
    }
    try {
      const result = await window.ipcRenderer.invoke('dialog:choose-directory', {
        title: 'Select device root folder',
        defaultPath: form.path || mainFolder || undefined,
      })

      if (!result?.canceled && result?.path) {
        setForm((prev) => ({ ...prev, path: result.path }))
      }
    } catch (err) {
      console.error(err)
      setMessage(err instanceof Error ? err.message : 'Unable to open folder chooser.')
    }
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!form.name.trim() || !form.path.trim()) {
      setMessage('Enter a device name and source folder.')
      return
    }

    setSaving(true)
    setMessage(null)
    try {
      await createIngestDevice({
        name: form.name.trim(),
        path: form.path.trim(),
        kind: form.kind,
        adb_serial: isAdbSource ? form.adbSerial.trim() || undefined : undefined,
      })
      setForm(createDeviceForm())
      setMessage('Device saved.')
      loadDevices()
    } catch (err) {
      console.error(err)
      setMessage(err instanceof Error ? err.message : 'Unable to save device.')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteDevice = async (deviceId: string) => {
    try {
      await deleteIngestDevice(deviceId)
      setMessage('Device removed.')
      loadDevices()
    } catch (err) {
      console.error(err)
      setMessage(err instanceof Error ? err.message : 'Unable to delete device.')
    }
  }

  const formatTimestamp = (value?: string | null) => {
    if (!value) return '—'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return value
    return date.toLocaleString()
  }

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

  return (
    <section className="ingest-panel">
      <div className="panel-header">
        <div>
          <h2>Devices</h2>
          <p>Register folders we can ingest from.</p>
        </div>
        <button className="ghost-button" type="button" onClick={loadDevices} disabled={loading}>
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {error && <p className="inline-message inline-message--error">{error}</p>}
      {message && !error && <p className="inline-message">{message}</p>}

      <div className="ingest-card ingest-card--full">
        <h3>Add device</h3>
        <form className="ingest-form" onSubmit={handleSubmit}>
          <label>
            <span>Device name</span>
            <input
              type="text"
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              placeholder="Lumix Camera"
              disabled={saving}
            />
          </label>
          <label>
            <span>Source type</span>
            <select
              value={form.kind}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, kind: event.target.value as DeviceKind }))
              }
              disabled={saving}
            >
              <option value="filesystem">Mounted drive or SD card</option>
              <option value="adb">Android (ADB)</option>
            </select>
          </label>
          {isAdbSource && (
            <label>
              <span>ADB serial (optional)</span>
              <input
                type="text"
                value={form.adbSerial}
                onChange={(event) => setForm((prev) => ({ ...prev, adbSerial: event.target.value }))}
                placeholder="e.g. 2A101FDH2006TG"
                disabled={saving}
              />
            </label>
          )}
          <label>
            <span>{isAdbSource ? 'Remote folder on device' : 'Source folder'}</span>
            <div className="path-input">
              <input
                type="text"
                value={form.path}
                onChange={(event) => setForm((prev) => ({ ...prev, path: event.target.value }))}
                placeholder={isAdbSource ? '/storage/emulated/0/DCIM/Camera' : 'D:/footage/lumix'}
                disabled={saving}
              />
              {!isAdbSource && (
                <button className="ghost-button" type="button" onClick={handleChoosePath} disabled={saving}>
                  Browse
                </button>
              )}
            </div>
          </label>
          {isAdbSource && (
            <div className="android-path-presets">
              {ANDROID_CAMERA_FOLDERS.map((folder) => (
                <button
                  key={folder}
                  type="button"
                  className="ghost-button"
                  onClick={() => setForm((prev) => ({ ...prev, path: folder }))}
                  disabled={saving}
                >
                  {folder}
                </button>
              ))}
            </div>
          )}
          <button className="primary-button" type="submit" disabled={saving}>
            {saving ? 'Saving...' : 'Save device'}
          </button>
        </form>
      </div>

      <div className="ingest-card ingest-card--full">
        <h3>Registered devices</h3>
        {devices.length === 0 ? (
          <p className="text-muted">No devices yet. Add one above.</p>
        ) : (
          <table className="device-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Source</th>
                <th>Last ingested</th>
                <th>Output</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {devices.map((device) => (
                <tr key={device.id}>
                  <td>{device.name}</td>
                  <td>
                    <code className="path-chip">{device.path}</code>
                  </td>
                  <td>{formatTimestamp(device.last_ingested_at)}</td>
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
                  <td>
                    <div className="table-actions">
                      <button
                        type="button"
                        className="ghost-button"
                        onClick={() => handleOpenSource(device)}
                        disabled={device.kind === 'adb'}
                      >
                        Open source
                      </button>
                      <button
                        type="button"
                        className="ghost-button"
                        onClick={() => handleDeleteDevice(device.id)}
                      >
                        Remove
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}
