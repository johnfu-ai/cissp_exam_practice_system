"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useHydratedAuth } from "@/lib/use-hydrated-auth";
import { Loading } from "@/components/loading";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { hydrated, accessToken } = useHydratedAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (hydrated && !accessToken) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [hydrated, accessToken, router, pathname]);

  if (!hydrated || !accessToken) {
    return (
      <div className="p-8">
        <Loading label="Loading…" />
      </div>
    );
  }
  return <>{children}</>;
}
