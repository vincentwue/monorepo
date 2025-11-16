import { LayoutGrid } from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { IdentityMenu } from "./IdentityMenu";

export interface TopBarLayoutProps {
  children: ReactNode;
  /**
   * Name rendered in the left side of the top bar.
   */
  appName?: string;
  /**
   * Route to navigate to when clicking the app name.
   */
  homePath?: string;
  /**
   * Route for the admin panel button.
   */
  adminPath?: string;
  /**
   * Whether to display the admin panel shortcut.
   */
  showAdminLink?: boolean;
  /**
   * Path to fall back to if Ory logout does not return a redirect URL.
   */
  logoutRedirectPath?: string;
}

const DEFAULT_APP_NAME = "Idea Workspace";
const DEFAULT_HOME_PATH = "/ideas";
const DEFAULT_ADMIN_PATH = "/admin/users";
const DEFAULT_LOGOUT_REDIRECT = "/login";

export function TopBarLayout({
  children,
  appName = DEFAULT_APP_NAME,
  homePath = DEFAULT_HOME_PATH,
  adminPath = DEFAULT_ADMIN_PATH,
  showAdminLink = true,
  logoutRedirectPath = DEFAULT_LOGOUT_REDIRECT,
}: TopBarLayoutProps) {
  const navigate = useNavigate();

  return (
    <div className="flex h-screen w-screen flex-col bg-slate-950 text-slate-50">
      {/* Top bar */}
      <header className="relative z-40 border-b border-slate-800/70 bg-slate-900/80 shadow-lg shadow-slate-950/40 backdrop-blur-xl">
        {/* subtle gradient accent line */}
        <div className="h-0.5 w-full bg-gradient-to-r from-sky-500/70 via-fuchsia-500/70 to-amber-400/70" />

        <div className="flex items-center justify-between px-6 py-3">
          {/* App brand / home link */}
          <button
            type="button"
            onClick={() => navigate(homePath)}
            className="group flex items-center gap-2 rounded-lg px-2 py-1 text-left text-slate-100 transition hover:bg-slate-800/60"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-sky-500/15 text-sky-400 ring-1 ring-sky-500/30 transition group-hover:bg-sky-500/25 group-hover:text-sky-300">
              <LayoutGrid className="h-4 w-4" />
            </span>
            <span className="flex flex-col">
              <span className="text-sm font-semibold tracking-wide">
                {appName}
              </span>
              <span className="text-[11px] font-medium uppercase tracking-[0.18em] text-slate-400">
                workspace
              </span>
            </span>
          </button>

          {/* Right side: identity menu */}
          <IdentityMenu
            adminPath={adminPath}
            showAdminLink={showAdminLink}
            logoutRedirectPath={logoutRedirectPath}
          />
        </div>
      </header>

      {/* Content area */}
      <main className="min-h-0 flex-1 overflow-auto bg-gradient-to-b from-slate-950 via-slate-950/95 to-slate-950 px-6 py-6">
        {/* Optional max-width wrapper to make apps feel centered */}
        <div className="mx-auto h-full w-full max-w-6xl">{children}</div>
      </main>
    </div>
  );
}
