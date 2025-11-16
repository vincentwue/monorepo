import type { CSSProperties } from "react";

export const INDENT_WIDTH = 24;

// Base parameters for the depth color generator
const BASE_HUE = 270; // starting hue (purple-ish)
const HUE_STEP = 80; // hue shift per depth level
const SATURATION = 55; // constant saturation
const LIGHTNESS_BASE = 90; // base lightness
const LIGHTNESS_STEP = 0; // lightness change per depth

export function getIndentStyle(depth: number = 0): CSSProperties {
  return {
    // TreeNode.tsx spreads this into the wrapper div
    // <div style={{ marginTop: 12, ...indentStyle }}>
    marginLeft: `${Math.max(depth, 0) * INDENT_WIDTH}px`,
  };
}

// Background color generated from depth.
// `selected` is intentionally ignored so selection stays border-only.
export function getDepthBackground(
  depth: number = 0,
  _selected: boolean = false
): string {
  const d = Math.max(depth, 0);
  const hue = (BASE_HUE + d * HUE_STEP) % 360;
  const lightness = Math.min(LIGHTNESS_BASE + d * LIGHTNESS_STEP, 32);

  // Slight transparency so it blends with the dark page background
  return `hsla(${hue}, ${SATURATION}%, ${lightness}%, 0.2)`;
}

// Guide color derived from the same hue, but brighter
export function getDepthGuideColor(depth: number = 0): string {
  const d = Math.max(depth, 0);
  const hue = (BASE_HUE + d * HUE_STEP) % 360;
  const lightness = Math.min(58 + d * 3, 80);

  return `hsl(${hue}, ${SATURATION + 10}%, ${lightness}%)`;
}
