import type { CSSProperties } from "react";

export const INDENT_WIDTH = 24;

// Base parameters for the depth color generator
const BASE_HUE = 270; // starting hue (purple-ish)
const HUE_STEP = 80; // hue shift per depth
const SATURATION = 50;
const LIGHTNESS_BASE = 58; // darker = works better with transparency
const LIGHTNESS_STEP = 0;

// Overall transparency for depth backgrounds
const BG_ALPHA = 0.28; // previously 0.20

// Transparency for guide lines
const GUIDE_ALPHA = 0.35;

export function getIndentStyle(depth: number = 0): CSSProperties {
  return {
    marginLeft: `${Math.max(depth, 0) * INDENT_WIDTH}px`,
  };
}

// Background color generated from depth (very subtle)
export function getDepthBackground(
  depth: number = 0,
  _selected: boolean = false
): string {
  const d = Math.max(depth, 0);
  const hue = (BASE_HUE + d * HUE_STEP) % 360;
  const lightness = Math.min(LIGHTNESS_BASE + d * LIGHTNESS_STEP, 28);

  return `hsla(${hue}, ${SATURATION}%, ${lightness}%, ${BG_ALPHA})`;
}

// Guide color – slightly bright but still transparent
export function getDepthGuideColor(depth: number = 0): string {
  const d = Math.max(depth, 0);
  const hue = (BASE_HUE + d * HUE_STEP) % 360;
  const lightness = Math.min(50 + d * 3, 78);

  return `hsla(${hue}, ${SATURATION + 10}%, ${lightness}%, ${GUIDE_ALPHA})`;
}
