"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useHydratedAuth } from "@/lib/use-hydrated-auth";
import { hasAdminPortalAccess, isManageRoute } from "@/lib/admin-access";
import { Loading } from "@/components/loading";
import { useT } from "@/lib/i18n/provider";

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
    // v1.4: learners use the web app too — keep them out of ONLY the
    // permission-gated manage routes, sending them to the paper library.
    if (user && !hasAdminPortalAccess(user.perms) && isManageRoute(pathname)) {
      router.replace("/papers");
    }
  }, [hydrated, accessToken, user, router, pathname]);

  if (!hydrated || !accessToken) {
    return (
      <div className="p-8">
        <Loading label={t("common.loading")} />
      </div>
    );
  }

  if (user && !hasAdminPortalAccess(user.perms) && isManageRoute(pathname)) {
    return (
      <div className="p-8">
        <Loading label={t("common.loading")} />
      </div>
    );
  }

  return <>{children}</>;
}
