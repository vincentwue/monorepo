import type { ReactNode } from "react"
import { AuthFlow, type AuthFlowProps } from "./AuthFlow"
import { openOryBrowserFlow } from "../utils/ory"

export interface LoginProps extends Omit<AuthFlowProps, "flowType"> {
    footer?: ReactNode
}

const footerLinkClass =
    "font-semibold text-brand underline-offset-4 transition hover:text-brand-strong hover:underline focus-visible:outline-none"

const DefaultLoginFooter = () => (
    <div className="flex flex-wrap items-center justify-center gap-4 text-sm text-muted">
        <button type="button" className={footerLinkClass} onClick={() => openOryBrowserFlow("registration")}>
            Create account
        </button>
        <button type="button" className={footerLinkClass} onClick={() => openOryBrowserFlow("recovery")}>
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
