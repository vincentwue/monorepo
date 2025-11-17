import { LayoutShell } from "../components/LayoutShell"
import { Logout } from "@monorepo/auth"

export const LogoutPage = () => (
    <LayoutShell>
            <div className="panel">
                <h1>Signing you out…</h1>
                <p className="mt-2 mb-4">
                    We are terminating your Ory session and redirecting you.
                </p>
                <Logout />
            </div>
    </LayoutShell>
)
