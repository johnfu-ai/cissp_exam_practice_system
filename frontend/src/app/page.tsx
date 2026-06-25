"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useHydratedAuth } from "@/lib/use-hydrated-auth";
import { Loading } from "@/components/loading";

export default function Home() {
  const { hydrated, accessToken } = useHydratedAuth();
  const router = useRouter();

  useEffect(() => {
    if (!hydrated) return;
    router.replace(accessToken ? "/dashboard" : "/login");
  }, [hydrated, accessToken, router]);

  return (
    <div className="p-8">
      <Loading label="Loading…" />
    </div>
  );
}
