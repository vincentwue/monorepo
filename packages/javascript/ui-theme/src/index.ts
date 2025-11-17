export const colors = {
  brand: "#38bdf8",
  brandStrong: "#3b82f6",
  background: "#020617",
  card: "#0f172a",
  surface: "#1e293b",
  borderSoft: "#475569",
  borderStrong: "#334155",
  textPrimary: "#f8fafc",
  textMuted: "#94a3b8",
  textFaint: "#64748b",
  error: "#f87171",
} as const;

export const spacing = {
  xxs: 2,
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const typography = {
  fontFamily: "Inter, System",
  fontFamilyBold: "Inter-Bold, System",
} as const;

export const radii = {
  none: 0,
  sm: 6,
  md: 12,
  lg: 20,
  full: 999,
} as const;

export const borderWidth = {
  hairline: 1,
  thick: 2,
} as const;

export const opacity = {
  disabled: 0.4,
} as const;

export const uiTheme = {
  colors,
  spacing,
  typography,
  radii,
  borderWidth,
  opacity,
} as const;

export type UiTheme = typeof uiTheme;
