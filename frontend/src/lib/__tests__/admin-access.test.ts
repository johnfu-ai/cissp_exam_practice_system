import { describe, it, expect } from "vitest";
import { hasAdminPortalAccess, firstAdminRoute } from "../admin-access";

describe("hasAdminPortalAccess", () => {
  it("is false for empty / learner-only perms", () => {
    expect(hasAdminPortalAccess(undefined)).toBe(false);
    expect(hasAdminPortalAccess([])).toBe(false);
    expect(hasAdminPortalAccess(["practice:read", "exam:read"])).toBe(false);
  });

  it("is true for any listed portal perm or admin:*", () => {
    expect(hasAdminPortalAccess(["question:read"])).toBe(true);
    expect(hasAdminPortalAccess(["question:write"])).toBe(true);
    expect(hasAdminPortalAccess(["admin:manage_users"])).toBe(true);
    expect(hasAdminPortalAccess(["admin:something_new"])).toBe(true);
  });
});

describe("firstAdminRoute", () => {
  it("picks the first matching manage route in order", () => {
    expect(firstAdminRoute(["question:read"])).toBe("/questions");
    expect(firstAdminRoute(["question:import", "question:read"])).toBe("/import");
    expect(firstAdminRoute(["admin:view_audit"])).toBe("/admin");
    expect(firstAdminRoute(["admin:manage_taxonomy", "admin:view_reports"])).toBe(
      "/taxonomy",
    );
  });

  it("returns null when no manage route matches", () => {
    expect(firstAdminRoute(["practice:read"])).toBe(null);
    expect(firstAdminRoute(["question:write"])).toBe(null);
  });
});
