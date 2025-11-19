import { INGEST_API_BASE_URL } from '../config/constants'

export type AbletonConnectionStatus = {
  connected: boolean
  project_saved: boolean
  project_path: string | null
  project_name: string | null
  is_playing?: boolean | null
  tempo?: number | null
  warning?: string | null
  error?: string | null
  timestamp?: string
  reconnecting?: boolean
}

export type AbletonReconnectResponse = {
  started: boolean
  already_running: boolean
  reconnecting: boolean
  error?: string | null
  status: AbletonConnectionStatus
}

const API_BASE = INGEST_API_BASE_URL.replace(/\/+$/, '')

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, options)
  const contentType = response.headers.get('content-type') || ''
  if (!response.ok) {
    if (contentType.includes('application/json')) {
      const payload = await response.json()
      const detail = typeof payload?.detail === 'string' ? payload.detail : JSON.stringify(payload, null, 2)
      throw new Error(detail || `Request to ${path} failed.`)
    }
    throw new Error((await response.text()) || `Request to ${path} failed.`)
  }

  if (contentType.includes('application/json')) {
    return (await response.json()) as T
  }
  return undefined as T
}

export function fetchAbletonConnection(): Promise<AbletonConnectionStatus> {
  return request<AbletonConnectionStatus>('/ableton/connection')
}

export function triggerAbletonReconnect(): Promise<AbletonReconnectResponse> {
  return request<AbletonReconnectResponse>('/ableton/connection/reconnect', {
    method: 'POST',
  })
}
