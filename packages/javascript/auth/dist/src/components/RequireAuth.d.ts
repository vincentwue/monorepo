import type { JSX } from "react";
export interface RequireAuthProps {
    children: JSX.Element;
    redirectTo?: string;
    loadingFallback?: JSX.Element;
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
export declare const RequireAuth: ({ children, redirectTo, loadingFallback, skipRedirect, }: RequireAuthProps) => JSX.Element | null;
//# sourceMappingURL=RequireAuth.d.ts.map