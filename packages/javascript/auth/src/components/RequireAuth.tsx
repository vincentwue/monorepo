import type { JSX } from "react"
import { useSession } from "./useSession"

export interface RequireAuthProps {
    children: JSX.Element
    redirectTo?: string
    loadingFallback?: JSX.Element
    skipRedirect?: boolean

    /**
     * If true, do not redirect when unauthenticated.
     * Instead, render nothing (unless `unauthenticatedFallback` is provided).
     */
    hideIfUnauthenticated?: boolean

    /**
     * If provided, this element is rendered when the user is NOT authenticated.
     * This takes precedence over `hideIfUnauthenticated` and `skipRedirect`.
     */
    unauthenticatedFallback?: JSX.Element
}

/**
 * RequireAuth
 *
 * - Loading: renders fallback.
 * - Unauthenticated:
 *     - If `unauthenticatedFallback` provided: renders that.
 *     - Else if `hideIfUnauthenticated` or `skipRedirect`: returns null.
 *     - Else: redirects to `redirectTo`.
 * - Authenticated: renders children.
 */
export const RequireAuth = ({
    children,
    redirectTo = "/login",
    loadingFallback,
    skipRedirect = false,
    hideIfUnauthenticated = false,
    unauthenticatedFallback,
}: RequireAuthProps) => {
    const { session, loading } = useSession()

    if (loading) {
        return loadingFallback ?? <p>Checking session...</p>
    }

    // --- not logged in ---
    
    if (!session) {
        // 1) Local-only / custom UI if provided
        if (unauthenticatedFallback) {
            return unauthenticatedFallback
        }

        // 2) Stay on page but hide content
        if (hideIfUnauthenticated || skipRedirect) {
            return null
        }

        // 3) Redirect to login
        const target = redirectTo ?? "/login"
        let finalUrl: string

        if (/^https?:\/\//i.test(target)) {
            finalUrl = target               // absolute URL
        } else if (target.startsWith("/")) {
            finalUrl = `${window.location.origin}${target}` // same origin path
        } else {
            finalUrl = `${window.location.origin}/${target}` // normalize
        }

        window.location.href = finalUrl
        return null
    }

    // --- logged in ---
    return children
}
