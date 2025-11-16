import Split from "react-split";
import type { ReactNode } from "react";

export interface SplitLayoutProps {
  direction?: "horizontal" | "vertical"; // horizontal: left/right, vertical: top/bottom
  minSize?: number | number[];
  sizes?: number[]; // initial sizes in %
  gutterSize?: number;
  className?: string;
  children: [ReactNode, ReactNode]; // exactly two panels
  onDragEnd?: (sizes: number[]) => void;
}

export function SplitLayout({
  direction = "horizontal",
  minSize = 150,
  sizes = [50, 50],
  gutterSize = 6,
  className,
  children,
  onDragEnd,
}: SplitLayoutProps) {
  return (
    <Split
      className={className}
      direction={direction}
      minSize={minSize}
      sizes={sizes}
      gutterSize={gutterSize}
      onDragEnd={onDragEnd}
    >
      {children[0]}
      {children[1]}
    </Split>
  );
}
