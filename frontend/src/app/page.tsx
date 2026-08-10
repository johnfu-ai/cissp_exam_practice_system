"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useHydratedAuth } from "@/lib/use-hydrated-auth";
import { firstAdminRoute, hasAdminPortalAccess } from "@/lib/admin-access";
import { Loading } from "@/components/loading";
import { useT } from "@/lib/i18n/provider";

export default function Home() {
  const { hydrated, accessToken, user } = useHydratedAuth();
  const router = useRouter();
  const t = useT();

  useEffect(() => {
    if (!hydrated) return;
    if (!accessToken) {
      router.replace("/login");
      return;
    }
    const perms = user?.perms ?? [];
    if (!hasAdminPortalAccess(perms)) {
      router.replace("/access-required");
      return;
    }
    router.replace(firstAdminRoute(perms) ?? "/access-required");
  }, [hydrated, accessToken, user, router]);

  return (
    <div className="p-8">
      <Loading label={t("common.loading")} />
    </div>
  );
}
