import { Route, Routes } from "react-router-dom"
import { LoginPage } from "../pages/LoginPage"
import { RegistrationPage } from "../pages/RegistrationPage"
import { RecoveryPage } from "../pages/RecoveryPage"
import { ErrorPage } from "../pages/ErrorPage"
import { DashboardPage } from "../pages/DashboardPage"

export const AuthRoutes = () => (
    <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegistrationPage />} />
        <Route path="/recovery" element={<RecoveryPage />} />
        <Route path="/error" element={<ErrorPage />} />
        <Route path="/*" element={<DashboardPage />} />
    </Routes>
)
