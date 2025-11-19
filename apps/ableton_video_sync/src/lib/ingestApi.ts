import { INGEST_API_BASE_URL } from '../config/constants'

export type IngestDevice = {
  id: string
  name: string
  kind: 'filesystem' | 'adb'
  path: string
  adb_serial?: string | null
  created_at?: string
  last_ingested_at?: string | null
}

export type IngestRunStatus = 'pending' | 'running' | 'completed' | 'failed'

export type IngestRun = {
  id: string
  project_path: string
  device_ids: string[]
  status: IngestRunStatus
  copied_files: string[]
  error?: string | null
  started_at: string
  completed_at?: string | null
  only_today?: boolean
}

export type IngestState = {
  devices: IngestDevice[]
  runs: IngestRun[]
}

export type IngestPreviewCounts = Record<
  string,
  {
    total: number
    new: number
  }
>

export type DiscoveredDevice = {
  id: string
  kind: string
  label: string
  path?: string | null
  serial?: string | null
  connection_state?: string
  status_text?: string
  hints?: string[]
}

export type DeviceDirectoryEntry = {
  path: string
  name: string
  hasChildren: boolean
}

export type DeviceDirectoryListing = {
  serial?: string
  path: string | null
  parent: string | null
  entries: DeviceDirectoryEntry[]
}

const sanitizeBaseUrl = (value: string) => value.replace(/\/+$/, '')

const API_BASE = sanitizeBaseUrl(INGEST_API_BASE_URL)

const defaultHeaders = {
  'Content-Type': 'application/json',
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const target = `${API_BASE}${path}`
  try {
    const response = await fetch(target, {
      ...options,
      headers: {
        ...(options.headers || {}),
      },
    })

    const contentType = response.headers.get('content-type') || ''

    if (!response.ok) {
      if (contentType.includes('application/json')) {
        const payload = await response.json()
        const message =
          typeof payload?.detail === 'string'
            ? payload.detail
            : JSON.stringify(payload, null, 2)
        throw new Error(message || `Request to ${path} failed with ${response.statusText}`)
      }

      const message = await response.text()
      throw new Error(message || `Request to ${path} failed with ${response.statusText}`)
    }

    if (response.status === 204) {
      return undefined as T
    }

    if (contentType.includes('application/json')) {
      return (await response.json()) as T
    }

    return undefined as T
  } catch (error) {
    if (error instanceof Error) {
      throw error
    }
    throw new Error(`Unable to reach ingest server at ${target}`)
  }
}

export function fetchIngestState(): Promise<IngestState> {
  return request<IngestState>('/ingest/state')
}

export function fetchDiscoveredDevices(): Promise<DiscoveredDevice[]> {
  return request<DiscoveredDevice[]>('/ingest/discovery')
}

export function browseDiscoveredDirectories(serial: string, path?: string | null): Promise<DeviceDirectoryListing> {
  const safeSerial = encodeURIComponent(serial)
  const query = path && path.trim().length > 0 ? `?path=${encodeURIComponent(path.trim())}` : ''
  return request<DeviceDirectoryListing>(`/ingest/discovery/${safeSerial}/directories${query}`)
}

export function createIngestDevice(payload: {
  name: string
  path: string
  kind?: string
  adb_serial?: string | null
}): Promise<IngestDevice> {
  return request<IngestDevice>('/ingest/devices', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: defaultHeaders,
  })
}

export function deleteIngestDevice(deviceId: string) {
  return request<{ status: string }>(`/ingest/devices/${deviceId}`, {
    method: 'DELETE',
  })
}

export function startIngestRun(payload: {
  project_path: string
  device_ids: string[]
  only_today?: boolean
}): Promise<IngestRun> {
  return request<IngestRun>('/ingest/runs', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: defaultHeaders,
  })
}

export function previewIngestCounts(payload: {
  project_path: string
  device_ids: string[]
  only_today?: boolean
}): Promise<{ counts: IngestPreviewCounts }> {
  return request<{ counts: IngestPreviewCounts }>('/ingest/preview', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: defaultHeaders,
  })
}

export function abortIngestRun(runId: string) {
  return request<{ status: string }>(`/ingest/runs/${runId}/abort`, {
    method: 'POST',
  })
}
