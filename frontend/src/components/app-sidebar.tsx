"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  BookOpen,
  Repeat,
  GraduationCap,
  BarChart3,
  Upload,
  FileText,
  FolderTree,
  Shield,
  Settings,
  LogOut,
} from "lucide-react";
import { useAuthStore } from "@/lib/auth-store";
import { BACKEND } from "@/lib/config";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

type NavKey = "dashboard" | "practice" | "review" | "exam" | "analytics";
type ManageKey = "import" | "questions" | "taxonomy";

const NAV: { href: string; key: NavKey; icon: typeof LayoutDashboard }[] = [
  { href: "/dashboard", key: "dashboard", icon: LayoutDashboard },
  { href: "/practice", key: "practice", icon: BookOpen },
  { href: "/review", key: "review", icon: Repeat },
  { href: "/exam", key: "exam", icon: GraduationCap },
  { href: "/analytics", key: "analytics", icon: BarChart3 },
];

// Management links, each shown only when the user holds the required permission.
const MANAGE: { href: string; key: ManageKey; icon: typeof Upload; perm: string }[] = [
  { href: "/import", key: "import", icon: Upload, perm: "question:import" },
  { href: "/questions", key: "questions", icon: FileText, perm: "question:read" },
  { href: "/taxonomy", key: "taxonomy", icon: FolderTree, perm: "admin:manage_taxonomy" },
];

export function AppSidebar() {
  const pathname = usePathname();
  const t = useT();
  const user = useAuthStore((s) => s.user);
  const perms = user?.perms ?? [];
  const isAdmin = perms.some((p) => p.startsWith("admin:"));
  const manageLinks = MANAGE.filter((m) => perms.includes(m.perm));
  const showManage = manageLinks.length > 0 || isAdmin;

  async function logout() {
    const { accessToken, refreshToken, clear } = useAuthStore.getState();
    if (refreshToken) {
      await fetch(`${BACKEND}/api/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken, access_token: accessToken }),
      }).catch(() => {});
    }
    clear();
    window.location.href = "/login";
  }

  function linkClass(active: boolean): string {
    return cn(
      "flex items-center gap-3 rounded-md h-11 px-3 py-2 text-sm font-medium transition-colors",
      active
        ? "bg-accent text-foreground"
        : "text-muted-foreground hover:bg-accent hover:text-foreground"
    );
  }

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r bg-card">
      <div className="px-5 py-4 text-lg font-semibold tracking-tight">{t("brand")}</div>
      <nav className="flex-1 space-y-1 overflow-y-auto px-3">
        {NAV.map(({ href, key, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link key={href} href={href} className={linkClass(active)}>
              <Icon className="h-4 w-4" />
              {t(`nav.${key}`)}
            </Link>
          );
        })}

        {showManage && (
          <div>
            <div className="my-2 h-px bg-border" />
            <div className="px-3 pb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground/70">
              {t("nav.manage")}
            </div>
            {manageLinks.map(({ href, key, icon: Icon }) => (
              <Link key={href} href={href} className={linkClass(pathname.startsWith(href))}>
                <Icon className="h-4 w-4" />
                {t(`nav.${key}`)}
              </Link>
            ))}
            {isAdmin && (
              <Link href="/admin" className={linkClass(pathname.startsWith("/admin"))}>
                <Shield className="h-4 w-4" />
                {t("nav.admin")}
              </Link>
            )}
          </div>
        )}
      </nav>
      <div className="border-t p-3">
        <div className="mb-2 px-2 text-sm">
          <div className="truncate font-medium">{user?.display_name || user?.email}</div>
          <div className="truncate text-xs text-muted-foreground">{user?.email}</div>
        </div>
        <Link
          href="/settings"
          className={cn(
            "mb-1 flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
            pathname === "/settings"
              ? "bg-accent text-foreground"
              : "text-muted-foreground hover:bg-accent hover:text-foreground"
          )}
        >
          <Settings className="h-4 w-4" />
          {t("nav.settings")}
        </Link>
        <Button variant="ghost" size="sm" className="w-full justify-start" onClick={logout}>
          <LogOut className="h-4 w-4" />
          {t("nav.logout")}
        </Button>
      </div>
    </aside>
  );
}
