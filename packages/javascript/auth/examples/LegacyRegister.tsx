import axios from "axios"
import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { getOryBrowserUrl } from "@monorepo/auth"

axios.defaults.withCredentials = true

/**
 * Legacy registration demo kept for experimentation.
 * Prefer <Registration /> from the library for real usage.
 */
const LegacyRegister = () => {
    const [flow, setFlow] = useState<any>(null)
    const [shake, setShake] = useState(false)
    const navigate = useNavigate()
    const api = getOryBrowserUrl()
    const type = "registration"

    useEffect(() => {
        const params = new URLSearchParams(window.location.search)
        const flowId = params.get("flow")

        const loadFlow = async () => {
            try {
                if (flowId) {
                    const r = await axios.get(`${api}/self-service/${type}/flows?id=${flowId}`, {
                        withCredentials: true,
                    })
                    setFlow(r.data)
                } else {
                    window.location.href = `${api}/self-service/${type}/browser`
                }
            } catch (err) {
                console.error(`Failed to load ${type} flow`, err)
                window.location.href = `${api}/self-service/${type}/browser`
            }
        }

        loadFlow()
    }, [api])

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault()
        if (!flow) return

        const form = new URLSearchParams()
        new FormData(e.currentTarget).forEach((value, key) => form.append(key, String(value)))
        if (!form.get("method")) form.set("method", "password")

        try {
            const res = await axios.post(flow.ui.action, form, {
                withCredentials: true,
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
            })
            console.log("Registration success:", res.data)
            navigate("/")
        } catch (err: any) {
            console.error("Registration failed:", err.response?.data || err)

            if (err.response?.data?.ui) {
                setFlow(err.response.data)
            }

            setShake(true)
            setTimeout(() => setShake(false), 500)
        }
    }

    if (!flow)
        return <p className="text-center text-slate-400 mt-20">Loading registration flow...</p>

    return (
        <div className="flex min-h-screen items-center justify-center bg-slate-950 text-white px-4">
            <form
                onSubmit={handleSubmit}
                className={`w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/80 p-8 shadow-xl backdrop-blur-md transition-transform ${
                    shake ? "animate-shake" : ""
                }`}
            >
                <h2 className="text-2xl font-semibold text-center mb-6">Create an Account</h2>

                {flow.ui.messages?.length > 0 && (
                    <div className="mb-4 text-red-400 text-sm">
                        {flow.ui.messages.map((m: any) => (
                            <p key={m.id}>{m.text}</p>
                        ))}
                    </div>
                )}

                {flow.ui.nodes.map((n: any) => {
                    const attr = n.attributes
                    if (attr.type === "hidden") return <input key={attr.name} {...attr} />
                    if (attr.name === "method" && attr.value === "password") return null

                    const messages = n.messages?.length ? n.messages : []

                    return (
                        <div key={attr.name} className="mb-5">
                            <label className="block text-sm mb-1 text-slate-300">
                                {n.meta?.label?.text || attr.name}
                            </label>
                            <input
                                {...attr}
                                className="w-full rounded-md bg-slate-800/60 px-3 py-2 text-white border border-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                            {messages.map((m: any) => (
                                <p key={m.id} className="text-red-400 text-xs mt-1">
                                    {m.text}
                                </p>
                            ))}
                        </div>
                    )
                })}

                <input type="hidden" name="method" value="password" />

                <button
                    type="submit"
                    className="w-full mt-4 bg-blue-600 hover:bg-blue-500 transition-colors py-2 rounded-md font-medium"
                >
                    Sign up
                </button>

                <p className="text-center text-sm text-slate-400 mt-6">
                    Already have an account?{" "}
                    <button type="button" onClick={() => navigate("/login")} className="text-blue-400 hover:underline">
                        Sign in
                    </button>
                </p>
            </form>

            <style>
                {`
        @keyframes shake {
          10%, 90% { transform: translateX(-2px); }
          20%, 80% { transform: translateX(4px); }
          30%, 50%, 70% { transform: translateX(-6px); }
          40%, 60% { transform: translateX(6px); }
        }
        .animate-shake {
          animation: shake 0.4s cubic-bezier(.36,.07,.19,.97) both;
        }
        `}
            </style>
        </div>
    )
}

export default LegacyRegister
