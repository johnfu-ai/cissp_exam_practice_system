/** Admin-portal permissions + route gating (FR-CLIENT-03/06, PRD v1.4).

 * v1.4: the web app carries BOTH the learner flow (papers / paper player /
 * wrong book) and the admin portal. Every authenticated user may use the
 * learner routes; the manage routes below stay permission-gated. */
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

export const MANAGE_ROUTE_PREFIXES = ["/import", "/questions", "/taxonomy", "/admin"];

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

/** True when the path belongs to the permission-gated admin area. */
export function isManageRoute(pathname: string): boolean {
  return MANAGE_ROUTE_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );
}
