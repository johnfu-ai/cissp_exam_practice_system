import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { RequirePermission } from "@/components/require-permission";
import { useAuthStore } from "@/lib/auth-store";

beforeEach(() => {
  useAuthStore.setState({
    user: { id: "1", email: "a@b.c", display_name: null, roles: [], perms: ["practice:read"], language_mode: "en" },
    accessToken: "t",
    refreshToken: "r",
    hydrated: true,
  });
});

describe("RequirePermission", () => {
  it("renders children when the perm is present", () => {
    render(
      <RequirePermission perm="practice:read">
        <span>visible</span>
      </RequirePermission>
    );
    expect(screen.getByText("visible")).toBeInTheDocument();
  });

  it("renders fallback when the perm is absent", () => {
    render(
      <RequirePermission perm="admin:manage_users" fallback={<span>denied</span>}>
        <span>secret</span>
      </RequirePermission>
    );
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
    expect(screen.getByText("denied")).toBeInTheDocument();
  });
});
