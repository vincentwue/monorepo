// apps/ableton_video_sync/src/align/AlignFootagePanel.tsx

import { useEffect, useState } from 'react'
import { fetchAlignState, runFootageAlignment } from '../lib/alignApi'
import { openProjectFile, openProjectFolder } from '../lib/systemApi'
import type { AlignFootageResult, AlignSegmentResult } from '../lib/types'

type AlignFootagePanelProps = {
  activeProjectPath: string | null
}

const formatSeconds = (value?: number | null) =>
  typeof value === 'number' && Number.isFinite(value)
    ? `${value.toFixed(2)}s`
    : '—'

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
        if (!cancelled) setLoadingState(false)
      })

    return () => {
      cancelled = true
    }
  }, [activeProjectPath])

  const handleRun = async () => {
    if (!activeProjectPath) return

    setRunning(true)
    setError(null)
    setMessage(null)

    try {
      const payload = await runFootageAlignment(activeProjectPath, audioPath)
      setResult(payload)
      setMessage(`Aligned ${payload.segments_aligned} segment(s).`)
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
            Aligns each detected <strong>segment</strong> to the master audio. Produces one aligned output per
            detected take.
          </p>
        </div>
        <button className="ghost-button" type="button" onClick={handleRun} disabled={running}>
          {running ? 'Aligning…' : 'Align footage'}
        </button>
      </div>

      <div className="align-form">
        <label htmlFor="align-audio-path">
          Audio file override (optional)
          <small>Leave empty to use the track in footage/music.</small>
        </label>
        <input
          id="align-audio-path"
          type="text"
          value={audioPath}
          onChange={(event) => setAudioPath(event.target.value)}
          placeholder="D:\\path\\to\\mixdown.wav"
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
              <span>Segments aligned</span>
              <strong>{result.segments_aligned}</strong>
            </div>

            <div className="status-card">
              <span>Output folder</span>
              <button className="ghost-button" type="button" onClick={openOutputDirectory}>
                Open folder
              </button>
            </div>
          </div>

          {/* MAIN TABLE */}
          <table className="recordings-table">
            <thead>
              <tr>
                <th>Video</th>
                <th>Segment</th>
                <th>Take ID</th>
                <th>Tracks</th>
                <th>Duration</th>
                <th>Output</th>
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {result.results.map((seg: AlignSegmentResult) => (
                <tr key={seg.output_path}>
                  <td>{seg.source_video}</td>
                  <td>#{seg.segment_index}</td>

                  <td>{seg.recording_id || '—'}</td>

                  <td>{seg.track_names?.join(', ') || '—'}</td>

                  <td>{formatSeconds(seg.segment_duration_s)}</td>

                  <td>{seg.output_path}</td>

                  <td>
                    <button
                      className="ghost-button"
                      type="button"
                      onClick={() => openProjectFile(seg.output_path)}
                    >
                      Open file
                    </button>
                  </td>
                </tr>
              ))}

              {result.results.length === 0 && (
                <tr>
                  <td colSpan={7}>
                    <p className="empty-state">No segments aligned. Check postprocess + primary cues.</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          {/* DEBUG */}
          {result.debug?.length > 0 && (
            <div className="align-debug">
              <h4>Debug details</h4>
              <pre>{JSON.stringify(result.debug, null, 2)}</pre>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
