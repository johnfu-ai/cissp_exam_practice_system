"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useQueries } from "@tanstack/react-query";
import { apiJson, ApiError } from "@/lib/api";
import { qk } from "@/lib/api/keys";
import { useExamHistory } from "@/lib/api/exam";
import type { ExamSession } from "@/lib/api/types";
import { getTrackedExamIds, untrackExam } from "./exam-tracker";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import { fmtDate } from "@/features/analytics/format";
import { useT } from "@/lib/i18n/provider";

function fmtPct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

export function ExamHistoryPanel() {
  const t = useT();
  const [ids, setIds] = useState<string[]>([]);
  useEffect(() => setIds(getTrackedExamIds()), []);

  const results = useQueries({
    queries: ids.map((id) => ({
      queryKey: qk.exam.session(id),
      queryFn: () => apiJson<ExamSession>(`/api/exam/sessions/${id}`),
      retry: false,
    })),
  });

  useEffect(() => {
    results.forEach((r, i) => {
      const id = ids[i];
      if (!id) return;
      if (r.isError && r.error instanceof ApiError && r.error.status === 404) untrackExam(id);
      if (r.data && r.data.status !== "in_progress") untrackExam(id);
    });
  }, [results, ids]);

  const active = useMemo(
    () =>
      results
        .map((r) => r.data)
        .filter((s): s is ExamSession => !!s && s.status === "in_progress"),
    [results]
  );

  const history = useExamHistory();

  return (
    <div className="space-y-6">
      {active.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-medium text-muted-foreground">{t("examHistory.inProgress")}</h3>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {active.map((s) => (
              <Card key={s.id} hover>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="text-base">
                    {s.session_kind === "cat" ? t("examHistory.catExam") : t("examHistory.fixedExam")}
                  </CardTitle>
                  <Badge variant="secondary">{t("examHistory.inProgress")}</Badge>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm text-muted-foreground tabular-nums">
                    {s.total_questions > 0 ? t("examHistory.nQuestions", { n: s.total_questions }) : t("examHistory.adaptive")}
                  </p>
                  <Button asChild size="sm">
                    <Link href={`/exam/sessions/${s.id}`}>{t("examHistory.resume")}</Link>
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      <div>
        <h3 className="mb-3 text-sm font-medium text-muted-foreground">{t("examHistory.completed")}</h3>
        {history.isLoading && <p className="text-sm text-muted-foreground">{t("examHistory.loading")}</p>}
        {history.data && history.data.length === 0 && active.length === 0 && (
          <EmptyState
            title={t("examHistory.noExams")}
            description={t("examHistory.noExamsDesc")}
          />
        )}
        {history.data && history.data.length > 0 && (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/40 text-left text-muted-foreground">
                  <th className="px-4 py-2 font-medium">{t("examHistory.colDate")}</th>
                  <th className="px-4 py-2 font-medium">{t("examHistory.colQuestions")}</th>
                  <th className="px-4 py-2 font-medium">{t("examHistory.colScore")}</th>
                  <th className="px-4 py-2 font-medium">{t("examHistory.colAccuracy")}</th>
                  <th className="px-4 py-2 font-medium">{t("examHistory.colResult")}</th>
                  <th className="px-4 py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {history.data.map((h) => (
                  <tr key={h.id} className="border-b transition-colors hover:bg-accent/50 last:border-0">
                    <td className="px-4 py-2.5 tabular-nums">{fmtDate(h.started_at)}</td>
                    <td className="px-4 py-2.5 tabular-nums">
                      {h.correct_count}/{h.total_questions}
                    </td>
                    <td className="px-4 py-2.5 tabular-nums">
                      {h.scaled_score}/{h.max_score}
                    </td>
                    <td className="px-4 py-2.5 tabular-nums">{fmtPct(h.accuracy)}</td>
                    <td className="px-4 py-2.5">
                      <Badge variant={h.passed ? "success" : "destructive"}>
                        {h.passed ? t("examHistory.pass") : t("examHistory.fail")}
                      </Badge>
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <Button asChild variant="ghost" size="sm">
                        <Link href={`/exam/sessions/${h.id}/report`}>{t("examHistory.viewReport")}</Link>
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
