import { useState } from 'react'
import { runAutoBarGeneration, runSyncVideoGeneration, type VideoGenResponse } from '../lib/videoGenApi'
import { openProjectFile, openProjectFolder } from '../lib/systemApi'

type VideoGeneratorPanelProps = {
  activeProjectPath: string | null
}

export function VideoGeneratorPanel({ activeProjectPath }: VideoGeneratorPanelProps) {
  const [audioPathOverride, setAudioPathOverride] = useState('')
  const [videoDirOverride, setVideoDirOverride] = useState('')
  const [barsPerCut, setBarsPerCut] = useState('')
  const [cutLength, setCutLength] = useState('')
  const [customDuration, setCustomDuration] = useState('')
  const [syncResult, setSyncResult] = useState<VideoGenResponse | null>(null)
  const [autoResult, setAutoResult] = useState<VideoGenResponse | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [syncLoading, setSyncLoading] = useState(false)
  const [autoLoading, setAutoLoading] = useState(false)

  if (!activeProjectPath) {
    return (
      <section className="placeholder-panel">
        <h2>Video generator</h2>
        <p>Select or create a project first.</p>
      </section>
    )
  }

  const parseNumber = (value: string) => {
    if (!value.trim()) {
      return undefined
    }
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : undefined
  }

  const handleRunSync = async () => {
    setSyncLoading(true)
    setError(null)
    setMessage(null)
    try {
      const payload = await runSyncVideoGeneration(activeProjectPath, {
        audioPath: audioPathOverride,
        barsPerCut: parseNumber(barsPerCut),
        cutLengthSeconds: parseNumber(cutLength),
        customDurationSeconds: parseNumber(customDuration),
      })
      setSyncResult(payload)
      setMessage(`Created sync edit at ${payload.output_file ?? 'unknown location'}.`)
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Failed to generate sync edit.')
    } finally {
      setSyncLoading(false)
    }
  }

  const handleRunAuto = async () => {
    setAutoLoading(true)
    setError(null)
    setMessage(null)
    try {
      const payload = await runAutoBarGeneration(activeProjectPath, {
        audioPath: audioPathOverride,
        videoDir: videoDirOverride,
        barsPerCut: parseNumber(barsPerCut),
        customDurationSeconds: parseNumber(customDuration),
      })
      setAutoResult(payload)
      setMessage(`Created auto-bar edit at ${payload.output_file ?? 'unknown location'}.`)
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Failed to generate auto-bar edit.')
    } finally {
      setAutoLoading(false)
    }
  }

  const openOutput = (path?: string) => {
    if (path) {
      openProjectFile(path)
    }
  }

  const openOutputFolder = (path?: string) => {
    if (path) {
      openProjectFolder(path)
    }
  }

  return (
    <section className="ingest-panel">
      <div className="panel-header">
        <div>
          <h2>Video generator</h2>
          <p>Kick off BPM-aligned sync edits or quick auto-bar cuts using the detected cue metadata.</p>
        </div>
      </div>

      <div className="align-form">
        <label htmlFor="video-gen-audio-path">
          Audio file override (optional)
          <small>Leave empty to use the first clip from footage/music.</small>
        </label>
        <input
          id="video-gen-audio-path"
          type="text"
          value={audioPathOverride}
          onChange={(event) => setAudioPathOverride(event.target.value)}
          placeholder="D:\mixdowns\final.wav"
          disabled={syncLoading || autoLoading}
        />
      </div>

      <div className="align-form">
        <label htmlFor="video-gen-video-dir">
          Video directory override (optional)
          <small>Defaults to footage/videos.</small>
        </label>
        <input
          id="video-gen-video-dir"
          type="text"
          value={videoDirOverride}
          onChange={(event) => setVideoDirOverride(event.target.value)}
          placeholder="D:\project\alt_clips"
          disabled={syncLoading || autoLoading}
        />
      </div>

      <div className="align-form">
        <label htmlFor="video-gen-bars">
          Bars per cut
          <small>Optional override.</small>
        </label>
        <input
          id="video-gen-bars"
          type="number"
          min={1}
          value={barsPerCut}
          onChange={(event) => setBarsPerCut(event.target.value)}
          disabled={syncLoading || autoLoading}
        />
      </div>

      <div className="align-form">
        <label htmlFor="video-gen-cut-length">
          Cut length (seconds)
          <small>Optional fixed length for sync edits.</small>
        </label>
        <input
          id="video-gen-cut-length"
          type="number"
          min={0}
          step="0.1"
          value={cutLength}
          onChange={(event) => setCutLength(event.target.value)}
          disabled={syncLoading}
        />
      </div>

      <div className="align-form">
        <label htmlFor="video-gen-custom-duration">
          Custom duration (seconds)
          <small>Optional render length override.</small>
        </label>
        <input
          id="video-gen-custom-duration"
          type="number"
          min={0}
          step="0.1"
          value={customDuration}
          onChange={(event) => setCustomDuration(event.target.value)}
          disabled={syncLoading || autoLoading}
        />
      </div>

      {error && <p className="inline-message inline-message--error">{error}</p>}
      {message && !error && <p className="inline-message">{message}</p>}

      <div className="button-row">
        <button className="primary-button" type="button" onClick={handleRunSync} disabled={syncLoading}>
          {syncLoading ? 'Rendering sync edit…' : 'Render sync edit'}
        </button>
        <button className="ghost-button" type="button" onClick={handleRunAuto} disabled={autoLoading}>
          {autoLoading ? 'Rendering auto-bar…' : 'Render auto-bar edit'}
        </button>
      </div>

      {syncResult && (
        <div className="status-card-grid">
          <div className="status-card">
            <span>Sync output</span>
            <button className="ghost-button" type="button" onClick={() => openOutput(syncResult.output_file)}>
              Open file
            </button>
          </div>
          <div className="status-card">
            <span>Audio source</span>
            <strong>{syncResult.audio_path}</strong>
          </div>
        </div>
      )}

      {autoResult && (
        <div className="status-card-grid">
          <div className="status-card">
            <span>Auto-bar output</span>
            <button className="ghost-button" type="button" onClick={() => openOutput(autoResult.output_file)}>
              Open file
            </button>
          </div>
          <div className="status-card">
            <span>Source directory</span>
            <button className="ghost-button" type="button" onClick={() => openOutputFolder(autoResult.video_dir)}>
              Open folder
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
