"use client";

import { useMemo } from "react";
import { PageHeader } from "@/components/page-header";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { EmptyState } from "@/components/empty-state";
import { useAuthStore } from "@/lib/auth-store";
import { useT } from "@/lib/i18n/provider";
import {
  UsersTab, ClassesTab, CatParamsTab, QualityTab, AuditTab, ReportsTab,
} from "@/features/admin/tabs";

export default function AdminPage() {
  const t = useT();
  const perms = useAuthStore((s) => s.user?.perms ?? []);

  const tabs = useMemo(
    () =>
      [
        { value: "users", label: t("admin.tabUsers"), perm: "admin:manage_users", el: <UsersTab /> },
        { value: "classes", label: t("admin.tabClasses"), perm: "admin:manage_users", el: <ClassesTab /> },
        { value: "cat", label: t("admin.tabCat"), perm: "admin:manage_taxonomy", el: <CatParamsTab /> },
        { value: "quality", label: t("admin.tabQuality"), perm: "question:publish", el: <QualityTab /> },
        { value: "audit", label: t("admin.tabAudit"), perm: "admin:view_audit", el: <AuditTab /> },
        { value: "reports", label: t("admin.tabReports"), perm: "admin:view_reports", el: <ReportsTab /> },
      ].filter((tab) => perms.includes(tab.perm)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [perms, t]
  );

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader
        eyebrow={t("admin.eyebrow")}
        title={t("admin.title")}
        description={t("admin.description")}
      />
      {tabs.length === 0 ? (
        <EmptyState title={t("admin.noAccess")} description={t("admin.noAccessDesc")} />
      ) : (
        <Tabs defaultValue={tabs[0].value}>
          <TabsList>
            {tabs.map((tab) => <TabsTrigger key={tab.value} value={tab.value}>{tab.label}</TabsTrigger>)}
          </TabsList>
          {tabs.map((tab) => <TabsContent key={tab.value} value={tab.value}>{tab.el}</TabsContent>)}
        </Tabs>
      )}
    </div>
  );
}
