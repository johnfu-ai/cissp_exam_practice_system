"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useHydratedAuth } from "@/lib/use-hydrated-auth";
import { Loading } from "@/components/loading";
import { useT } from "@/lib/i18n/provider";

export default function Home() {
  const { hydrated, accessToken } = useHydratedAuth();
  const router = useRouter();
  const t = useT();

  useEffect(() => {
    if (!hydrated) return;
    router.replace(accessToken ? "/dashboard" : "/login");
  }, [hydrated, accessToken, router]);

  return (
    <div className="p-8">
      <Loading label={t("common.loading")} />
    </div>
  );
}
