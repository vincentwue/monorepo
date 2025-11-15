import { useEffect } from "react"
import type { BreadcrumbItem } from "../hooks/useMobileTreeNavigator"

interface BreadcrumbBarProps {
    path: BreadcrumbItem[]
    onNavigate: (id: string | null) => void
    onPathChange?: (crumbs: BreadcrumbItem[]) => void
}

export const BreadcrumbBar = ({ path, onNavigate, onPathChange }: BreadcrumbBarProps) => {
    useEffect(() => {
        onPathChange?.(path)
    }, [path, onPathChange])
    return (
        <nav className="mtu-breadcrumb" aria-label="Breadcrumb">
            {path.map((crumb, index) => {
                const isLast = index === path.length - 1
                return (
                    <span key={crumb.id ?? "root"} className="mtu-breadcrumb__item">
                        {isLast ? (
                            <span className="mtu-breadcrumb__current">{crumb.title}</span>
                        ) : (
                            <button
                                type="button"
                                className="mtu-breadcrumb__button"
                                onClick={() => onNavigate(crumb.id)}
                            >
                                {crumb.title}
                            </button>
                        )}
                        {!isLast && <span className="mtu-breadcrumb__divider">/</span>}
                    </span>
                )
            })}
        </nav>
    )
}
