import type { ReactNode } from "react"
import { AuthFlow, type AuthFlowProps } from "./AuthFlow"
import { openOryBrowserFlow } from "../utils/ory"

export interface RegistrationProps extends Omit<AuthFlowProps, "flowType"> {
    footer?: ReactNode
}

const footerLinkClass =
    "font-semibold text-brand underline-offset-4 transition hover:text-brand-strong hover:underline focus-visible:outline-none"

const DefaultRegistrationFooter = () => (
    <div className="flex flex-wrap items-center justify-center gap-4 text-sm text-muted">
        <button type="button" className={footerLinkClass} onClick={() => openOryBrowserFlow("login")}>
            Already have an account?
        </button>
        <button type="button" className={footerLinkClass} onClick={() => openOryBrowserFlow("recovery")}>
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
