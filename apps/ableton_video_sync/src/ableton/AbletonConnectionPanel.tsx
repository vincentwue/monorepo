import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchAbletonConnection,
  triggerAbletonReconnect,
  type AbletonConnectionStatus,
} from '../lib/abletonConnectionApi'

type AbletonConnectionPanelProps = {
  activeProjectPath: string | null
}

const statusLabel = (status: AbletonConnectionStatus | null) => {
  if (!status) {
    return 'Unknown'
  }
  if (status.connected) {
    return 'Connected'
  }
  if (status.error) {
    return 'Error'
  }
  return 'Disconnected'
}

export function AbletonConnectionPanel({ activeProjectPath }: AbletonConnectionPanelProps) {
  const [status, setStatus] = useState<AbletonConnectionStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const loadStatus = useCallback(async (options?: { silent?: boolean }) => {
    const silent = options?.silent ?? false
    if (!silent) {
      setLoading(true)
      setMessage(null)
    }
    try {
      const response = await fetchAbletonConnection()
      setStatus(response)
      setError(null)
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Unable to read Ableton connection status.')
    } finally {
      if (!silent) {
        setLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    loadStatus()
  }, [loadStatus])

  useEffect(() => {
    const interval = setInterval(() => {
      loadStatus({ silent: true })
    }, 5000)
    return () => clearInterval(interval)
  }, [loadStatus])

  const handleReconnect = async () => {
    setReconnecting(true)
    setMessage(null)
    try {
      const response = await triggerAbletonReconnect()
      setStatus(response.status)
      if (response.error) {
        setError(response.error)
      } else if (response.started) {
        setMessage('Reconnect request sent. Give Ableton a moment to respond.')
        setError(null)
      }
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Reconnect request failed.')
    } finally {
      setReconnecting(false)
    }
  }

  const projectMismatch = useMemo(() => {
    if (!status?.project_path || !activeProjectPath) {
      return false
    }
    return status.project_path.toLowerCase() !== activeProjectPath.toLowerCase()
  }, [status, activeProjectPath])

  return (
    <section className="ingest-panel ableton-connection-panel">
      <div className="panel-header">
        <div>
          <h2>Ableton Connection</h2>
          <p>Ensure Live is connected and the current project is saved before triggering cues.</p>
        </div>
        <button className="ghost-button" type="button" onClick={loadStatus} disabled={loading}>
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {error && <p className="inline-message inline-message--error">{error}</p>}
      {message && !error && <p className="inline-message">{message}</p>}
      {!error && status?.warning && (
        <p className="inline-message inline-message--warning">{status.warning}</p>
      )}
      {projectMismatch && (
        <p className="inline-message inline-message--warning">
          Live is open to {status?.project_path ?? 'Unknown'}, but your active project is {activeProjectPath}.
        </p>
      )}

      <div className="connection-status-grid">
        <div className="status-card">
          <span>Status</span>
          <strong className={status?.connected ? 'text-highlight' : ''}>{statusLabel(status)}</strong>
          <small>{status?.timestamp ? new Date(status.timestamp).toLocaleString() : ''}</small>
        </div>
        <div className="status-card">
          <span>Project saved</span>
          <strong>{status?.project_saved ? 'Yes' : 'No'}</strong>
          <small>{status?.project_name || 'No project name'}</small>
        </div>
        <div className="status-card">
          <span>Tempo</span>
          <strong>{status?.tempo ? `${status.tempo.toFixed(1)} BPM` : '—'}</strong>
          <small>{status?.is_playing ? 'Playing' : 'Stopped'}</small>
        </div>
      </div>

      <div className="connection-details">
        <div>
          <p className="label">Live project path</p>
          <p className="value">{status?.project_path || 'Not available'}</p>
        </div>
        <div>
          <p className="label">Active project in UI</p>
          <p className="value">{activeProjectPath || 'No project selected'}</p>
        </div>
      </div>

      <div className="connection-actions">
        <button className="primary-button" type="button" onClick={handleReconnect} disabled={reconnecting}>
          {reconnecting || status?.reconnecting ? 'Reconnecting...' : 'Reconnect to Ableton'}
        </button>
      </div>
    </section>
  )
}
