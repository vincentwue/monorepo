/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_ORY_BROWSER_URL?: string
    readonly VITE_AUTH_SUCCESS_REDIRECT?: string
    readonly VITE_AUTH_LOGIN_REDIRECT?: string
    readonly VITE_AUTH_REGISTRATION_REDIRECT?: string
    readonly VITE_AUTH_RECOVERY_REDIRECT?: string
}

interface ImportMeta {
    readonly env: ImportMetaEnv
}
