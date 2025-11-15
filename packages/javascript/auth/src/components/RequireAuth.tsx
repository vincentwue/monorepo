import type { JSX } from "react"
import { useSession } from "./useSession"

export interface RequireAuthProps {
    children: JSX.Element
    redirectTo?: string
    loadingFallback?: JSX.Element
}

/**
 * RequireAuth
 *
 * - While loading: shows a small fallback.
 * - If unauthenticated: does a full-page redirect (window.location.href)
 *   to `redirectTo` (which can be absolute, e.g. http://localhost:5173/..., or
 *   a path like "/login").
 * - If authenticated: renders children.
 *
 * NOTE: We intentionally do NOT use React Router's <Navigate> here to avoid
 * cross-origin history.replaceState issues when redirecting to the auth-ui
 * (different port / origin).
 */
export const RequireAuth = ({
    children,
    redirectTo = "/login",
    loadingFallback,
    skipRedirect = false,
}: RequireAuthProps) => {
    const { session, loading } = useSession()

    if (loading) {
        return loadingFallback ?? <p>Checking session...</p>
    }

    if (!session && !skipRedirect) {
        const target = redirectTo ?? "/login"

        let finalUrl: string

        if (/^https?:\/\//i.test(target)) {
            // Absolute URL (can be different origin, e.g. auth-ui on 5173)
            finalUrl = target
        } else if (target.startsWith("/")) {
            // Path on the current origin
            finalUrl = `${window.location.origin}${target}`
        } else {
            // Relative segment, normalize to "/segment"
            finalUrl = `${window.location.origin}/${target}`
        }


        window.location.href = finalUrl
        return null
    }

    return children
}
