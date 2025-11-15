import { getOryPublicApiBaseUrl, useSession } from "@monorepo/auth"
import axios from "axios"
import { ChevronDown, LogOut, Settings, Shield } from "lucide-react"
import {
  ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { useNavigate } from "react-router-dom"

export interface TopBarLayoutProps {
  children: ReactNode
  /**
   * Name rendered in the left side of the top bar.
   */
  appName?: string
  /**
   * Route to navigate to when clicking the app name.
   */
  homePath?: string
  /**
   * Route for the admin panel button.
   */
  adminPath?: string
  /**
   * Whether to display the admin panel shortcut.
   */
  showAdminLink?: boolean
  /**
   * Path to fall back to if Ory logout does not return a redirect URL.
   */
  logoutRedirectPath?: string
}

const DEFAULT_APP_NAME = "Idea Workspace"
const DEFAULT_HOME_PATH = "/ideas"
const DEFAULT_ADMIN_PATH = "/admin/users"
const DEFAULT_LOGOUT_REDIRECT = "/login"

export function TopBarLayout({
  children,
  appName = DEFAULT_APP_NAME,
  homePath = DEFAULT_HOME_PATH,
  adminPath = DEFAULT_ADMIN_PATH,
  showAdminLink = true,
  logoutRedirectPath = DEFAULT_LOGOUT_REDIRECT,
}: TopBarLayoutProps) {
  const [open, setOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const { session, loading: sessionLoading } = useSession()

  const identityLabel = useMemo(() => getIdentityLabel(session), [session])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [])

  const handleLogout = useCallback(async () => {
    setOpen(false)
    const baseUrl = getOryPublicApiBaseUrl()
    try {
      const response = await axios.get<{ logout_url?: string }>(
        `${baseUrl}/self-service/logout/browser`,
        { withCredentials: true },
      )

      if (response.data?.logout_url) {
        window.location.href = response.data.logout_url
        return
      }
    } catch (error) {
      console.error("Logout failed", error)
    }
    window.location.href = logoutRedirectPath
  }, [logoutRedirectPath])

  const goToAdmin = useCallback(() => {
    setOpen(false)
    if (adminPath) {
      navigate(adminPath)
    }
  }, [adminPath, navigate])

  return (
    <div className="flex h-screen w-screen flex-col bg-slate-950 text-white">
      <header className="relative z-50 flex items-center justify-between border-b border-slate-800/70 bg-slate-900/80 px-6 py-3 backdrop-blur-md">
        <h1
          onClick={() => navigate(homePath)}
          className="cursor-pointer text-lg font-semibold tracking-wide text-slate-200 transition hover:text-blue-400"
        >
          {appName}
        </h1>

        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setOpen((o) => !o)}
            className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-800/40 px-3 py-1.5 text-sm transition hover:bg-slate-700/50"
          >
            <Settings className="h-4 w-4" />
            <span className="text-slate-100">
              {sessionLoading ? "Loading..." : identityLabel}
            </span>
            <ChevronDown className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`} />
          </button>

          {open && (
            <div className="absolute right-0 z-50 mt-2 w-52 overflow-hidden rounded-lg border border-slate-800 bg-slate-900 shadow-xl">
              {showAdminLink && (
                <button
                  onClick={goToAdmin}
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-200 transition hover:bg-slate-800"
                >
                  <Shield className="h-4 w-4 text-blue-400" />
                  Admin Panel
                </button>
              )}

              <div className="border-t border-slate-800" />

              <button
                onClick={handleLogout}
                className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-200 transition hover:bg-slate-800"
              >
                <LogOut className="h-4 w-4 text-slate-400" />
                Logout
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-auto p-6">{children}</main>
    </div>
  )
}

function getIdentityLabel(session: ReturnType<typeof useSession>["session"]): string {
  const fallback = "Settings"
  if (!session || typeof session !== "object") return fallback

  const identity = (session as Record<string, unknown>).identity
  if (!identity || typeof identity !== "object") return fallback

  const traits = (identity as Record<string, unknown>).traits
  if (!traits || typeof traits !== "object") return fallback

  const traitsRecord = traits as Record<string, unknown>
  const email = getString(traitsRecord["email"])
  const username = getString(traitsRecord["username"])

  const nameField = traitsRecord["name"]
  let composedName: string | undefined
  if (nameField && typeof nameField === "object") {
    const nameRecord = nameField as Record<string, unknown>
    const first = getString(nameRecord["first"])
    const last = getString(nameRecord["last"])
    composedName = [first, last].filter(Boolean).join(" ").trim() || undefined
  }

  return email ?? username ?? composedName ?? fallback
}

const getString = (value: unknown): string | undefined =>
  typeof value === "string" && value.length > 0 ? value : undefined
