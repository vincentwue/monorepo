import axios from "axios"
import type { FormEvent, ReactNode } from "react"
import { useEffect, useMemo, useState } from "react"
import { getOryBrowserUrl, getRedirectUrl, openOryBrowserFlow } from "../utils/ory"
import type { FlowType } from "../types/flows"
import "../styles.css"

type OryNode = {
    attributes: {
        name: string
        type: string
        value?: string | number | boolean
        required?: boolean
        disabled?: boolean
        autocomplete?: string
        pattern?: string
        minLength?: number
        maxLength?: number
        placeholder?: string
    }
    meta?: {
        label?: {
            text?: string
        }
    }
    messages?: { id: string | number; text: string }[]
}

type OryFlow = {
    id: string
    ui: {
        action: string
        method: string
        nodes: OryNode[]
        messages?: { id: string | number; text: string }[]
    }
}

const DEFAULT_SUBMIT_LABEL: Record<FlowType, string> = {
    login: "Continue",
    registration: "Create account",
    recovery: "Send recovery link",
}

export interface AuthFlowProps {
    flowType: FlowType
    title?: string
    description?: string
    submitLabel?: string
    className?: string
    redirectTo?: string
    footer?: ReactNode
    onSuccess?: (payload: unknown) => void
    onError?: (error: unknown) => void
}

export const AuthFlow = ({
    flowType,
    title,
    description,
    submitLabel,
    className,
    redirectTo,
    footer,
    onError,
    onSuccess,
}: AuthFlowProps) => {
    const [flow, setFlow] = useState<OryFlow | null>(null)
    const [loading, setLoading] = useState(true)
    const [formValues, setFormValues] = useState<Record<string, string>>({})
    const [localError, setLocalError] = useState<string | null>(null)
    const baseUrl = useMemo(() => getOryBrowserUrl(), [])

    useEffect(() => {
        if (typeof window === "undefined") return
        let cancelled = false
        const fetchFlow = async () => {
            setLoading(true)
            setLocalError(null)
            try {
                const params = new URLSearchParams(window.location.search)
                const flowId = params.get("flow")
                if (!flowId) {
                    openOryBrowserFlow(flowType, window.location.href)
                    return
                }

                const res = await axios.get<OryFlow>(`${baseUrl}/self-service/${flowType}/flows`, {
                    params: { id: flowId },
                    withCredentials: true,
                })

                if (!cancelled) {
                    setFlow(res.data)
                }
            } catch (error: any) {
                console.error(`Failed to load ${flowType} flow`, error)
                if (error?.response?.status === 404 || error?.response?.status === 410) {
                    openOryBrowserFlow(flowType, window.location.href)
                    return
                }
                setLocalError("Unable to reach the Ory backend. Check your env values.")
                onError?.(error)
            } finally {
                if (!cancelled) {
                    setLoading(false)
                }
            }
        }

        fetchFlow()
        return () => {
            cancelled = true
        }
    }, [baseUrl, flowType, onError])

    useEffect(() => {
        if (!flow) return
        setFormValues((prev) => {
            const next = { ...prev }
            flow.ui.nodes.forEach((node) => {
                const { name, value } = node.attributes
                if (value !== undefined && next[name] === undefined) {
                    next[name] = String(value)
                }
            })
            return next
        })
    }, [flow])

    const handleChange = (key: string, value: string) => {
        setFormValues((prev) => ({ ...prev, [key]: value }))
    }

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        if (!flow) return

        const payload = new URLSearchParams()
        Object.entries(formValues).forEach(([key, value]) => {
            payload.set(key, value)
        })

        flow.ui.nodes
            .filter((node) => node.attributes.type === "hidden")
            .forEach((node) => {
                const { name, value } = node.attributes
                if (!name || value === undefined) return
                if (!payload.has(name)) {
                    payload.set(name, String(value))
                }
            })

        const csrfNode = flow.ui.nodes.find((node) => node.attributes.name === "csrf_token")
        if (csrfNode && !payload.get("csrf_token") && csrfNode.attributes.value) {
            payload.set("csrf_token", String(csrfNode.attributes.value))
        }

        if (!payload.get("method")) {
            const methodNode = flow.ui.nodes.find((node) => node.attributes.name === "method")
            if (methodNode?.attributes.value) {
                payload.set("method", String(methodNode.attributes.value))
            } else if (flowType === "login") {
                payload.set("method", "password")
            }
        }

        try {
            const response = await axios.post(flow.ui.action, payload, {
                withCredentials: true,
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
            })

            if (onSuccess) {
                onSuccess(response.data)
                return
            }

            const target = redirectTo || getRedirectUrl(flowType)
            if (target && typeof window !== "undefined") {
                window.location.assign(target)
            }
        } catch (error: any) {
            console.error("Auth flow submission failed", error)
            onError?.(error)

            const data = error?.response?.data
            if (data?.ui) {
                setFlow(data)
                return
            }

            if (error?.response?.status === 410) {
                openOryBrowserFlow(flowType, typeof window !== "undefined" ? window.location.href : undefined)
                return
            }

            setLocalError("The credentials were rejected. Please try again.")
        }
    }

    if (loading || !flow) {
        return (
            <div className={`ory-auth-shell ${className ?? ""}`}>
                <div className="ory-auth-panel">
                    <p className="ory-auth-loading">Loading {flowType} flow...</p>
                </div>
            </div>
        )
    }

    return (
        <div className={`ory-auth-shell ${className ?? ""}`}>
            <form className="ory-auth-panel" onSubmit={handleSubmit}>
                {title && <h2 className="ory-auth-title">{title}</h2>}
                {description && <p className="ory-auth-description">{description}</p>}

                {localError && <p className="ory-auth-error">{localError}</p>}

                {flow.ui.messages?.length ? (
                    <div className="ory-auth-error">
                        {flow.ui.messages.map((message) => (
                            <p key={message.id}>{message.text}</p>
                        ))}
                    </div>
                ) : null}

                {flow.ui.nodes.map((node) => {
                    const attr = node.attributes
                    const key = `${flow.id}-${attr.name}`

                    if (attr.type === "hidden") {
                        return <input key={key} type="hidden" name={attr.name} value={String(attr.value ?? "")} />
                    }

                    if (attr.type === "submit" || attr.type === "button") {
                        return null
                    }

                    const label = node.meta?.label?.text || attr.name
                    const currentValue = formValues[attr.name] ?? ""

                    return (
                        <div key={key} className="ory-auth-field">
                            <label className="ory-auth-label" htmlFor={attr.name}>
                                {label}
                            </label>
                            <input
                                id={attr.name}
                                name={attr.name}
                                type={attr.name.toLowerCase().includes("email") ? "email" : attr.type}
                                className="ory-auth-input"
                                placeholder={attr.placeholder}
                                autoComplete={attr.autocomplete}
                                disabled={attr.disabled}
                                required={attr.required}
                                value={currentValue}
                                onChange={(event) => handleChange(attr.name, event.target.value)}
                            />
                            {node.messages?.map((message) => (
                                <p key={message.id} className="ory-auth-field-message">
                                    {message.text}
                                </p>
                            ))}
                        </div>
                    )
                })}

                <button type="submit" className="ory-auth-submit">
                    {submitLabel || DEFAULT_SUBMIT_LABEL[flowType]}
                </button>

                {footer && <div className="ory-auth-footer">{footer}</div>}
            </form>
        </div>
    )
}
