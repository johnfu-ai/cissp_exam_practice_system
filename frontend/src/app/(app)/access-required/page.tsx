"use client";

import Link from "next/link";
import { ShieldAlert } from "lucide-react";
import { useT } from "@/lib/i18n/provider";
import { useAuthStore } from "@/lib/auth-store";
import { BACKEND } from "@/lib/config";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/page-header";

export default function AccessRequiredPage() {
  const t = useT();

  async function logout() {
    const { accessToken, clear } = useAuthStore.getState();
    await fetch(`${BACKEND}/api/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ access_token: accessToken }),
      credentials: "include",
    }).catch(() => {});
    clear();
    window.location.href = "/login";
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <PageHeader
        eyebrow={t("accessRequired.eyebrow")}
        title={t("accessRequired.title")}
        description={t("accessRequired.description")}
      />
      <Card>
        <CardHeader>
          <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-muted">
            <ShieldAlert className="h-5 w-5 text-muted-foreground" />
          </div>
          <CardTitle className="text-base">{t("accessRequired.cardTitle")}</CardTitle>
          <CardDescription>{t("accessRequired.cardDesc")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Button asChild variant="outline" size="pill">
            <Link href="/settings">{t("nav.settings")}</Link>
          </Button>
          <Button variant="ghost" size="pill" onClick={logout}>
            {t("nav.logout")}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
