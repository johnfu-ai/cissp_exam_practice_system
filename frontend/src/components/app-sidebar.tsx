"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, BookOpen, GraduationCap, BarChart3, Shield, LogOut } from "lucide-react";
import { useAuthStore } from "@/lib/auth-store";
import { BACKEND } from "@/lib/config";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, enabled: true },
  { href: "/practice", label: "Practice", icon: BookOpen, enabled: true },
  { href: "/exam", label: "Exam", icon: GraduationCap, enabled: false },
  { href: "/analytics", label: "Analytics", icon: BarChart3, enabled: true },
];

export function AppSidebar() {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const perms = user?.perms ?? [];
  const isAdmin = perms.some((p) => p.startsWith("admin:"));

  async function logout() {
    const { refreshToken, clear } = useAuthStore.getState();
    if (refreshToken) {
      await fetch(`${BACKEND}/api/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      }).catch(() => {});
    }
    clear();
    window.location.href = "/login";
  }

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r bg-card">
      <div className="px-5 py-4 text-lg font-semibold tracking-tight">CISSP Practice</div>
      <nav className="flex-1 space-y-1 px-3">
        {NAV.map(({ href, label, icon: Icon, enabled }) => {
          const active = pathname.startsWith(href);
          if (!enabled) {
            return (
              <span
                key={href}
                className="flex cursor-not-allowed items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground/60"
                title="Coming soon"
              >
                <Icon className="h-4 w-4" />
                {label}
                <span className="ml-auto text-xs">Soon</span>
              </span>
            );
          }
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active ? "bg-primary text-primary-foreground" : "hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
        {isAdmin && (
          <Link
            href="/admin"
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              pathname.startsWith("/admin")
                ? "bg-primary text-primary-foreground"
                : "hover:bg-accent hover:text-accent-foreground"
            )}
          >
            <Shield className="h-4 w-4" />
            Admin
          </Link>
        )}
      </nav>
      <div className="border-t p-3">
        <div className="mb-2 px-2 text-sm">
          <div className="truncate font-medium">{user?.display_name || user?.email}</div>
          <div className="truncate text-xs text-muted-foreground">{user?.email}</div>
        </div>
        <Button variant="ghost" size="sm" className="w-full justify-start" onClick={logout}>
          <LogOut className="h-4 w-4" />
          Log out
        </Button>
      </div>
    </aside>
  );
}
