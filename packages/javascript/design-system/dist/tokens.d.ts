export type DesignTokens = typeof designTokens;
export declare const designTokens: {
    readonly typography: {
        readonly fontFamily: "Inter, System";
        readonly fontFamilyBold: "Inter-Bold, System";
    };
    readonly colors: {
        readonly brand: "#38bdf8";
        readonly brandStrong: "#3b82f6";
        readonly background: "#020617";
        readonly card: "#0f172a";
        readonly surface: "#1e293b";
        readonly borderSoft: "#475569";
        readonly borderStrong: "#334155";
        readonly textPrimary: "#f8fafc";
        readonly textMuted: "#94a3b8";
        readonly textFaint: "#64748b";
        readonly error: "#f87171";
    };
    readonly spacing: {
        readonly xxs: 2;
        readonly xs: 4;
        readonly sm: 8;
        readonly md: 12;
        readonly lg: 16;
        readonly xl: 24;
        readonly xxl: 32;
    };
    readonly radii: {
        readonly none: 0;
        readonly sm: 6;
        readonly md: 12;
        readonly lg: 20;
        readonly full: 999;
    };
    readonly borderWidth: {
        readonly hairline: 1;
        readonly thick: 2;
    };
    readonly opacity: {
        readonly disabled: 0.4;
    };
    readonly shadows: {
        readonly card: {
            readonly shadowColor: "#020617";
            readonly shadowOpacity: 0.4;
            readonly shadowOffset: {
                readonly width: 0;
                readonly height: 20;
            };
            readonly shadowRadius: 35;
            readonly elevation: 16;
        };
    };
};
export type NativeShadow = typeof designTokens.shadows.card;
