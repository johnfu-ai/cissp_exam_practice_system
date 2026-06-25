"use client";

import { useMemo } from "react";
import { PageHeader } from "@/components/page-header";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { EmptyState } from "@/components/empty-state";
import { useAuthStore } from "@/lib/auth-store";
import {
  UsersTab, ClassesTab, CatParamsTab, QualityTab, AuditTab, ReportsTab,
} from "@/features/admin/tabs";

export default function AdminPage() {
  const perms = useAuthStore((s) => s.user?.perms ?? []);

  const tabs = useMemo(
    () =>
      [
        { value: "users", label: "Users", perm: "admin:manage_users", el: <UsersTab /> },
        { value: "classes", label: "Classes", perm: "admin:manage_users", el: <ClassesTab /> },
        { value: "cat", label: "CAT params", perm: "admin:manage_taxonomy", el: <CatParamsTab /> },
        { value: "quality", label: "Quality", perm: "question:publish", el: <QualityTab /> },
        { value: "audit", label: "Audit log", perm: "admin:view_audit", el: <AuditTab /> },
        { value: "reports", label: "Reports", perm: "admin:view_reports", el: <ReportsTab /> },
      ].filter((t) => perms.includes(t.perm)),
    [perms]
  );

  return (
    <div>
      <PageHeader title="Admin" description="User, class, CAT-parameter, content-quality, audit, and reporting administration." />
      {tabs.length === 0 ? (
        <EmptyState title="No admin access" description="Your account has no administrative permissions." />
      ) : (
        <Tabs defaultValue={tabs[0].value}>
          <TabsList>
            {tabs.map((t) => <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>)}
          </TabsList>
          {tabs.map((t) => <TabsContent key={t.value} value={t.value}>{t.el}</TabsContent>)}
        </Tabs>
      )}
    </div>
  );
}
