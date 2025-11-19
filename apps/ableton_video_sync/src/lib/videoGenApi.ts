import { INGEST_API_BASE_URL } from '../config/constants'

export type VideoGenResponse = {
  project_name: string
  output_file?: string
  audio_path: string
  video_dir?: string
  bars_per_cut?: number | null
  cut_length_s?: number | null
  custom_duration_s?: number | null
}

const API_BASE = INGEST_API_BASE_URL.replace(/\/+$/, '')

const jsonHeaders = {
  'Content-Type': 'application/json',
}

async function handleResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get('content-type') || ''
  if (!response.ok) {
    if (contentType.includes('application/json')) {
      const payload = await response.json()
      const message =
        typeof payload?.detail === 'string' ? payload.detail : JSON.stringify(payload, null, 2)
      throw new Error(message || 'Video generation request failed.')
    }
    throw new Error((await response.text()) || 'Video generation request failed.')
  }
  if (contentType.includes('application/json')) {
    return (await response.json()) as T
  }
  return undefined as T
}

type SyncOptions = {
  audioPath?: string
  barsPerCut?: number
  cutLengthSeconds?: number
  customDurationSeconds?: number
  debug?: boolean
}

export function runSyncVideoGeneration(
  projectPath: string,
  options: SyncOptions = {},
): Promise<VideoGenResponse> {
  if (!projectPath) {
    return Promise.reject(new Error('Select an active project first.'))
  }
  return fetch(`${API_BASE}/video-gen/sync`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({
      project_path: projectPath,
      audio_path: options.audioPath?.trim() || undefined,
      bars_per_cut: options.barsPerCut ?? undefined,
      cut_length_s: options.cutLengthSeconds ?? undefined,
      custom_duration_s: options.customDurationSeconds ?? undefined,
      debug: options.debug ?? undefined,
    }),
  }).then(handleResponse)
}

type AutoOptions = {
  audioPath?: string
  videoDir?: string
  barsPerCut?: number
  customDurationSeconds?: number
}

export function runAutoBarGeneration(
  projectPath: string,
  options: AutoOptions = {},
): Promise<VideoGenResponse> {
  if (!projectPath) {
    return Promise.reject(new Error('Select an active project first.'))
  }
  return fetch(`${API_BASE}/video-gen/auto`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({
      project_path: projectPath,
      audio_path: options.audioPath?.trim() || undefined,
      video_dir: options.videoDir?.trim() || undefined,
      bars_per_cut: options.barsPerCut ?? undefined,
      custom_duration_s: options.customDurationSeconds ?? undefined,
    }),
  }).then(handleResponse)
}
