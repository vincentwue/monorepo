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

export const useSession = (): UseSessionResult => {
    const [session, setSession] = useState<OrySession | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<unknown | null>(null)

    useEffect(() => {
        let active = true

        const fetchSession = async () => {
            try {
                const baseUrl = getOryPublicApiBaseUrl()
                const response = await axios.get<OrySession>(`${baseUrl}/sessions/whoami`, {
                    withCredentials: true,
                })
                if (!active) return
                setSession(response.data)
                setError(null)
            } catch (err: unknown) {
                if (!active) return
                if (axios.isAxiosError(err) && (err.response?.status === 401 || err.response?.status === 403)) {
                    setSession(null)
                    setError(null)
                } else {
                    setSession(null)
                    setError(err)
                }
            } finally {
                if (active) {
                    setLoading(false)
                }
            }
        }

        fetchSession()

        return () => {
            active = false
        }
    }, [])

    return { session, loading, error }
}
