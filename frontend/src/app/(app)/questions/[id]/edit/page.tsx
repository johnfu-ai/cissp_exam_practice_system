"use client";

import { use } from "react";
import { PageHeader } from "@/components/page-header";
import { QuestionEditor } from "@/features/questions/editor";
import { useQuestionDetail } from "@/lib/api/questions";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { useT } from "@/lib/i18n/provider";

export default function EditQuestionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const t = useT();
  const { id } = use(params);
  const detail = useQuestionDetail(id);
  if (detail.isLoading) return <Loading label={t("questions.loadingQuestion")} />;
  if (detail.isError || !detail.data)
    return <ErrorState message={t("questions.loadFailedQuestion")} />;
  return (
    <div>
      <PageHeader
        eyebrow={t("questions.eyebrow")}
        title={t("questions.editTitle")}
        crumbs={[t("questions.title")]}
        description={t("questions.versionDesc", { n: detail.data.version })}
      />
      <QuestionEditor initial={detail.data} />
    </div>
  );
}
