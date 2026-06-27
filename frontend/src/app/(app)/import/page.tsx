"use client";

import { PageHeader } from "@/components/page-header";
import { RequirePermission } from "@/components/require-permission";
import { EmptyState } from "@/components/empty-state";
import { ImportWizard } from "@/features/import/import-wizard";
import { useT } from "@/lib/i18n/provider";

export default function ImportPage() {
  const t = useT();
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader
        eyebrow={t("importPage.eyebrow")}
        title={t("importPage.title")}
        description={t("importPage.description")}
      />
      <RequirePermission
        perm="question:import"
        fallback={
          <EmptyState
            title={t("importPage.notAvailable")}
            description={t("importPage.notAvailableDesc")}
          />
        }
      >
        <ImportWizard />
      </RequirePermission>
    </div>
  );
}
