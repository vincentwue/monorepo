import { RequireAuth, useSession } from "@monorepo/auth";
import { useEffect } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { TopBarLayout } from "@monorepo/topbar-layout";
import { FocusOverlay } from "./components/FocusOverlay";
import { IdeasTreePage } from "./features/ideas/IdeasTreePage";

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
        {/* Render login button if logged out */}
        <SessionAwareLoginButton authUrl={loginUrl} />

        <Routes>
          <Route
            path="/*"
            element={
              <RequireAuth
                skipRedirect   // do not auto-redirect away
                // redirectTo={loginUrl}
                unauthenticatedFallback={<div>login here</div>}
              >
                <IdeasTreePage />
              </RequireAuth>
            }
          />
        </Routes>

        <FocusOverlay />
      </TopBarLayout>
    </BrowserRouter>
  );
}

// ---------------------------------------------------------
// Login button that auto-hides when logged in
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
