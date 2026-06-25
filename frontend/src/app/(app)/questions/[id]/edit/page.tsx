"use client";

import { PageHeader } from "@/components/page-header";
import { QuestionEditor } from "@/features/questions/editor";
import { useQuestionDetail } from "@/lib/api/questions";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";

export default function EditQuestionPage({ params }: { params: { id: string } }) {
  const detail = useQuestionDetail(params.id);
  if (detail.isLoading) return <Loading label="Loading question…" />;
  if (detail.isError || !detail.data) return <ErrorState message="Could not load this question." />;
  return (
    <div>
      <PageHeader title="Edit question" crumbs={["Questions"]} description={`v${detail.data.version}`} />
      <QuestionEditor initial={detail.data} />
    </div>
  );
}
