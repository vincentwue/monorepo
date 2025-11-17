import { Registration, useSession } from "@monorepo/auth"
import { useEffect, useMemo } from "react"
import { useSearchParams } from "react-router-dom"
import { LayoutShell } from "../components/LayoutShell"

const DEFAULT_SUCCESS_REDIRECT = import.meta.env.VITE_AUTH_SUCCESS_REDIRECT ?? ""

export const RegistrationPage = () => {
    const [searchParams] = useSearchParams()
    const { session, loading } = useSession()

    const hasFlow = useMemo(() => searchParams.has("flow"), [searchParams])
    const hasReturnTo = useMemo(() => searchParams.has("return_to"), [searchParams])
    const returnTo = useMemo(() => searchParams.get("return_to"), [searchParams])

    useEffect(() => {
        if (loading || !session || !hasReturnTo) return
        if (!returnTo) return

        try {
            const targetUrl = new URL(returnTo, window.location.origin)

            const allowedOrigins = [window.location.origin]
            if (DEFAULT_SUCCESS_REDIRECT) {
                try {
                    const envOrigin = new URL(DEFAULT_SUCCESS_REDIRECT).origin
                    if (!allowedOrigins.includes(envOrigin)) {
                        allowedOrigins.push(envOrigin)
                    }
                } catch {
                    console.warn("Invalid VITE_AUTH_SUCCESS_REDIRECT value:", DEFAULT_SUCCESS_REDIRECT)
                }
            }

            if (!allowedOrigins.includes(targetUrl.origin)) {
                console.warn("Blocked return_to with disallowed origin:", targetUrl.origin)
                if (DEFAULT_SUCCESS_REDIRECT) {
                    window.location.href = DEFAULT_SUCCESS_REDIRECT
                }
                return
            }

            window.location.href = targetUrl.toString()
        } catch {
            console.warn("Invalid return_to URL, staying on registration portal.")
        }
    }, [session, loading, hasReturnTo, returnTo])

    const showPortal = !loading && !!session && !hasReturnTo
    const showRedirectNotice = !loading && !!session && hasReturnTo
    const showSessionCheck = loading && !hasFlow

    return (
        <LayoutShell>
            {showPortal ? (
                <div className="panel">
                    <h1>You're already registered</h1>
                    <p className="mt-2">
                        Your identity session is active. You can head to the app or sign out instead.
                    </p>

                    <pre className="mt-4">
                        {JSON.stringify((session as any).identity ?? session, null, 2)}
                    </pre>

                    <div className="mt-4 flex flex-wrap gap-3">
                        {DEFAULT_SUCCESS_REDIRECT && (
                            <a className="cta-link" href={DEFAULT_SUCCESS_REDIRECT}>
                                Go to main app
                            </a>
                        )}
                        <a className="cta-link" href="/logout">
                            Log out
                        </a>
                    </div>
                </div>
            ) : showRedirectNotice ? (
                <div className="panel">
                    <h1>Welcome back</h1>
                    <p className="mt-2">We found an active session. Redirecting you shortly...</p>
                </div>
            ) : showSessionCheck ? (
                <div className="panel">
                    <h1>Checking session...</h1>
                    <p className="mt-2">Hold on while we look up your Kratos session.</p>
                </div>
            ) : (
                <Registration />
            )}
        </LayoutShell>
    )
}
