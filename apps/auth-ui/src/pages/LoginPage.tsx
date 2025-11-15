import { Login, useSession } from "@monorepo/auth"
import { useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import { LayoutShell } from "../components/LayoutShell"

const DEFAULT_SUCCESS_REDIRECT =
    import.meta.env.VITE_AUTH_SUCCESS_REDIRECT ?? "http://localhost:5174/"

export const LoginPage = () => {
    const [searchParams] = useSearchParams()
    const { session, loading } = useSession()

    useEffect(() => {
        if (loading) return
        if (!session) return

        // 1) Try to use ?return_to= from the URL
        const returnTo = searchParams.get("return_to")

        if (returnTo) {
            try {
                const url = new URL(returnTo, window.location.origin)

                // Only allow safe origins (same origin or the main app at 5174)
                const allowedOrigins = [window.location.origin, "http://localhost:5174"]
                if (allowedOrigins.includes(url.origin)) {
                    window.location.href = url.toString()
                    return
                }
            } catch {
                // Invalid URL in return_to → ignore and fall back
            }
        }

        // 2) Fallback to env-based success redirect
        window.location.href = DEFAULT_SUCCESS_REDIRECT
    }, [session, loading, searchParams])

    return (
        <LayoutShell>
            <Login />
        </LayoutShell>
    )
}
