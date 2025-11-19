import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchPrimaryCueState,
  resetPrimaryCueDetection,
  runPrimaryCueDetection,
  type PrimaryCueMediaEntry,
  type PrimaryCuePair,
  type PrimaryCueState,
} from '../lib/primaryCueApi'
import { openProjectFile } from '../lib/systemApi'

type PrimaryCuePanelProps = {
  activeProjectPath: string | null
}

const DEFAULT_THRESHOLD = 0.6
const DEFAULT_MIN_GAP = 0.25

const formatTime = (value?: number | null) => {
  if (value === undefined || value === null) return '--'
  return `${value.toFixed(2)}s`
}

const describeHit = (label: string, hit?: { time_s?: number; ref_id?: string | null }) => {
  if (!hit) return `No ${label}`
  if (hit.ref_id) {
    return `${hit.ref_id} @ ${formatTime(hit.time_s)}`
  }
  return `${label} @ ${formatTime(hit.time_s)}`
}

export function PrimaryCuePanel({ activeProjectPath }: PrimaryCuePanelProps) {
  const [state, setState] = useState<PrimaryCueState | null>(null)
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [thresholdInput, setThresholdInput] = useState(DEFAULT_THRESHOLD.toString())
  const [minGapInput, setMinGapInput] = useState(DEFAULT_MIN_GAP.toString())

  const hasProject = Boolean(activeProjectPath)

  const loadState = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!activeProjectPath) {
        setState(null)
        return
      }
      const silent = options?.silent ?? false
      if (!silent) {
        setLoading(true)
        setMessage(null)
      }
      try {
        const payload = await fetchPrimaryCueState(activeProjectPath)
        setState(payload)
        setError(null)
      } catch (err) {
        console.error(err)
        setError(err instanceof Error ? err.message : 'Failed to load primary cue state.')
      } finally {
        if (!silent) {
          setLoading(false)
        }
      }
    },
    [activeProjectPath],
  )

  useEffect(() => {
    loadState()
  }, [loadState])

  useEffect(() => {
    if (!state?.job || state.job.status !== 'running' || !activeProjectPath) {
      return
    }
    const interval = setInterval(() => {
      loadState({ silent: true })
    }, 4000)
    return () => clearInterval(interval)
  }, [state, activeProjectPath, loadState])

  const parseInput = (value: string, fallback: number) => {
    const parsed = parseFloat(value)
    return Number.isFinite(parsed) ? parsed : fallback
  }

  const handleRun = async () => {
    if (!activeProjectPath || running) {
      return
    }
    setRunning(true)
    setMessage(null)
    setError(null)
    try {
      await runPrimaryCueDetection(activeProjectPath, {
        threshold: parseInput(thresholdInput, DEFAULT_THRESHOLD),
        minGapSeconds: parseInput(minGapInput, DEFAULT_MIN_GAP),
      })
      setMessage('Primary cue detection started.')
      loadState({ silent: true })
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Failed to start cue detection.')
    } finally {
      setRunning(false)
    }
  }

  const summary = state?.results?.summary
  const cueBasePath = state?.project_path
    ? `${state.project_path.replace(/\\$/, '')}/ableton/cue_refs`
    : null
  const jobRunning = state?.job?.status === 'running'

  const tableRows = useMemo(() => {
    if (!state?.results?.media) {
      return []
    }
    const rows: { entry: PrimaryCueMediaEntry; pair: PrimaryCuePair | null }[] = []
    state.results.media.forEach((entry) => {
      if (!entry.pairs || entry.pairs.length === 0) {
        rows.push({ entry, pair: null })
        return
      }
      entry.pairs.forEach((pair) => {
        rows.push({ entry, pair })
      })
    })
    return rows
  }, [state])

  const handleReset = async () => {
    if (!activeProjectPath || resetting) {
      return
    }
    setResetting(true)
    setMessage(null)
    try {
      await resetPrimaryCueDetection(activeProjectPath)
      setError(null)
      setMessage('Primary cue results cleared.')
      loadState({ silent: true })
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Failed to reset primary cue results.')
    } finally {
      setResetting(false)
    }
  }

  if (!hasProject) {
    return (
      <section className="ingest-panel">
        <div className="panel-header">
          <div>
            <h2>Primary cue detection</h2>
            <p>Select an active project to analyze cues.</p>
          </div>
        </div>
        <p className="inline-message inline-message--warning">Choose or create a project first.</p>
      </section>
    )
  }

  return (
    <section className="ingest-panel">
      <div className="panel-header">
        <div>
          <h2>Primary cue detection</h2>
          <p>Scan your footage for the universal start/stop cues and review each detected window.</p>
        </div>
        <div className="panel-actions">
          <button className="ghost-button" type="button" onClick={() => loadState()} disabled={loading}>
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
          <button
            className="ghost-button"
            type="button"
            onClick={handleReset}
            disabled={resetting || jobRunning}
          >
            {resetting ? 'Resetting...' : 'Reset results'}
          </button>
        </div>
      </div>

      {error && <p className="inline-message inline-message--error">{error}</p>}
      {message && !error && <p className="inline-message">{message}</p>}
      {state?.job?.status === 'running' && (
        <p className="inline-message inline-message--info">
          Detecting cues... {state.job.progress ? `${state.job.progress.processed}/${state.job.progress.total}` : ''}
        </p>
      )}

      <div className="postprocess-card">
        <h3>Detection settings</h3>
        <div className="form-grid two-column-grid">
          <label>
            <span>Primary threshold</span>
            <input
              type="number"
              min="0"
              max="1"
              step="0.05"
              value={thresholdInput}
              onChange={(event) => setThresholdInput(event.target.value)}
            />
          </label>
          <label>
            <span>Min gap (seconds)</span>
            <input
              type="number"
              min="0"
              step="0.05"
              value={minGapInput}
              onChange={(event) => setMinGapInput(event.target.value)}
            />
          </label>
        </div>
        <div className="panel-actions">
          <button
            className="primary-button"
            type="button"
            onClick={handleRun}
            disabled={running || jobRunning || !hasProject}
          >
            {running ? 'Starting...' : 'Run detection'}
          </button>
        </div>
      </div>

      <div className="postprocess-card">
        <h3>Summary</h3>
        <div className="summary-grid">
          <div>
            <strong>{summary?.files_processed ?? 0}</strong>
            <span>Files processed</span>
          </div>
          <div>
            <strong>{summary?.pairs_detected ?? 0}</strong>
            <span>Primary windows</span>
          </div>
          <div>
            <strong>{summary?.complete_pairs ?? 0}</strong>
            <span>Complete pairs</span>
          </div>
          <div>
            <strong>{summary?.missing_end ?? 0}</strong>
            <span>Missing end</span>
          </div>
          <div>
            <strong>{summary?.missing_start ?? 0}</strong>
            <span>Missing start</span>
          </div>
        </div>
      </div>

      <div className="postprocess-card">
        <h3>Primary cue windows</h3>
        <table className="postprocess-table">
          <thead>
            <tr>
              <th>File</th>
              <th>Pair #</th>
              <th>Start anchor</th>
              <th>Unique start</th>
              <th>End anchor</th>
              <th>Unique end</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {tableRows.map(({ entry, pair }) => {
              if (!pair) {
                return (
                  <tr key={`pair-empty-${entry.file}`}>
                    <td>{entry.relative_path}</td>
                    <td>--</td>
                    <td colSpan={5}>
                      <p className="empty-state">No primary cues detected in this clip.</p>
                    </td>
                    <td className="table-actions">
                      <button className="ghost-button" type="button" onClick={() => entry.file && openProjectFile(entry.file)}>
                        Open video
                      </button>
                    </td>
                  </tr>
                )
              }
              const startUnique = pair.start_secondary_hits?.[0]
              const endUnique = pair.end_secondary_hits?.[0]
              return (
                <tr key={`${entry.file}-${pair.index}`}>
                  <td>{entry.relative_path}</td>
                  <td>{pair.index}</td>
                  <td>{describeHit('start', pair.start_anchor)}</td>
                  <td>{startUnique ? describeHit('unique start', startUnique) : 'No secondary'}</td>
                  <td>{describeHit('end', pair.end_anchor)}</td>
                  <td>{endUnique ? describeHit('unique end', endUnique) : 'No secondary'}</td>
                  <td>
                    <span className={`status-badge status-badge--${pair.status === 'complete' ? 'ready' : 'incomplete'}`}>
                      {pair.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="table-actions">
                    <button className="ghost-button" type="button" onClick={() => entry.file && openProjectFile(entry.file)}>
                      Open video
                    </button>
                    {cueBasePath && startUnique?.ref_id && (
                      <button
                        className="ghost-button"
                        type="button"
                        onClick={() => openProjectFile(`${cueBasePath}/${startUnique.ref_id}`)}
                      >
                        Play start cue
                      </button>
                    )}
                    {cueBasePath && endUnique?.ref_id && (
                      <button
                        className="ghost-button"
                        type="button"
                        onClick={() => openProjectFile(`${cueBasePath}/${endUnique.ref_id}`)}
                      >
                        Play end cue
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
            {tableRows.length === 0 && (
              <tr>
                <td colSpan={8}>
                  <p className="empty-state">Run detection to populate this table.</p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}
