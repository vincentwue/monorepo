import { useEffect, useState } from "react"
import { LayoutShell } from "../components/LayoutShell"

interface OryErrorPayload {
    id: string
    error?: {
        message?: string
        reason?: string
        status?: string
    }
    [key: string]: unknown
}

const sanitizeBaseUrl = (url: string) => url.replace(/\/$/, "")

export const ErrorPage = () => {
    const search = new URLSearchParams(window.location.search)
    const errorId = search.get("id")
    const [payload, setPayload] = useState<OryErrorPayload | null>(null)
    const [loading, setLoading] = useState(Boolean(errorId))
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        if (!errorId) {
            setError("Missing error ID in URL.")
            setLoading(false)
            return
        }

        const base = sanitizeBaseUrl(import.meta.env.VITE_ORY_BROWSER_URL ?? "http://localhost:4433")

        const url = new URL(`${base}/self-service/errors`)
        url.searchParams.set("id", errorId)

        fetch(url.toString(), { credentials: "include" })
            .then(async (response) => {
                if (!response.ok) throw new Error(`Request failed: ${response.status}`)
                return (await response.json()) as OryErrorPayload
            })
            .then((data) => setPayload(data))
            .catch((err: unknown) => {
                console.error("Failed to fetch Ory error", err)
                setError("Unable to load error details.")
            })
            .finally(() => setLoading(false))
    }, [errorId])

    return (
        <LayoutShell>
            <div className="panel">
                <h1>Something went wrong</h1>
                {loading && <p>Loading error details...</p>}
                {!loading && error && <p className="error">{error}</p>}
                {!loading && !error && payload && (
                    <>
                        <p>Ory error ID: {payload.id}</p>
                        {payload.error?.message && <p>{payload.error.message}</p>}
                        <pre>{JSON.stringify(payload, null, 2)}</pre>
                    </>
                )}
                <a className="cta-link" href="/login">
                    Back to login
                </a>
            </div>
        </LayoutShell>
    )
}
