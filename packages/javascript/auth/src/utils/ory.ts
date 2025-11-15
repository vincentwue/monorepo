import type { FlowType } from "../types/flows"

const DEFAULT_BROWSER_URL = "http://localhost:4433"
const DEFAULT_PUBLIC_API_URL = DEFAULT_BROWSER_URL

export const getOryBrowserUrl = () =>
    import.meta.env?.VITE_ORY_BROWSER_URL?.replace(/\/$/, "") || DEFAULT_BROWSER_URL

export const getOryPublicApiBaseUrl = () =>
    import.meta.env?.VITE_ORY_PUBLIC_API_URL?.replace(/\/$/, "") || DEFAULT_PUBLIC_API_URL

export const getRedirectUrl = (flowType: FlowType) => {
    const env = import.meta.env
    if (flowType === "login") return env?.VITE_AUTH_LOGIN_REDIRECT || env?.VITE_AUTH_SUCCESS_REDIRECT || "/"
    if (flowType === "registration")
        return env?.VITE_AUTH_REGISTRATION_REDIRECT || env?.VITE_AUTH_SUCCESS_REDIRECT || "/"
    return env?.VITE_AUTH_RECOVERY_REDIRECT || env?.VITE_AUTH_SUCCESS_REDIRECT || "/login"
}

export const openOryBrowserFlow = (flowType: FlowType, returnTo?: string) => {
    const base = getOryBrowserUrl()
    if (typeof window === "undefined") return
    const url = new URL(`${base}/self-service/${flowType}/browser`)
    if (returnTo) url.searchParams.set("return_to", returnTo)
    window.location.href = url.toString()
}
