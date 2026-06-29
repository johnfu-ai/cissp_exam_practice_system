"use client";

import { useExamSession } from "@/lib/api/exam";
import { FixedExamRunner } from "./fixed-runner";
import { CatExamRunner } from "./cat-runner";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { useT } from "@/lib/i18n/provider";

export function ExamRunner({ sessionId }: { sessionId: string }) {
  const t = useT();
  const session = useExamSession(sessionId);

  if (session.isLoading) return <Loading label={t("examRunnerPage.loadingExam")} />;
  if (session.isError || !session.data) {
    return <ErrorState message={t("examRunnerPage.loadFailed")} />;
  }
  const s = session.data;

  // A finished/expired session has no live delivery — send the user to the report.
  if (s.status !== "in_progress") {
    if (typeof window !== "undefined") {
      window.location.replace(`/exam/sessions/${sessionId}/report`);
    }
    return <Loading label={t("examRunnerPage.loadingReport")} />;
  }

  if (s.session_kind === "cat") {
    return <CatExamRunner sessionId={sessionId} session={s} />;
  }
  return <FixedExamRunner sessionId={sessionId} session={s} />;
}
