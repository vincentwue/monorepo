import { INGEST_API_BASE_URL } from '../config/constants'

export type CueSpeakerDevice = {
  index: number
  name: string
  hostapi: string
  channels: number
}

export type CueSpeakerState = {
  outputs: CueSpeakerDevice[]
  recommended_device_index: number | null
  selected_device_index: number | null
  volume: number
  warning?: string | null
}

const sanitizeBaseUrl = (value: string) => value.replace(/\/+$/, '')
const API_BASE = sanitizeBaseUrl(INGEST_API_BASE_URL)

const jsonHeaders = {
  'Content-Type': 'application/json',
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const target = `${API_BASE}${path}`
  const response = await fetch(target, options)
  const contentType = response.headers.get('content-type') || ''

  if (!response.ok) {
    if (contentType.includes('application/json')) {
      const payload = await response.json()
      const message =
        typeof payload?.detail === 'string'
          ? payload.detail
          : JSON.stringify(payload, null, 2)
      throw new Error(message || `Request to ${path} failed.`)
    }
    throw new Error((await response.text()) || `Request to ${path} failed.`)
  }

  if (response.status === 204) {
    return undefined as T
  }

  if (contentType.includes('application/json')) {
    return (await response.json()) as T
  }

  return undefined as T
}

export function fetchCueSpeakerState(): Promise<CueSpeakerState> {
  return request<CueSpeakerState>('/cue/speaker')
}

export function selectCueSpeaker(deviceIndex: number | null): Promise<CueSpeakerState> {
  return request<CueSpeakerState>('/cue/speaker/select', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ device_index: deviceIndex }),
  })
}

export function updateCueSpeakerVolume(volume: number): Promise<CueSpeakerState> {
  return request<CueSpeakerState>('/cue/speaker/volume', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ volume }),
  })
}

export function playCueSpeakerTest(deviceIndex?: number | null, volume?: number) {
  const payload: Record<string, number | null> = {}
  if (typeof deviceIndex === 'number') {
    payload.device_index = deviceIndex
  } else if (deviceIndex === null) {
    payload.device_index = null
  }
  if (typeof volume === 'number') {
    payload.volume = volume
  }
  return request<{ status: string }>('/cue/speaker/test', {
    method: 'POST',
    headers: jsonHeaders,
    body: Object.keys(payload).length > 0 ? JSON.stringify(payload) : '{}',
  })
}
