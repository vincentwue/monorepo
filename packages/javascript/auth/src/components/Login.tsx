import type { ReactNode } from "react"
import { AuthFlow, type AuthFlowProps } from "./AuthFlow"
import { openOryBrowserFlow } from "../utils/ory"

export interface LoginProps extends Omit<AuthFlowProps, "flowType"> {
    footer?: ReactNode
}

const DefaultLoginFooter = () => (
    <div className="ory-auth-links">
        <button type="button" onClick={() => openOryBrowserFlow("registration")}>
            Create account
        </button>
        <button type="button" onClick={() => openOryBrowserFlow("recovery")}>
            Forgot password?
        </button>
    </div>
)

export const Login = ({
    title = "Sign in",
    description = "Enter your credentials to continue with your subscription.",
    submitLabel = "Continue",
    footer,
    ...rest
}: LoginProps) => (
    <AuthFlow
        flowType="login"
        title={title}
        description={description}
        submitLabel={submitLabel}
        footer={footer ?? <DefaultLoginFooter />}
        {...rest}
    />
)
