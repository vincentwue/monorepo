import type { FlowType } from "../types/flows"

const sanitizeUrl = (value: string) => value.replace(/\/$/, "")

const requireEnv = (value: string | undefined, key: string) => {
    if (!value) {
        throw new Error(`Missing ${key} environment variable.`)
    }
    return sanitizeUrl(value)
}

export const getOryBrowserUrl = () => requireEnv(import.meta.env?.VITE_ORY_BROWSER_URL, "VITE_ORY_BROWSER_URL")

export const getOryPublicApiBaseUrl = () =>
    requireEnv(import.meta.env?.VITE_ORY_PUBLIC_API_URL, "VITE_ORY_PUBLIC_API_URL")

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
