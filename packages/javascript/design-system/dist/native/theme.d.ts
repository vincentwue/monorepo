import { designTokens } from "../tokens";
export interface NativeTheme {
    colors: typeof designTokens.colors;
    spacing: typeof designTokens.spacing;
    radii: typeof designTokens.radii;
    typography: typeof designTokens.typography;
    borderWidth: typeof designTokens.borderWidth;
    opacity: typeof designTokens.opacity;
    shadows: typeof designTokens.shadows;
}
export declare const nativeTheme: NativeTheme;
