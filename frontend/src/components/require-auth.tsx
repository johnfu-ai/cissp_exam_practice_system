"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useHydratedAuth } from "@/lib/use-hydrated-auth";
import { hasAdminPortalAccess } from "@/lib/admin-access";
import { Loading } from "@/components/loading";
import { useT } from "@/lib/i18n/provider";

const ALLOWED_WITHOUT_ADMIN = new Set(["/settings", "/access-required"]);

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { hydrated, accessToken, user } = useHydratedAuth();
  const router = useRouter();
  const pathname = usePathname();
  const t = useT();

  useEffect(() => {
    if (!hydrated) return;
    if (!accessToken) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    if (
      user &&
      !hasAdminPortalAccess(user.perms) &&
      !ALLOWED_WITHOUT_ADMIN.has(pathname)
    ) {
      router.replace("/access-required");
    }
  }, [hydrated, accessToken, user, router, pathname]);

  if (!hydrated || !accessToken) {
    return (
      <div className="p-8">
        <Loading label={t("common.loading")} />
      </div>
    );
  }

  if (
    user &&
    !hasAdminPortalAccess(user.perms) &&
    !ALLOWED_WITHOUT_ADMIN.has(pathname)
  ) {
    return (
      <div className="p-8">
        <Loading label={t("common.loading")} />
      </div>
    );
  }

  return <>{children}</>;
}
