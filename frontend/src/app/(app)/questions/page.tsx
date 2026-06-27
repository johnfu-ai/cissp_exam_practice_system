"use client";

import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { RequirePermission } from "@/components/require-permission";
import { QuestionList } from "@/features/questions/list";
import { useT } from "@/lib/i18n/provider";

export default function QuestionsPage() {
  const t = useT();
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader
        eyebrow={t("questions.eyebrow")}
        title={t("questions.title")}
        description={t("questions.description")}
        actions={
          <RequirePermission perm="question:write">
            <Button asChild size="pill">
              <Link href="/questions/new">{t("questions.newQuestion")}</Link>
            </Button>
          </RequirePermission>
        }
      />
      <QuestionList />
    </div>
  );
}
