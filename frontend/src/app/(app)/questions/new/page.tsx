"use client";

import { PageHeader } from "@/components/page-header";
import { QuestionEditor } from "@/features/questions/editor";
import { useT } from "@/lib/i18n/provider";

export default function NewQuestionPage() {
  const t = useT();
  return (
    <div>
      <PageHeader
        eyebrow={t("questions.eyebrow")}
        title={t("questions.newTitle")}
        crumbs={[t("questions.title")]}
        description={t("questions.newDesc")}
      />
      <QuestionEditor />
    </div>
  );
}
