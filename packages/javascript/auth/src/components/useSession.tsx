import { useEffect, useState } from "react"
import axios from "axios"
import { getOryPublicApiBaseUrl } from "../utils/ory"

export interface OrySession {
    id: string
    [key: string]: unknown
}

export interface UseSessionResult {
    session: OrySession | null
    loading: boolean
    error: unknown | null
}

interface SessionCache {
    value: OrySession | null | undefined
    error: unknown | null
    promise: Promise<void> | null
}

const localSessionCache: SessionCache = {
    value: undefined,
    error: null,
    promise: null,
}

const getSessionCache = (): SessionCache => {
    if (typeof window === "undefined") {
        return localSessionCache
    }
    const globalWindow = window as Window & { __orySessionCache?: SessionCache }
    if (!globalWindow.__orySessionCache) {
        globalWindow.__orySessionCache = { value: undefined, error: null, promise: null }
    }
    return globalWindow.__orySessionCache
}

const fetchSession = async (): Promise<void> => {
    const cache = getSessionCache()
    try {
        const baseUrl = getOryPublicApiBaseUrl()
        const response = await axios.get<OrySession>(`${baseUrl}/sessions/whoami`, {
            withCredentials: true,
        })
        cache.value = response.data
        cache.error = null
    } catch (err: unknown) {
        if (axios.isAxiosError(err) && (err.response?.status === 401 || err.response?.status === 403)) {
            cache.value = null
            cache.error = null
        } else {
            cache.value = null
            cache.error = err
        }
    }
}

const ensureSession = (): Promise<void> => {
    const cache = getSessionCache()
    if (!cache.promise) {
        cache.promise = fetchSession().finally(() => {
            cache.promise = null
        })
    }
    return cache.promise
}

export const useSession = (): UseSessionResult => {
    const cache = getSessionCache()
    const [session, setSession] = useState<OrySession | null>(cache.value ?? null)
    const [loading, setLoading] = useState(cache.value === undefined)
    const [error, setError] = useState<unknown | null>(cache.error)

    useEffect(() => {
        let active = true

        const syncFromCache = () => {
            const currentCache = getSessionCache()
            if (!active) return
            setSession(currentCache.value ?? null)
            setError(currentCache.error)
            setLoading(false)
        }

        const currentCache = getSessionCache()
        if (currentCache.promise) {
            currentCache.promise.finally(syncFromCache)
        } else if (currentCache.value === undefined) {
            ensureSession().finally(syncFromCache)
        } else {
            setLoading(false)
        }

        return () => {
            active = false
        }
    }, [])

    return { session, loading, error }
}
