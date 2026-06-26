"use client";

import Link from "next/link";
import { useExamReport, useExamSession } from "@/lib/api/exam";
import { localizedText } from "@/components/bilingual-text";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { fmtDuration, fmtPct, accuracyColor } from "@/features/analytics/format";
import { readinessLabel } from "./format";
import type { LanguageMode } from "@/lib/api/types";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-normal text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent className="text-2xl font-semibold">{value}</CardContent>
    </Card>
  );
}

export function ExamReport({ sessionId }: { sessionId: string }) {
  const report = useExamReport(sessionId);
  const session = useExamSession(sessionId);

  if (report.isLoading) return <Loading label="Loading report…" />;
  if (report.isError || !report.data) {
    return <ErrorState message="Could not load the exam report. It may not be finished yet." />;
  }
  const r = report.data;
  const isCat = r.ability_estimate != null;
  // Render wrong-question stems in the language mode the exam was taken in.
  // `language_mode` is frozen into the session config at creation; fall back to
  // English if it is missing.
  const mode: LanguageMode =
    (session.data?.config?.language_mode as LanguageMode | undefined) ?? "en";

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="Exam report"
        description={isCat ? "Adaptive (CAT) mock exam result" : "Fixed mock exam result"}
        actions={
          <div className="flex gap-2">
            <Button asChild variant="outline">
              <Link href={`/exam/sessions/${sessionId}/review`}>Review answers</Link>
            </Button>
            <Button asChild>
              <Link href="/exam">New exam</Link>
            </Button>
          </div>
        }
      />

      <div className="mb-6 flex items-center gap-3">
        <Badge variant={r.passed ? "success" : "destructive"} className="text-sm">
          {r.passed ? "PASS" : "FAIL"}
        </Badge>
        <span className="text-sm text-muted-foreground">
          {r.scaled_score} / {r.max_score} (passing {r.passing_score})
        </span>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Scaled score" value={`${r.scaled_score}`} />
        <Stat label="Accuracy" value={fmtPct(r.accuracy)} />
        <Stat label="Answered" value={`${r.correct_count}/${r.answered_count}`} />
        <Stat label="Total time" value={fmtDuration(r.total_time_ms)} />
      </div>

      {isCat && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Adaptive estimate</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <Badge variant="secondary">Readiness: {readinessLabel(r.readiness_level)}</Badge>
              <span className="text-muted-foreground">
                Ability θ {r.ability_estimate?.toFixed(2)} (95% CI {r.ability_ci_lower?.toFixed(2)} –{" "}
                {r.ability_ci_upper?.toFixed(2)}, SEM {r.sem?.toFixed(2)})
              </span>
            </div>
            {r.disclaimer && (
              <Alert>
                <AlertTitle>Study tool — not an official score</AlertTitle>
                <AlertDescription>{r.disclaimer}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>By domain</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {r.domains.length === 0 && <p className="text-sm text-muted-foreground">No domain data.</p>}
          {r.domains.map((d, i) => (
            <div key={d.domain_id ?? `none-${i}`} className="space-y-1">
              <div className="flex items-center justify-between text-sm">
                <span>{d.domain_name ?? "Unmapped"}</span>
                <span className="text-muted-foreground">
                  {d.answered === 0 ? "—" : `${fmtPct(d.accuracy)} (${d.correct}/${d.answered})`}
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div className={`h-full ${accuracyColor(d.accuracy)}`} style={{ width: `${Math.round(d.accuracy * 100)}%` }} />
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Wrong questions ({r.wrong_questions.length})</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {r.wrong_questions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No wrong answers — excellent.</p>
          ) : (
            r.wrong_questions.map((w) => (
              <div key={w.question_id} className="rounded-md border p-3">
                <p className="text-sm">{localizedText(mode, w.stem)}</p>
                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                  <Badge variant="destructive">Your answer: {w.selected_indexes.join(", ") || "—"}</Badge>
                  <Badge variant="success">Correct: {w.correct_indexes.join(", ")}</Badge>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
