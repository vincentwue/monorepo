import { RequireAuth, useSession } from "@monorepo/auth"
import { LayoutShell } from "../components/LayoutShell"

const DashboardContent = () => {
    const { session, loading } = useSession()

    if (loading) {
        return <p className="panel">Loading session...</p>
    }

    if (!session) {
        return <p className="panel">No session found.</p>
    }

    return (
        <div className="panel">
            <h1>Welcome back</h1>
            <p>Your Ory session is active.</p>
            <pre>{JSON.stringify(session.identity ?? session, null, 2)}</pre>
        </div>
    )
}

export const DashboardPage = () => (
    <LayoutShell>
        <RequireAuth>
            <DashboardContent />
        </RequireAuth>
    </LayoutShell>
)
