import type { PropsWithChildren } from "react"
import { Link, NavLink } from "react-router-dom"

export const LayoutShell = ({ children }: PropsWithChildren) => (
    <div className="auth-shell">
        <header className="auth-shell__header">
            <Link to="/" className="auth-shell__brand">
                Identity Portal
            </Link>
            <nav className="auth-shell__nav">
                <NavLink to="/login">Login</NavLink>
                <NavLink to="/register">Register</NavLink>
                <NavLink to="/recovery">Recovery</NavLink>
            </nav>
        </header>
        <main className="auth-shell__main">{children}</main>
    </div>
)
