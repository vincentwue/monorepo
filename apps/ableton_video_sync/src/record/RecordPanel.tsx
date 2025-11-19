import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  deleteRecording,
  fetchRecordingState,
  updateRecordingState,
  type RecordingEntry,
  type RecordingState,
} from '../lib/recordingApi'
import { openProjectFile } from '../lib/systemApi'

type RecordPanelProps = {
  activeProjectPath: string | null
}

const TrashIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path
      fill="currentColor"
      d="M9 3a1 1 0 0 0-1 1v1H5a1 1 0 1 0 0 2h1v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7h1a1 1 0 1 0 0-2h-3V4a1 1 0 0 0-1-1H9zm1 2h4V4h-4v1zm-1 3v10h2V8H9zm4 0v10h2V8h-2z"
    />
  </svg>
)

const formatDate = (value: unknown) => {
  if (typeof value === 'number') {
    return new Date(value * 1000).toLocaleString()
  }
  if (typeof value === 'string' && value.trim().length > 0) {
    const date = new Date(value)
    if (!Number.isNaN(date.getTime())) {
      return date.toLocaleString()
    }
  }
  return '—'
}

const formatDuration = (entry: RecordingEntry) => {
  if (typeof entry.duration_seconds === 'number') {
    return `${entry.duration_seconds.toFixed(1)}s`
  }
  if (typeof entry.time_start_recording === 'number' && typeof entry.time_end_recording === 'number') {
    const delta = Math.max(0, entry.time_end_recording - entry.time_start_recording)
    return `${delta.toFixed(1)}s`
  }
  return '—'
}

const entryTitle = (entry: RecordingEntry) =>
  (typeof entry.title === 'string' && entry.title) ||
  (typeof entry.name === 'string' && entry.name) ||
  (typeof entry.project_name === 'string' && entry.project_name) ||
  entry.id ||
  'Recording'

const formatBar = (value?: number) => {
  if (!value && value !== 0) return '—'
  return value.toFixed(2)
}

export function RecordPanel({ activeProjectPath }: RecordPanelProps) {
  const [state, setState] = useState<RecordingState | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const hasProject = Boolean(activeProjectPath)

  const loadState = useCallback(
    async (projectPath: string | null, options?: { silent?: boolean }) => {
      if (!projectPath) {
        setState(null)
        return
      }
      const silent = options?.silent ?? false
      if (!silent) {
        setLoading(true)
        setMessage(null)
      }
      try {
        const payload = await fetchRecordingState(projectPath)
        setState(payload)
        setError(null)
      } catch (err) {
        console.error(err)
        setError(err instanceof Error ? err.message : 'Failed to load recording state.')
      } finally {
        if (!silent) {
          setLoading(false)
        }
      }
    },
    [setState],
  )

  useEffect(() => {
    loadState(activeProjectPath)
  }, [activeProjectPath, loadState])

  useEffect(() => {
    if (!activeProjectPath) {
      return
    }
    const interval = setInterval(() => {
      loadState(activeProjectPath, { silent: true })
    }, 5000)
    return () => clearInterval(interval)
  }, [activeProjectPath, loadState])

  const handleMasterToggle = async (enabled: boolean) => {
    if (!activeProjectPath) {
      return
    }
    setSaving(true)
    setMessage(null)
    try {
      const payload = await updateRecordingState(activeProjectPath, enabled)
      setState(payload)
      setError(null)
      setMessage('Recording preferences updated.')
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Failed to update recording state.')
    } finally {
      setSaving(false)
    }
  }

  const recordings = useMemo(() => state?.recordings ?? [], [state])
  const captureEnabled = state ? Boolean(state.capture_enabled ?? state.cues_enabled) : true
  const recordingsFile =
    state?.project_path && activeProjectPath
      ? `${state.project_path.replace(/\\$/, '')}/recordings.json`
      : null

  const handleDeleteRecording = async (recordingId: string) => {
    if (!activeProjectPath || !recordingId) {
      return
    }
    setMessage(null)
    setDeletingId(recordingId)
    try {
      const payload = await deleteRecording(activeProjectPath, recordingId)
      setState(payload)
      setError(null)
      setMessage('Recording deleted.')
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Failed to delete recording.')
    } finally {
      setDeletingId(null)
    }
  }

  if (!hasProject) {
    return (
      <section className="ingest-panel">
        <div className="panel-header">
          <div>
            <h2>Record</h2>
            <p>Select an active project to manage cue playback and recordings.</p>
          </div>
        </div>
        <p className="inline-message inline-message--warning">Choose or create a project first.</p>
      </section>
    )
  }

  return (
    <section className="ingest-panel record-panel">
      <div className="panel-header">
        <div>
          <h2>Record</h2>
          <p>Activate the cues, turn on your cameras, and let them catch the cues before you start playing.</p>
        </div>
        <button className="ghost-button" type="button" onClick={() => loadState(activeProjectPath)} disabled={loading}>
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {error && <p className="inline-message inline-message--error">{error}</p>}
      {message && !error && <p className="inline-message">{message}</p>}
      {!error && state?.warning && <p className="inline-message inline-message--warning">{state.warning}</p>}

      <div className="record-controls">
        <label className="record-toggle">
          <input
            type="checkbox"
            checked={captureEnabled}
            onChange={(event) => handleMasterToggle(event.target.checked)}
            disabled={saving || !state}
          />
          <span>Enable recording capture & cues</span>
        </label>
        <p className="record-note">
          When enabled, cues are played automatically when you start/stop recording inside Ableton and the takes are
          stored in this project.
        </p>
      </div>

      <div className="recordings-table__wrapper">
        <h3>Captured recordings</h3>
        <table className="recordings-table">
          <thead>
            <tr>
              <th>Recording</th>
              <th>Captured</th>
              <th>Duration</th>
              <th>Bars</th>
              <th>Armed tracks</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {recordings.map((entry, index) => (
              <tr key={entry.id ?? `${index}-${entryTitle(entry)}`}>
                <td>{entryTitle(entry)}</td>
                <td>{formatDate(entry.captured_at ?? entry.created_at ?? entry.time_start_recording)}</td>
                <td>{formatDuration(entry)}</td>
                <td>
                  start {formatBar(entry.start_recording_bar)} / end {formatBar(entry.end_recording_bar)}
                </td>
                <td>{Array.isArray(entry.recording_track_names) ? entry.recording_track_names.join(', ') : '—'}</td>
                <td className="recordings-table__actions">
                  <button
                    type="button"
                    className="recording-delete-button"
                    aria-label={`Delete ${entryTitle(entry)}`}
                    title={`Delete ${entryTitle(entry)}`}
                    onClick={() => entry.id && handleDeleteRecording(entry.id)}
                    disabled={!entry.id || deletingId === entry.id}
                  >
                    <TrashIcon />
                  </button>
                </td>
              </tr>
            ))}
            {recordings.length === 0 && (
              <tr>
                <td colSpan={6}>
                  <p className="empty-state">No recordings logged yet.</p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {recordingsFile && (
        <div className="recording-file-bar">
          <span>Recording log:</span>
          <button className="ghost-button" type="button" onClick={() => openProjectFile(recordingsFile)}>
            Open recordings.json
          </button>
        </div>
      )}
    </section>
  )
}
