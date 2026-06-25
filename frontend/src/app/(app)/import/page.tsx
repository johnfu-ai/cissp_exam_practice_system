"use client";

import { PageHeader } from "@/components/page-header";
import { RequirePermission } from "@/components/require-permission";
import { EmptyState } from "@/components/empty-state";
import { ImportWizard } from "@/features/import/import-wizard";

export default function ImportPage() {
  return (
    <div>
      <PageHeader
        title="Question import"
        description="Preview, validate, and commit question datasets. Imports run as a two-phase preview → commit with full rollback."
      />
      <RequirePermission
        perm="question:import"
        fallback={
          <EmptyState
            title="Import not available"
            description="You need the question import permission to use this page."
          />
        }
      >
        <ImportWizard />
      </RequirePermission>
    </div>
  );
}
