import { useEffect, useState } from 'react'
import { fetchAlignState, runFootageAlignment, type AlignFootageResult } from '../lib/alignApi'
import { openProjectFile, openProjectFolder } from '../lib/systemApi'

type AlignFootagePanelProps = {
  activeProjectPath: string | null
}

const formatSeconds = (value?: number | null) =>
  typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(2)}s` : '—'

export function AlignFootagePanel({ activeProjectPath }: AlignFootagePanelProps) {
  const [audioPath, setAudioPath] = useState('')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [result, setResult] = useState<AlignFootageResult | null>(null)
  const [loadingState, setLoadingState] = useState(false)

  useEffect(() => {
    if (!activeProjectPath) {
      setResult(null)
      return
    }
    let cancelled = false
    setLoadingState(true)
    fetchAlignState(activeProjectPath)
      .then((payload) => {
        if (!cancelled) {
          setResult(payload)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error(err)
          setError(err instanceof Error ? err.message : 'Failed to load alignment state.')
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingState(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [activeProjectPath])

  const handleRun = async () => {
    if (!activeProjectPath) {
      return
    }
    setRunning(true)
    setError(null)
    setMessage(null)
    try {
      const payload = await runFootageAlignment(activeProjectPath, audioPath)
      setResult(payload)
      setMessage(`Aligned ${payload.videos_processed} clip(s).`)
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Failed to align footage.')
    } finally {
      setRunning(false)
    }
  }

  if (!activeProjectPath) {
    return (
      <section className="placeholder-panel">
        <h2>Align footage</h2>
        <p>Select or create a project first.</p>
      </section>
    )
  }

  const openOutputDirectory = () => {
    if (result?.output_dir) {
      openProjectFolder(result.output_dir)
    }
  }

  return (
    <section className="ingest-panel">
      <div className="panel-header">
        <div>
          <h2>Align footage</h2>
          <p>
            Trim every clip to the master audio length and pad with black where necessary. Each output contains the
            master audio so the files can be dropped into Resolve or any NLE.
          </p>
        </div>
        <button className="ghost-button" type="button" onClick={handleRun} disabled={running}>
          {running ? 'Aligning…' : 'Align footage'}
        </button>
      </div>

      <div className="align-form">
        <label htmlFor="align-audio-path">
          Audio file override (optional)
          <small>Leave empty to use the first clip from footage/music.</small>
        </label>
        <input
          id="align-audio-path"
          type="text"
          value={audioPath}
          onChange={(event) => setAudioPath(event.target.value)}
          placeholder="D:\path\to\mixdown.wav"
          disabled={running}
        />
      </div>

      {error && <p className="inline-message inline-message--error">{error}</p>}
      {message && !error && <p className="inline-message">{message}</p>}

      {loadingState && !running && <p className="inline-message">Loading last alignment…</p>}

      {result && (
        <div className="align-results">
          <div className="status-card-grid">
            <div className="status-card">
              <span>Audio source</span>
              <strong>{result.audio_path || '—'}</strong>
            </div>
            <div className="status-card">
              <span>Audio duration</span>
              <strong>{formatSeconds(result.audio_duration)}</strong>
            </div>
            <div className="status-card">
              <span>Clips processed</span>
              <strong>{result.videos_processed}</strong>
            </div>
            <div className="status-card">
              <span>Output folder</span>
              <button className="ghost-button" type="button" onClick={openOutputDirectory}>
                Open folder
              </button>
            </div>
          </div>

          <table className="recordings-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Aligned clip</th>
                <th>Trim start</th>
                <th>Pad start</th>
                <th>Padded tail</th>
                <th>Used duration</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {result.results.map((entry) => (
                <tr key={entry.output}>
                  <td>{entry.source}</td>
                  <td>{entry.output}</td>
                  <td>{formatSeconds(entry.trim_start)}</td>
                  <td>{formatSeconds(entry.pad_start)}</td>
                  <td>{formatSeconds(entry.pad_end)}</td>
                  <td>{formatSeconds(entry.used_duration)}</td>
                  <td>
                    <button className="ghost-button" type="button" onClick={() => openProjectFile(entry.output)}>
                      Open file
                    </button>
                  </td>
                </tr>
              ))}
              {result.results.length === 0 && (
                <tr>
                  <td colSpan={7}>
                    <p className="empty-state">No clips were aligned. Check postprocess results first.</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          {result.debug && result.debug.length > 0 && (
            <div className="align-debug">
              <h4>Alignment details</h4>
              <table className="recordings-table">
                <thead>
                  <tr>
                    <th>File</th>
                    <th>Video cue (s)</th>
                    <th>Audio cue (s)</th>
                    <th>Video abs (s)</th>
                    <th>Audio abs (s)</th>
                    <th>Absolute delta (s)</th>
                    <th>Relative delta (s)</th>
                    <th>Combined offset (s)</th>
                    <th>Trim start (s)</th>
                    <th>Pad start (s)</th>
                    <th>Pad end (s)</th>
                    <th>Video length (s)</th>
                  </tr>
                </thead>
                <tbody>
                  {result.debug.map((row, index) => (
                    <tr key={`debug-${index}-${row.file}`}>
                      <td>{row.file}</td>
                      <td>{formatSeconds(row.video_cue)}</td>
                      <td>{formatSeconds(row.audio_cue)}</td>
                      <td>{formatSeconds(row.video_abs)}</td>
                      <td>{formatSeconds(row.audio_abs)}</td>
                      <td>{formatSeconds(row.absolute_component)}</td>
                      <td>{formatSeconds(row.relative_component)}</td>
                      <td>{formatSeconds(row.relative_offset)}</td>
                      <td>{formatSeconds(row.trim_start)}</td>
                      <td>{formatSeconds(row.pad_start)}</td>
                      <td>{formatSeconds(row.pad_end)}</td>
                      <td>{formatSeconds(row.video_duration)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
