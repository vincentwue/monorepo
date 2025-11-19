import { INGEST_API_BASE_URL } from '../config/constants'

export type AlignResultEntry = {
  source: string
  output: string
  trim_start: number
  pad_start: number
  pad_end: number
  used_duration: number
}

export type AlignFootageResult = {
  project_path: string
  audio_path: string | null
  audio_duration: number | null
  output_dir: string
  videos_processed: number
  results: AlignResultEntry[]
  debug?: {
    file: string
    video_cue: number
    audio_cue: number
    video_abs?: number
    audio_abs?: number
  absolute_component?: number
  relative_component?: number
    relative_offset: number
    trim_start: number
    pad_start: number
    pad_end: number
    video_duration: number
  }[]
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
      throw new Error(message || 'Align request failed.')
    }
    throw new Error((await response.text()) || 'Align request failed.')
  }
  if (contentType.includes('application/json')) {
    return (await response.json()) as T
  }
  return undefined as T
}

export function runFootageAlignment(projectPath: string, audioPath?: string): Promise<AlignFootageResult> {
  if (!projectPath) {
    return Promise.reject(new Error('Select an active project first.'))
  }
  return fetch(`${API_BASE}/align/footage`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({
      project_path: projectPath,
      audio_path: audioPath?.trim() || undefined,
    }),
  }).then(handleResponse)
}

export function fetchAlignState(projectPath: string): Promise<AlignFootageResult> {
  if (!projectPath) {
    return Promise.reject(new Error('Select an active project first.'))
  }
  return fetch(`${API_BASE}/align/state?project_path=${encodeURIComponent(projectPath)}`).then(handleResponse)
}
