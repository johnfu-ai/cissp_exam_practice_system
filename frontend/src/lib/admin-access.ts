/** Permissions that unlock the Next.js admin portal (FR-CLIENT-03/06). */
const PORTAL_PERMS = new Set([
  "question:import",
  "question:read",
  "question:write",
  "question:publish",
  "admin:manage_taxonomy",
  "admin:manage_users",
  "admin:view_audit",
  "admin:view_reports",
]);

const MANAGE_ROUTES: { href: string; match: (perms: string[]) => boolean }[] = [
  { href: "/import", match: (p) => p.includes("question:import") },
  { href: "/questions", match: (p) => p.includes("question:read") },
  { href: "/taxonomy", match: (p) => p.includes("admin:manage_taxonomy") },
  { href: "/admin", match: (p) => p.some((x) => x.startsWith("admin:")) },
];

export function hasAdminPortalAccess(perms: string[] | null | undefined): boolean {
  if (!perms?.length) return false;
  return perms.some((p) => PORTAL_PERMS.has(p) || p.startsWith("admin:"));
}

/** First manage route the user can open, or null if none. */
export function firstAdminRoute(perms: string[] | null | undefined): string | null {
  if (!perms?.length) return null;
  return MANAGE_ROUTES.find((r) => r.match(perms))?.href ?? null;
}
