import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchPostprocessState,
  runPostprocess,
  type PostprocessState,
} from '../lib/postprocessApi'
import { openProjectFile, openProjectFolder } from '../lib/systemApi'

type PostprocessPanelProps = {
  activeProjectPath: string | null
}

const DEFAULT_THRESHOLD = 0.6
const DEFAULT_MIN_GAP = 0.25

const CUE_LEGEND = [
  {
    key: 'start-primary',
    label: 'Primary start cue',
    description: 'Barker/standard cue that should always be audible.',
  },
  {
    key: 'start-secondary',
    label: 'Secondary start cue',
    description: 'Project-specific cue to link footage with recordings.',
  },
  {
    key: 'end-primary',
    label: 'Primary end cue',
    description: 'Barker/standard cue near the stop marker.',
  },
  {
    key: 'end-secondary',
    label: 'Secondary end cue',
    description: 'Project-specific stop cue to confirm the take.',
  },
]

const formatDuration = (value?: number | null) => {
  if (!value && value !== 0) return '—'
  const minutes = Math.floor(value / 60)
  const seconds = Math.round(value % 60)
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

const formatDate = (value?: string | null) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

const toPercentage = (value: number) => Math.min(100, Math.max(0, value))

type CueSummary = {
  primary?: boolean
  secondary?: boolean
}

type CueStatusProps = {
  label: string
  summary?: CueSummary
}

function CueStatus({ label, summary }: CueStatusProps) {
  const hasPrimary = Boolean(summary?.primary)
  const hasSecondary = Boolean(summary?.secondary)
  return (
    <div className="cue-status">
      <span className="cue-status__label">{label}</span>
      <span className={`cue-dot cue-dot--${label.toLowerCase()}-primary${hasPrimary ? '' : ' cue-dot--missing'}`} />
      <span className="cue-status__text">{hasPrimary ? 'Primary' : 'No primary'}</span>
      <span className={`cue-dot cue-dot--${label.toLowerCase()}-secondary${hasSecondary ? '' : ' cue-dot--missing'}`} />
      <span className="cue-status__text">{hasSecondary ? 'Secondary' : 'No secondary'}</span>
    </div>
  )
}

export function PostprocessPanel({ activeProjectPath }: PostprocessPanelProps) {
  const [state, setState] = useState<PostprocessState | null>(null)
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [settingsError, setSettingsError] = useState<string | null>(null)
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
        const payload = await fetchPostprocessState(activeProjectPath)
        setState(payload)
        setError(null)
      } catch (err) {
        console.error(err)
        setError(err instanceof Error ? err.message : 'Failed to load postprocess state.')
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
  }, [state, loadState, activeProjectPath])

  const handleRun = async () => {
    if (!activeProjectPath) return
    setSettingsError(null)
    const thresholdValue =
      thresholdInput.trim() === '' ? undefined : Number.parseFloat(thresholdInput)
    if (
      thresholdValue !== undefined &&
      (!Number.isFinite(thresholdValue) || thresholdValue < 0 || thresholdValue > 1)
    ) {
      setSettingsError('Threshold must be between 0 and 1.')
      return
    }
    const minGapValue = minGapInput.trim() === '' ? undefined : Number.parseFloat(minGapInput)
    if (minGapValue !== undefined && (!Number.isFinite(minGapValue) || minGapValue < 0)) {
      setSettingsError('Minimum gap must be zero or a positive number.')
      return
    }
    setRunning(true)
    setMessage(null)
    try {
      await runPostprocess(activeProjectPath, {
        threshold: thresholdValue,
        minGapSeconds: minGapValue,
      })
      setMessage('Postprocess started. This may take a moment...')
      loadState({ silent: true })
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Failed to start postprocess.')
    } finally {
      setRunning(false)
    }
  }

  const results = state?.results
  const mediaEntries = useMemo(() => results?.media ?? [], [results])
  const summary = results?.summary
  const matchesFile = results?.project_path ? `${results.project_path}/postprocess_matches.json` : null
  const matchesFolder = matchesFile
    ? matchesFile.replace(/[\\/][^\\/]*$/, '')
    : null
  const lastSettings = results?.settings
  const summaryTrackNames = useMemo(() => {
    const trackSet = new Set<string>()
    mediaEntries.forEach((entry) => {
      entry.track_names?.forEach((name) => {
        if (name) {
          trackSet.add(name)
        }
      })
    })
    return Array.from(trackSet).sort((a, b) => a.localeCompare(b))
  }, [mediaEntries])

  const topFiles = useMemo(() => {
    return [...mediaEntries].sort((a, b) => (b.top_score ?? 0) - (a.top_score ?? 0)).slice(0, 5)
  }, [mediaEntries])

  useEffect(() => {
    if (!lastSettings) {
      return
    }
    setThresholdInput(lastSettings.threshold.toString())
    setMinGapInput(lastSettings.min_gap_s.toString())
  }, [lastSettings])

  if (!hasProject) {
    return (
      <section className="ingest-panel">
        <div className="panel-header">
          <div>
            <h2>Postprocess footage</h2>
            <p>Select a project first to analyze footage.</p>
          </div>
        </div>
        <p className="inline-message inline-message--warning">Choose an active project to continue.</p>
      </section>
    )
  }

  return (
    <section className="ingest-panel postprocess-panel">
      <div className="panel-header">
        <div>
          <h2>Postprocess footage</h2>
          <p>Scan your footage for cue matches and review the detected segments.</p>
        </div>
        <div className="postprocess-actions">
          <button className="ghost-button" type="button" onClick={() => loadState()} disabled={loading}>
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
          <button className="primary-button" type="button" onClick={handleRun} disabled={running || !hasProject}>
            {running || state?.job?.status === 'running' ? 'Processing...' : 'Run postprocess'}
          </button>
        </div>
      </div>
      <p className="postprocess-settings__note">
        <strong>Threshold</strong> controls how strong a cue match must be (lower it to catch faint cues, raise it to
        avoid false positives). <strong>Minimum gap</strong> enforces the spacing between hits so echoes don’t create
        duplicate segments. If you regularly need finer control, we can surface extra parameters such as minimum segment
        length or frequency-weighted matching.
      </p>
      <div className="postprocess-settings">
        <div className="postprocess-settings__field">
          <label htmlFor="threshold-input">
            Match threshold <small>(0-1, default {DEFAULT_THRESHOLD.toFixed(2)})</small>
          </label>
          <input
            id="threshold-input"
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={thresholdInput}
            onChange={(event) => setThresholdInput(event.target.value)}
          />
        </div>
        <div className="postprocess-settings__field">
          <label htmlFor="min-gap-input">
            Minimum gap (seconds) <small>(default {DEFAULT_MIN_GAP}s)</small>
          </label>
          <input
            id="min-gap-input"
            type="number"
            min={0}
            step={0.05}
            value={minGapInput}
            onChange={(event) => setMinGapInput(event.target.value)}
          />
        </div>
        {lastSettings && (
          <div className="postprocess-settings__info">
            <span>Last run used threshold {lastSettings.threshold.toFixed(2)} / gap {lastSettings.min_gap_s}s.</span>
          </div>
        )}
      </div>

      {error && <p className="inline-message inline-message--error">{error}</p>}
      {settingsError && <p className="inline-message inline-message--error">{settingsError}</p>}
      {message && !error && <p className="inline-message">{message}</p>}
      {state?.job && (
        <p className={`inline-message ${state.job.status === 'failed' ? 'inline-message--error' : ''}`}>
          Status: <strong>{state.job.status}</strong>
          {state.job.progress && state.job.progress.total > 0 && (
            <> ({state.job.progress.processed}/{state.job.progress.total})</>
          )}
          {state.job.error && ` – ${state.job.error}`}
        </p>
      )}

      {summary && (
        <div className="postprocess-summary">
          <div className="status-card">
            <span>Files processed</span>
            <strong>{summary.files_processed}</strong>
          </div>
          <div className="status-card">
            <span>Segments detected</span>
            <strong>{summary.segments_detected}</strong>
          </div>
          <div className="status-card">
            <span>Last run</span>
            <strong>{formatDate(results?.generated_at)}</strong>
          </div>
          <div className="status-card">
            <span>Cues used</span>
            <strong>{summary.cue_refs_used.length}</strong>
            <small>
              {summaryTrackNames.length > 0
                ? summaryTrackNames.join(', ')
                : summary.cue_refs_used.join(', ') || 'None'}
            </small>
          </div>
        </div>
      )}

      {matchesFile && (
        <div className="recording-file-bar">
          <span>Matches file:</span>
          <button className="ghost-button" type="button" onClick={() => openProjectFile(matchesFile)}>
            Open JSON
          </button>
          {matchesFolder && (
            <button className="ghost-button" type="button" onClick={() => openProjectFolder(matchesFolder)}>
              Open folder
            </button>
          )}
        </div>
      )}

      <div className="postprocess-timeline">
        {mediaEntries.length > 0 && (
          <div className="cue-legend">
            {CUE_LEGEND.map((item) => (
              <div key={item.key} className="cue-legend__item">
                <span className={`cue-dot cue-dot--${item.key}`} />
                <div>
                  <strong>{item.label}</strong>
                  <small>{item.description}</small>
                </div>
              </div>
            ))}
          </div>
        )}
        {mediaEntries.length === 0 && <p className="empty-state">No footage analyzed yet.</p>}
        {mediaEntries.map((entry) => {
          const duration = entry.duration_s || 1
          return (
            <div className="timeline-row" key={entry.file}>
              <div className="timeline-header">
                <strong>{entry.relative_path}</strong>
                <span>{formatDuration(entry.duration_s)}</span>
              </div>
              <div className="timeline-bar">
                {entry.segments.map((segment) => {
                  const startPct = toPercentage(((segment.start_time_s ?? 0) / duration) * 100)
                  const durationPct = segment.duration_s
                    ? toPercentage((segment.duration_s / duration) * 100)
                    : 2
                  return (
                    <span
                      key={`${entry.file}-${segment.index}`}
                      className={`timeline-block${segment.edge_case ? ' timeline-block--warn' : ''}`}
                      style={{
                        left: `${startPct}%`,
                        width: `${Math.max(durationPct, 1)}%`,
                      }}
                      title={`Segment ${segment.index}: ${formatDuration(segment.start_time_s)} → ${
                        segment.end_time_s ? formatDuration(segment.end_time_s) : '—'
                      }`}
                    />
                  )
                })}
              </div>
              <div className="timeline-meta">
                <span>{entry.segments.length} segment(s)</span>
                <span>
                  {entry.track_names?.length
                    ? entry.track_names.join(', ')
                    : entry.cue_refs_used.join(', ') || 'No cues detected'}
                </span>
              </div>
              <div className="timeline-cue-status">
                <CueStatus label="Start" summary={entry.cue_detection?.start} />
                <CueStatus label="End" summary={entry.cue_detection?.end} />
              </div>
            </div>
          )
        })}
      </div>

      {topFiles.length > 0 && (
        <div className="postprocess-card">
          <h3>Top matches</h3>
          <table className="postprocess-table">
            <thead>
              <tr>
                <th>File</th>
                <th>Segments</th>
                <th>Tracks</th>
                <th>Top score</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              {topFiles.map((entry) => (
                <tr key={entry.file}>
                  <td>{entry.relative_path}</td>
                  <td>{entry.segments.length}</td>
                  <td>{entry.track_names?.join(', ') || '—'}</td>
                  <td>{entry.top_score ? entry.top_score.toFixed(3) : '—'}</td>
                  <td>{formatDuration(entry.duration_s)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
