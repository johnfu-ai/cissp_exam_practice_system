"use client";

import type { ReactNode } from "react";
import { useAuthStore } from "@/lib/auth-store";

export function RequirePermission({
  perm,
  fallback = null,
  children,
}: {
  perm: string;
  fallback?: ReactNode;
  children: ReactNode;
}) {
  const perms = useAuthStore((s) => s.user?.perms ?? []);
  if (!perms.includes(perm)) return <>{fallback}</>;
  return <>{children}</>;
}
