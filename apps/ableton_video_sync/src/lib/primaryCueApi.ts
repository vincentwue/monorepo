import { INGEST_API_BASE_URL } from '../config/constants'

export type PrimaryCueHit = {
  time_s: number
  score: number
  ref_id?: string
}

export type PrimaryCuePair = {
  index: number
  status: 'complete' | 'missing_start' | 'missing_end'
  start_anchor?: PrimaryCueHit | null
  start_secondary_hits?: PrimaryCueHit[]
  end_anchor?: PrimaryCueHit | null
  end_secondary_hits?: PrimaryCueHit[]
  window_start_s: number
  window_end_s?: number | null
}

export type PrimaryCueMediaEntry = {
  file: string
  relative_path: string
  duration_s: number | null
  start_hits: PrimaryCueHit[]
  end_hits: PrimaryCueHit[]
  pairs: PrimaryCuePair[]
  elapsed_s?: number
  notes: string[]
}

export type PrimaryCueSummary = {
  files_processed: number
  pairs_detected: number
  complete_pairs: number
  missing_start: number
  missing_end: number
  errors: string[]
}

export type PrimaryCueResults = {
  project_path: string
  generated_at: string | null
  media: PrimaryCueMediaEntry[]
  summary: PrimaryCueSummary
  settings?: {
    threshold: number
    min_gap_s: number
  }
}

export type PrimaryCueJob = {
  status: string
  started_at?: string | null
  completed_at?: string | null
  progress?: {
    processed: number
    total: number
  }
  error?: string | null
}

export type PrimaryCueState = {
  project_path: string
  job?: PrimaryCueJob | null
  results: PrimaryCueResults
}

export type PrimaryCueRunOptions = {
  threshold?: number
  minGapSeconds?: number
  files?: string[]
}

const API_BASE = INGEST_API_BASE_URL.replace(/\/+$/, '')

async function handle<T>(response: Response): Promise<T> {
  const contentType = response.headers.get('content-type') || ''
  if (!response.ok) {
    if (contentType.includes('application/json')) {
      const payload = await response.json()
      const message =
        typeof payload?.detail === 'string'
          ? payload.detail
          : JSON.stringify(payload, null, 2)
      throw new Error(message || 'Primary cue request failed.')
    }
    throw new Error((await response.text()) || 'Primary cue request failed.')
  }
  if (contentType.includes('application/json')) {
    return (await response.json()) as T
  }
  return undefined as T
}

export function fetchPrimaryCueState(projectPath: string): Promise<PrimaryCueState> {
  if (!projectPath) {
    return Promise.reject(new Error('Select an active project first.'))
  }
  const url = `${API_BASE}/primary-cues/state?project_path=${encodeURIComponent(projectPath)}`
  return fetch(url).then(handle)
}

export function runPrimaryCueDetection(projectPath: string, options?: PrimaryCueRunOptions): Promise<PrimaryCueJob> {
  if (!projectPath) {
    return Promise.reject(new Error('Select an active project first.'))
  }
  const payload: Record<string, unknown> = { project_path: projectPath }
  if (typeof options?.threshold === 'number' && Number.isFinite(options.threshold)) {
    payload.threshold = options.threshold
  }
  if (typeof options?.minGapSeconds === 'number' && Number.isFinite(options.minGapSeconds)) {
    payload.min_gap_s = options.minGapSeconds
  }
  if (Array.isArray(options?.files) && options!.files.length > 0) {
    payload.files = options!.files
  }
  return fetch(`${API_BASE}/primary-cues/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then(handle)
}

export function resetPrimaryCueDetection(projectPath: string): Promise<PrimaryCueState> {
  if (!projectPath) {
    return Promise.reject(new Error('Select an active project first.'))
  }
  return fetch(`${API_BASE}/primary-cues/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_path: projectPath }),
  }).then(handle)
}
