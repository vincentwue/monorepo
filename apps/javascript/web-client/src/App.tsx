import { RequireAuth, useSession } from "@monorepo/auth";
import { useEffect } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { SplitLayout } from "@monorepo/layout";
import { FocusOverlay } from "./components/FocusOverlay";
import { IdeasTreePage } from "./features/ideas/IdeasTreePage";
import { TopBarLayout } from "./layout/TopBarLayout";

const AUTH_UI_BASE_URL = import.meta.env.VITE_AUTH_UI_BASE_URL ?? "";
const APP_BASE_URL = import.meta.env.VITE_APP_BASE_URL ?? "";

export default function App() {
  useEffect(() => {
    console.log("[App] initialized web client");
  }, []);

  const currentUrl = window.location.href;
  const returnTo = currentUrl || APP_BASE_URL || window.location.href;
  const loginTargetBase = AUTH_UI_BASE_URL || "";

  if (!AUTH_UI_BASE_URL) {
    console.warn("Missing VITE_AUTH_UI_BASE_URL; falling back to relative login route.");
  }

  const loginUrl = loginTargetBase
    ? `${loginTargetBase}/login?return_to=${encodeURIComponent(returnTo)}`
    : `/login?return_to=${encodeURIComponent(returnTo)}`;

  return (
    <BrowserRouter>
      <TopBarLayout>
        {/* ?Y'? Render login button if logged out */}
        <SessionAwareLoginButton authUrl={loginUrl} />

        <div className="relative flex h-full min-h-0 flex-1 flex-col gap-4 bg-slate-900 p-4 text-white">
          <div className="flex h-full min-h-0 flex-1 overflow-hidden rounded-xl border border-slate-800/70 bg-slate-900/80">
            <Routes>
              <Route
                path="/*"
                element={
                  <RequireAuth skipRedirect redirectTo={loginUrl}>
                    <SplitLayout
                      direction="horizontal"
                      sizes={[40, 60]}
                      minSize={[500, 300]}
                      gutterSize={8}
                      className="flex h-full"
                    >
                      {/* Left panel (tree, navigator) */}
                      <div className="flex h-full min-w-[500px] overflow-hidden border-r border-slate-800">
                        {/* Your Tree / Sidebar */}
                        <IdeasTreePage />
                      </div>

                      {/* Right panel (details) */}
                      <div className="h-full">
                        {/* Active idea / editor / etc. */}
                      </div>
                    </SplitLayout>
                  </RequireAuth>
                }
              />
            </Routes>
          </div>
        </div>

        <FocusOverlay />
      </TopBarLayout>
    </BrowserRouter>
  );
}

// ---------------------------------------------------------
// ?Y"? New: Login button that auto-hides when logged in
// ---------------------------------------------------------

function SessionAwareLoginButton({ authUrl }: { authUrl: string }) {
  const { session, loading } = useSession();

  if (loading) return null;
  if (session) return null;

  return (
    <button
      onClick={() => {
        window.location.href = authUrl;
      }}
      className="absolute top-3 left-3 rounded-md bg-white/10 px-3 py-1 text-sm hover:bg-white/20 border border-white/20"
    >
      Login
    </button>
  );
}
