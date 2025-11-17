import { Route, Routes } from "react-router-dom"
import { DashboardPage } from "../pages/DashboardPage"
import { ErrorPage } from "../pages/ErrorPage"
import { LoginPage } from "../pages/LoginPage"
import { LogoutPage } from "../pages/LogoutPage"
import { RecoveryPage } from "../pages/RecoveryPage"
import { RegistrationPage } from "../pages/RegistrationPage"

export const AuthRoutes = () => (
    <Routes>
        <Route path="/auth/login" element={<LoginPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/auth/register" element={<RegistrationPage />} />
        <Route path="/register" element={<RegistrationPage />} />
        <Route path="/auth/recovery" element={<RecoveryPage />} />
        <Route path="/recovery" element={<RecoveryPage />} />
        <Route path="/error" element={<ErrorPage />} />
        <Route path="/logout" element={<LogoutPage />} />
        <Route path="/*" element={<DashboardPage />} />
    </Routes>
)
