import { INGEST_API_BASE_URL } from '../config/constants'

export type RecordingEntry = Record<string, unknown> & {
  id?: string
  title?: string
  name?: string
  captured_at?: string
  created_at?: string
  time_start_recording?: number
  time_end_recording?: number
  duration_seconds?: number
}

export type RecordingState = {
  project_path: string
  cues_enabled: boolean
  capture_enabled: boolean
  cue_active: boolean
  recordings: RecordingEntry[]
  warning?: string
}

const sanitizeBaseUrl = (value: string) => value.replace(/\/+$/, '')

const API_BASE = sanitizeBaseUrl(INGEST_API_BASE_URL)

const jsonHeaders = {
  'Content-Type': 'application/json',
}

function withProjectQuery(projectPath: string) {
  const safe = encodeURIComponent(projectPath)
  return `${API_BASE}/recording/state?project_path=${safe}`
}

async function handleResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get('content-type') || ''
  if (!response.ok) {
    if (contentType.includes('application/json')) {
      const payload = await response.json()
      const message =
        typeof payload?.detail === 'string' ? payload.detail : JSON.stringify(payload, null, 2)
      throw new Error(message || 'Recording API request failed.')
    }
    throw new Error((await response.text()) || 'Recording API request failed.')
  }
  if (contentType.includes('application/json')) {
    return (await response.json()) as T
  }
  return undefined as T
}

export function fetchRecordingState(projectPath: string): Promise<RecordingState> {
  if (!projectPath) {
    return Promise.reject(new Error('Select an active project first.'))
  }
  const url = withProjectQuery(projectPath)
  return fetch(url).then(handleResponse)
}

export function updateRecordingState(projectPath: string, enabled: boolean) {
  if (!projectPath) {
    return Promise.reject(new Error('Select an active project first.'))
  }
  return fetch(`${API_BASE}/recording/state`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({
      project_path: projectPath,
      cues_enabled: enabled,
      capture_enabled: enabled,
    }),
  }).then(handleResponse)
}

export function triggerRecordingCue(projectPath: string, action: 'start' | 'stop') {
  if (!projectPath) {
    return Promise.reject(new Error('Select an active project first.'))
  }
  return fetch(`${API_BASE}/recording/cues`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({
      project_path: projectPath,
      action,
    }),
  }).then(handleResponse)
}

export function deleteRecording(projectPath: string, recordingId: string) {
  if (!projectPath) {
    return Promise.reject(new Error('Select an active project first.'))
  }
  if (!recordingId) {
    return Promise.reject(new Error('Recording id is required.'))
  }
  const projectSafe = encodeURIComponent(projectPath)
  const idSafe = encodeURIComponent(recordingId)
  const url = `${API_BASE}/recording/state/${idSafe}?project_path=${projectSafe}`
  return fetch(url, {
    method: 'DELETE',
    headers: jsonHeaders,
  }).then(handleResponse)
}
