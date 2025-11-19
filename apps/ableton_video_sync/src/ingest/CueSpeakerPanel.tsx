import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from 'react'
import {
  fetchCueSpeakerState,
  selectCueSpeaker,
  updateCueSpeakerVolume,
  playCueSpeakerTest,
  type CueSpeakerDevice,
  type CueSpeakerState,
} from '../lib/cueSpeakerApi'

export function CueSpeakerPanel() {
  const [state, setState] = useState<CueSpeakerState | null>(null)
  const [loading, setLoading] = useState(false)
  const [savingSelection, setSavingSelection] = useState(false)
  const [updatingVolume, setUpdatingVolume] = useState(false)
  const [testingCue, setTestingCue] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const loadState = useCallback(async () => {
    setLoading(true)
    try {
      const response = await fetchCueSpeakerState()
      setState(response)
      setError(null)
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Unable to read cue speaker state.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadState()
  }, [loadState])

  const handleSelectDevice = async (deviceIndex: number | null) => {
    setSavingSelection(true)
    setMessage(null)
    try {
      const response = await selectCueSpeaker(deviceIndex)
      setState(response)
      setMessage('Cue speaker updated.')
      setError(null)
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Unable to save cue speaker selection.')
    } finally {
      setSavingSelection(false)
    }
  }

  const handleVolumeChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const sliderValue = Number(event.target.value)
    const normalized = sliderValue / 100
    setState((prev) => (prev ? { ...prev, volume: normalized } : prev))
    setUpdatingVolume(true)
    setMessage(null)
    try {
      const response = await updateCueSpeakerVolume(normalized)
      setState(response)
      setMessage('Volume saved.')
      setError(null)
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Unable to update volume.')
    } finally {
      setUpdatingVolume(false)
    }
  }

  const handlePlayTest = async () => {
    setTestingCue(true)
    setMessage(null)
    try {
      await playCueSpeakerTest(state?.selected_device_index ?? undefined, state?.volume)
      setMessage('Playing cue...')
      setError(null)
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Unable to play cue.')
    } finally {
      setTestingCue(false)
    }
  }

  const recommendedDevice: CueSpeakerDevice | undefined = useMemo(() => {
    if (!state?.outputs?.length || state.recommended_device_index == null) {
      return undefined
    }
    return state.outputs.find((device) => device.index === state.recommended_device_index)
  }, [state])

  const sliderValue = Math.round(Math.min(200, Math.max(0, (state?.volume ?? 1) * 100)))

  return (
    <section className="ingest-panel cue-speaker-panel">
      <div className="panel-header">
        <div>
          <h2>Cue speaker</h2>
          <p>
            Pick the monitor or headphone output Ableton should use for cue beeps and aim for a level the show
            cameras capture as loudly as possible.
          </p>
        </div>
        <button className="ghost-button" type="button" onClick={loadState} disabled={loading}>
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {error && <p className="inline-message inline-message--error">{error}</p>}
      {message && !error && <p className="inline-message">{message}</p>}
      {!error && state?.warning && <p className="inline-message inline-message--warning">{state.warning}</p>}

      {recommendedDevice && (
        <div className="cue-speaker-recommendation">
          <div>
            <p>Recommended output</p>
            <strong>{recommendedDevice.name}</strong>
            <span>
              {recommendedDevice.hostapi} · {recommendedDevice.channels}ch
            </span>
          </div>
          <button
            type="button"
            className="ghost-button"
            onClick={() => handleSelectDevice(recommendedDevice.index)}
            disabled={savingSelection || state?.selected_device_index === recommendedDevice.index}
          >
            Use recommended
          </button>
        </div>
      )}

      <div className="cue-device-list">
        {loading ? (
          <p className="empty-state">Loading outputs...</p>
        ) : state?.outputs?.length ? (
          state.outputs.map((device) => {
            const selected = state.selected_device_index === device.index
            const isRecommended = device.index === state.recommended_device_index
            return (
              <label
                key={device.index}
                className={`cue-device-card${selected ? ' cue-device-card--selected' : ''}`}
              >
                <input
                  type="radio"
                  name="cue-speaker"
                  value={device.index}
                  checked={selected}
                  onChange={() => handleSelectDevice(device.index)}
                  disabled={savingSelection}
                />
                <div className="cue-device-card__body">
                  <div className="cue-device-card__title">
                    <span>{device.name}</span>
                    {isRecommended && <span className="cue-device-badge">Recommended</span>}
                    {selected && <span className="cue-device-badge cue-device-badge--active">Selected</span>}
                  </div>
                  <p className="cue-device-meta">
                    {device.hostapi} · {device.channels} channels
                  </p>
                </div>
              </label>
            )
          })
        ) : (
          <p className="empty-state">No audio outputs were detected.</p>
        )}
      </div>

      <div className="cue-speaker-controls">
        <label className="cue-volume-slider">
          <span>Master cue volume ({sliderValue}%)</span>
          <input
            type="range"
            min={0}
            max={200}
            step={5}
            value={sliderValue}
            onChange={handleVolumeChange}
            disabled={updatingVolume || !state}
          />
        </label>
        <div className="cue-speaker-actions">
          <button
            className="ghost-button"
            type="button"
            onClick={() => handleSelectDevice(null)}
            disabled={savingSelection || state?.selected_device_index == null}
          >
            Use system default
          </button>
          <button
            className="primary-button"
            type="button"
            onClick={handlePlayTest}
            disabled={!state || testingCue}
          >
            {testingCue ? 'Playing...' : 'Play test cue'}
          </button>
        </div>
      </div>
    </section>
  )
}
