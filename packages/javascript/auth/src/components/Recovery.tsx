import type { ReactNode } from "react"
import { AuthFlow, type AuthFlowProps } from "./AuthFlow"
import { openOryBrowserFlow } from "../utils/ory"

export interface RecoveryProps extends Omit<AuthFlowProps, "flowType"> {
    footer?: ReactNode
}

const DefaultRecoveryFooter = () => (
    <div className="ory-auth-links">
        <button type="button" onClick={() => openOryBrowserFlow("login")}>
            Back to login
        </button>
        <button type="button" onClick={() => openOryBrowserFlow("registration")}>
            Need an account?
        </button>
    </div>
)

export const Recovery = ({
    title = "Recover access",
    description = "Send yourself a magic link to reset your password.",
    submitLabel = "Send recovery link",
    footer,
    ...rest
}: RecoveryProps) => (
    <AuthFlow
        flowType="recovery"
        title={title}
        description={description}
        submitLabel={submitLabel}
        footer={footer ?? <DefaultRecoveryFooter />}
        {...rest}
    />
)
