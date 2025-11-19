import { INGEST_API_BASE_URL } from '../config/constants'

export type PostprocessSegment = {
  index: number
  start_time_s: number
  end_time_s?: number | null
  duration_s?: number | null
  edge_case?: string | null
}

export type PostprocessHit = {
  time_s: number
  score: number
  ref_id: string
  track_names?: string[]
  cue_tier?: 'primary' | 'secondary'
}

export type CueDetectionSummary = {
  primary: boolean
  secondary: boolean
}

export type PostprocessMediaEntry = {
  file: string
  relative_path: string
  duration_s: number | null
  segments: PostprocessSegment[]
  cue_refs_used: string[]
  start_hits: PostprocessHit[]
  end_hits: PostprocessHit[]
  notes: string[]
  media_type?: string
  top_score?: number | null
  elapsed_s?: number
  track_names?: string[]
  cue_detection?: {
    start: CueDetectionSummary
    end: CueDetectionSummary
  }
}

export type PostprocessSummary = {
  files_processed: number
  segments_detected: number
  cue_refs_used: string[]
  errors: string[]
}

export type PostprocessSettings = {
  threshold: number
  min_gap_s: number
}

export type PostprocessResults = {
  project_path: string
  generated_at: string | null
  media: PostprocessMediaEntry[]
  summary: PostprocessSummary
  settings?: PostprocessSettings
}

export type PostprocessJob = {
  status: string
  started_at?: string | null
  completed_at?: string | null
  progress?: {
    processed: number
    total: number
  }
  error?: string | null
}

export type PostprocessState = {
  project_path: string
  job?: PostprocessJob | null
  results: PostprocessResults
}

export type PostprocessRunOptions = {
  threshold?: number
  minGapSeconds?: number
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
      throw new Error(message || 'Postprocess request failed.')
    }
    throw new Error((await response.text()) || 'Postprocess request failed.')
  }
  if (contentType.includes('application/json')) {
    return (await response.json()) as T
  }
  return undefined as T
}

export function fetchPostprocessState(projectPath: string): Promise<PostprocessState> {
  if (!projectPath) {
    return Promise.reject(new Error('Select an active project first.'))
  }
  const url = `${API_BASE}/postprocess/state?project_path=${encodeURIComponent(projectPath)}`
  return fetch(url).then(handle)
}

export function runPostprocess(projectPath: string, options?: PostprocessRunOptions): Promise<PostprocessJob> {
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
  return fetch(`${API_BASE}/postprocess/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then(handle)
}
