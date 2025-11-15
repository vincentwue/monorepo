import { useEffect } from "react"
import axios from "axios"
import { getOryPublicApiBaseUrl } from "../utils/ory"

const DEFAULT_REDIRECT = "/login"

export const Logout = () => {
    useEffect(() => {
        const baseUrl = getOryPublicApiBaseUrl()
        axios
            .get(`${baseUrl}/self-service/logout/browser`, { withCredentials: true })
            .then((response) => {
                window.location.href = response.data.logout_url || DEFAULT_REDIRECT
            })
            .catch(() => {
                window.location.href = DEFAULT_REDIRECT
            })
    }, [])

    return <p>Logging out...</p>
}

export default Logout
