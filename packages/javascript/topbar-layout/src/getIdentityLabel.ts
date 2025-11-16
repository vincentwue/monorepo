import type { UseSessionResult } from "@monorepo/auth";

/**
 * Safely extract a display label for the identity.
 * - Prefer name (first + last)
 * - Then username
 * - Then email
 * - Fallback to "Settings"
 */
export function getIdentityLabel(
  session: UseSessionResult["session"],
): string {
  const fallback = "Settings";

  if (!session || typeof session !== "object") return fallback;

  const identity = (session as Record<string, unknown> | null)?.identity;
  if (!identity || typeof identity !== "object") return fallback;

  const traits = (identity as Record<string, unknown>).traits;
  if (!traits || typeof traits !== "object") return fallback;

  const traitsRecord = traits as Record<string, unknown>;

  // email
  const email = getString(traitsRecord["email"]);
  // username
  const username = getString(traitsRecord["username"]);

  // composed name
  const nameField = traitsRecord["name"];
  let composedName: string | undefined;

  if (nameField && typeof nameField === "object") {
    const record = nameField as Record<string, unknown>;
    const first = getString(record["first"]);
    const last = getString(record["last"]);
    const combined = [first, last].filter(Boolean).join(" ").trim();
    if (combined.length > 0) {
      composedName = combined;
    }
  }

  return composedName ?? username ?? email ?? fallback;
}

function getString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim().length > 0
    ? value
    : undefined;
}
