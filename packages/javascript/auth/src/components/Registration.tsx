import type { ReactNode } from "react"
import { AuthFlow, type AuthFlowProps } from "./AuthFlow"
import { openOryBrowserFlow } from "../utils/ory"

export interface RegistrationProps extends Omit<AuthFlowProps, "flowType"> {
    footer?: ReactNode
}

const DefaultRegistrationFooter = () => (
    <div className="ory-auth-links">
        <button type="button" onClick={() => openOryBrowserFlow("login")}>
            Already have an account?
        </button>
        <button type="button" onClick={() => openOryBrowserFlow("recovery")}>
            Recover access
        </button>
    </div>
)

export const Registration = ({
    title = "Create your account",
    description = "Provision access to the shared Ory identity platform.",
    submitLabel = "Create account",
    footer,
    ...rest
}: RegistrationProps) => (
    <AuthFlow
        flowType="registration"
        title={title}
        description={description}
        submitLabel={submitLabel}
        footer={footer ?? <DefaultRegistrationFooter />}
        {...rest}
    />
)
