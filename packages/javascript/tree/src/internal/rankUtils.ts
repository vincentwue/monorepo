// simple helpers to generate fractional rank values between siblings

export function computeMiddleRank(a: number, b: number): number {
  return (a + b) / 2;
}

export function computeRankAfter(a: number): number {
  return a + 100;
}

export function computeRankBefore(a: number): number {
  return a - 100;
}
