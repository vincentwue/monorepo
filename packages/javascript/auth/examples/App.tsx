import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom"
import { Login, Registration, Recovery, RequireAuth, useSession, openOryBrowserFlow } from "@monorepo/auth"

const SessionPanel = () => {
    const { session, loading, error } = useSession()

    if (loading) return <p className="session-panel">Checking session...</p>
    if (error) return <p className="session-panel error">Session check failed. See console.</p>

    return (
        <div className="session-panel">
            <strong>Session status:</strong> {session ? "active" : "none"}
            {session && <pre>{JSON.stringify(session.identity?.traits ?? session, null, 2)}</pre>}
        </div>
    )
}

const ProtectedDashboard = () => {
    const { session } = useSession()
    const email = session?.identity?.traits?.email || session?.id

    return (
        <div className="protected-card">
            <h3>Protected content</h3>
            <p>Only visible if Ory session is valid.</p>
            <p className="muted">Signed in as: {email}</p>
        </div>
    )
}

const Landing = () => (
    <div className="landing-card">
        <h2>Unified Ory Auth Components</h2>
        <p>Navigate via the links above to start login, registration, or recovery flows.</p>
        <button type="button" onClick={() => openOryBrowserFlow("login")} className="cta">
            Trigger login flow
        </button>
    </div>
)

const ExampleApp = () => (
    <BrowserRouter>
        <div className="demo-shell">
            <header>
                <h1>Ory Auth Components</h1>
                <p>Share login, registration, recovery, and session guards across apps.</p>
            </header>

            <nav className="demo-tabs">
                <NavLink to="/" end>
                    Home
                </NavLink>
                <NavLink to="/login">Login</NavLink>
                <NavLink to="/register">Registration</NavLink>
                <NavLink to="/recovery">Recovery</NavLink>
                <NavLink to="/protected">Protected route</NavLink>
            </nav>

            <SessionPanel />

            <section className="demo-preview">
                <Routes>
                    <Route path="/" element={<Landing />} />
                    <Route path="/login" element={<Login />} />
                    <Route path="/register" element={<Registration />} />
                    <Route path="/recovery" element={<Recovery />} />
                    <Route
                        path="/protected"
                        element={
                            <RequireAuth loadingFallback={<p className="session-panel">Authorizing...</p>}>
                                <ProtectedDashboard />
                            </RequireAuth>
                        }
                    />
                </Routes>
            </section>
        </div>
    </BrowserRouter>
)

export default ExampleApp
