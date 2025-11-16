import { getOryPublicApiBaseUrl, useSession } from "@monorepo/auth";
import axios from "axios";
import { ChevronDown, LogOut, Settings, Shield, User } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getIdentityLabel } from "./getIdentityLabel";

export interface IdentityMenuProps {
  adminPath?: string;
  showAdminLink?: boolean;
  logoutRedirectPath?: string;
  /**
   * Where to send the user when they click "Login" and there is no active session.
   * Defaults to VITE_AUTH_LOGIN_REDIRECT, falling back to "/login".
   */
  loginRedirectPath?: string;
}

const DEFAULT_ADMIN_PATH = "/admin/users";
const DEFAULT_LOGOUT_REDIRECT = "/login";
const DEFAULT_LOGIN_REDIRECT = "/login";

/**
 * Resolve the login redirect target:
 * 1. Explicit prop
 * 2. Vite env: VITE_AUTH_LOGIN_REDIRECT
 * 3. "/login"
 */
function resolveLoginRedirect(custom?: string): string {
  if (custom && custom.trim().length > 0) return custom;

  try {
    // Guard against non-Vite environments
    if (
      typeof import.meta !== "undefined" &&
      (import.meta as any).env?.VITE_AUTH_LOGIN_REDIRECT
    ) {
      return (import.meta as any).env.VITE_AUTH_LOGIN_REDIRECT as string;
    }
  } catch {
    // ignore and use fallback
  }

  return DEFAULT_LOGIN_REDIRECT;
}

export function IdentityMenu({
  adminPath = DEFAULT_ADMIN_PATH,
  showAdminLink = true,
  logoutRedirectPath = DEFAULT_LOGOUT_REDIRECT,
  loginRedirectPath,
}: IdentityMenuProps) {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { session, loading: sessionLoading } = useSession();

  const label = useMemo(() => getIdentityLabel(session), [session]);
  const loginTarget = useMemo(
    () => resolveLoginRedirect(loginRedirectPath),
    [loginRedirectPath],
  );

  // Close on outside click.
  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      if (!dropdownRef.current) return;
      if (!dropdownRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Close on Escape.
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const handleLogout = useCallback(async () => {
    setOpen(false);
    const baseUrl = getOryPublicApiBaseUrl();
    try {
      const response = await axios.get<{ logout_url?: string }>(
        `${baseUrl}/self-service/logout/browser`,
        { withCredentials: true },
      );

      if (response.data?.logout_url) {
        window.location.href = response.data.logout_url;
        return;
      }
    } catch (error) {
      console.error("Logout failed", error);
    }
    window.location.href = logoutRedirectPath;
  }, [logoutRedirectPath]);

  const goToAdmin = useCallback(() => {
    setOpen(false);
    if (adminPath) {
      navigate(adminPath);
    }
  }, [adminPath, navigate]);

  // ---------------------------------------------------------------------------
  // Logged-out state: show a simple "Login" button on the top right
  // ---------------------------------------------------------------------------
  if (!sessionLoading && !session) {
    return (
      <button
        type="button"
        onClick={() => {
          window.location.href = loginTarget;
        }}
        className="rounded-full border border-sky-500/70 bg-slate-900/80 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-sky-400 shadow-sm shadow-slate-950/40 transition hover:border-sky-400 hover:bg-slate-900 hover:text-sky-300"
      >
        Login
      </button>
    );
  }

  // ---------------------------------------------------------------------------
  // Logged-in state: full identity dropdown menu
  // ---------------------------------------------------------------------------
  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setOpen((state) => !state)}
        className="flex items-center gap-2 rounded-full border border-slate-800/80 bg-slate-900/70 px-3 py-1.5 text-xs font-medium text-slate-100 shadow-sm shadow-slate-950/40 transition hover:border-sky-500/60 hover:bg-slate-900"
      >
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-800 text-slate-300 ring-1 ring-slate-700">
          <User className="h-3.5 w-3.5" />
        </span>
        <span className="max-w-[140px] truncate text-[12px]">
          {sessionLoading ? "Loading session..." : label}
        </span>
        <ChevronDown
          className={`h-3 w-3 text-slate-500 transition-transform ${open ? "rotate-180" : ""
            }`}
        />
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-56 overflow-hidden rounded-xl border border-slate-800/80 bg-slate-950/98 shadow-xl shadow-black/60">
          <div className="flex items-center gap-2 border-b border-slate-800/80 bg-gradient-to-r from-slate-950 via-slate-900 to-slate-950 px-3 py-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-sky-500/15 text-sky-400 ring-1 ring-sky-500/40">
              <Settings className="h-4 w-4" />
            </div>
            <div className="flex flex-col">
              <span className="text-[13px] font-semibold text-slate-50">
                {label}
              </span>
              <span className="text-[11px] text-slate-400">
                Account & workspace
              </span>
            </div>
          </div>

          <div className="py-1">
            {showAdminLink && (
              <button
                type="button"
                onClick={goToAdmin}
                className="flex w-full items-center gap-2 px-3 py-2 text-[13px] text-slate-200 transition hover:bg-slate-900/90"
              >
                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-sky-500/15 text-sky-400">
                  <Shield className="h-3.5 w-3.5" />
                </span>
                <div className="flex flex-col items-start">
                  <span className="leading-tight">Admin panel</span>
                  <span className="text-[11px] text-slate-500">
                    Manage users & access
                  </span>
                </div>
              </button>
            )}

            <div className="my-1 border-t border-slate-800/80" />

            <button
              type="button"
              onClick={handleLogout}
              className="flex w-full items-center gap-2 px-3 py-2 text-[13px] text-slate-200 transition hover:bg-slate-900/90"
            >
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-slate-800 text-slate-300">
                <LogOut className="h-3.5 w-3.5" />
              </span>
              <div className="flex flex-col items-start">
                <span className="leading-tight">Logout</span>
                <span className="text-[11px] text-slate-500">
                  Sign out from this browser
                </span>
              </div>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
