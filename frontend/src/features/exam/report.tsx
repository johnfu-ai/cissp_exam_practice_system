"use client";

import Link from "next/link";
import { useExamReport, useExamSession } from "@/lib/api/exam";
import { localizedText } from "@/components/bilingual-text";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Eyebrow } from "@/components/eyebrow";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";
import { CheckCircle2, XCircle, Clock, Target, ListChecks } from "lucide-react";
import { fmtDuration, fmtPct, accuracyColor } from "@/features/analytics/format";
import { readinessLabel } from "./format";
import type { LanguageMode } from "@/lib/api/types";

export function ExamReport({ sessionId }: { sessionId: string }) {
  const t = useT();
  const report = useExamReport(sessionId);
  const session = useExamSession(sessionId);

  if (report.isLoading) return <Loading label={t("examReport.loadingReport")} />;
  if (report.isError || !report.data) {
    return <ErrorState message={t("examReport.loadFailed")} />;
  }
  const r = report.data;
  const isCat = r.ability_estimate != null;
  // Render wrong-question stems in the language mode the exam was taken in.
  // `language_mode` is frozen into the session config at creation; fall back to
  // English if it is missing.
  const mode: LanguageMode =
    (session.data?.config?.language_mode as LanguageMode | undefined) ?? "en";

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader
        eyebrow={t("exam.eyebrow")}
        title={t("examReport.title")}
        description={isCat ? t("examReport.descCat") : t("examReport.descFixed")}
        actions={
          <div className="flex gap-2">
            <Button asChild variant="outline">
              <Link href={`/exam/sessions/${sessionId}/review`}>{t("examReport.reviewAnswers")}</Link>
            </Button>
            <Button asChild size="pill">
              <Link href="/exam">{t("exam.newExam")}</Link>
            </Button>
          </div>
        }
      />

      {/* Score hero */}
      <Card>
        <CardContent className="p-6">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center">
            {/* Score ring (left) */}
            <div className="flex shrink-0 flex-col items-center">
              <div className="relative flex h-32 w-32 items-center justify-center rounded-full border-8 border-border">
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-3xl font-bold tabular-nums">{r.scaled_score}</span>
                  <span className="text-xs text-muted-foreground">{t("examReport.ofMax", { n: r.max_score })}</span>
                </div>
              </div>
              <Badge
                variant={r.passed ? "success" : "destructive"}
                className="mt-3 text-sm"
              >
                {r.passed ? t("examReport.pass") : t("examReport.fail")}
              </Badge>
              <p className="mt-2 text-center text-xs text-muted-foreground">
                {t("examReport.passing", { n: r.passing_score })}
              </p>
            </div>

            {/* Quick stats (right) */}
            <div className="grid flex-1 grid-cols-1 gap-3 sm:grid-cols-3">
              <StatTile
                icon={<ListChecks className="h-4 w-4" />}
                label={t("examReport.correct")}
                value={`${r.correct_count}/${r.answered_count}`}
                sub={fmtPct(r.accuracy)}
              />
              <StatTile
                icon={<Target className="h-4 w-4" />}
                label={t("examReport.accuracy")}
                value={fmtPct(r.accuracy)}
                sub={t("examReport.nAnswered", { n: r.answered_count })}
              />
              <StatTile
                icon={<Clock className="h-4 w-4" />}
                label={t("examReport.totalTime")}
                value={fmtDuration(r.total_time_ms)}
                sub={r.answered_count > 0 ? t("examReport.perQuestion", { t: fmtDuration(r.avg_time_ms) }) : undefined}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* CAT adaptive estimate */}
      {isCat && (
        <Card>
          <CardHeader>
            <Eyebrow>{t("examReport.adaptiveEstimate")}</Eyebrow>
            <CardTitle>{t("examReport.abilityReadiness")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Metric label={t("examReport.ability")} value={r.ability_estimate?.toFixed(2) ?? "—"} />
              <Metric label={t("examReport.ci")} value={
                r.ability_ci_lower != null && r.ability_ci_upper != null
                  ? `${r.ability_ci_lower.toFixed(2)} – ${r.ability_ci_upper.toFixed(2)}`
                  : "—"
              } />
              <Metric label={t("examReport.sem")} value={r.sem?.toFixed(2) ?? "—"} />
              <Metric label={t("examReport.readiness")} value={readinessLabel(t, r.readiness_level)} />
            </div>
            {r.disclaimer && (
              <Alert>
                <AlertTitle>{t("examReport.studyToolTitle")}</AlertTitle>
                <AlertDescription>{r.disclaimer}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {/* By domain */}
      <Card>
        <CardHeader>
          <Eyebrow>{t("examReport.breakdown")}</Eyebrow>
          <CardTitle>{t("examReport.byDomain")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {r.domains.length === 0 && <p className="text-sm text-muted-foreground">{t("examReport.noDomainData")}</p>}
          {r.domains.map((d, i) => (
            <div key={d.domain_id ?? `none-${i}`} className="space-y-1.5">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{d.domain_name ?? t("examReport.unmapped")}</span>
                <span className="text-muted-foreground tabular-nums">
                  {d.answered === 0 ? "—" : `${fmtPct(d.accuracy)} · ${d.correct}/${d.answered}`}
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className={cn("h-full rounded-full", accuracyColor(d.accuracy))}
                  style={{ width: `${Math.round(d.accuracy * 100)}%` }}
                />
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Wrong questions */}
      <Card>
        <CardHeader>
          <Eyebrow>{t("examReport.review")}</Eyebrow>
          <CardTitle>{t("examReport.wrongQuestions", { n: r.wrong_questions.length })}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {r.wrong_questions.length === 0 ? (
            <div className="flex items-center gap-2 rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success">
              <CheckCircle2 className="h-4 w-4" /> {t("examReport.noWrong")}
            </div>
          ) : (
            r.wrong_questions.map((w) => (
              <div
                key={w.question_id}
                className="space-y-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3"
              >
                <p className="text-sm leading-relaxed">{localizedText(mode, w.stem)}</p>
                <div className="flex flex-wrap gap-2 text-xs">
                  <Badge variant="destructive">
                    <XCircle className="mr-1 h-3 w-3" />
                    {t("examReport.yourAnswer")}: {w.selected_indexes.join(", ") || "—"}
                  </Badge>
                  <Badge variant="success">
                    <CheckCircle2 className="mr-1 h-3 w-3" />
                    {t("examReport.correctLabel")}: {w.correct_indexes.join(", ")}
                  </Badge>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatTile({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="flex items-start gap-3 rounded-lg border bg-accent/50 p-4">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
        {icon}
      </div>
      <div className="min-w-0">
        <p className="truncate text-xs text-muted-foreground">{label}</p>
        <p className="text-lg font-semibold tabular-nums">{value}</p>
        {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-muted/30 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-semibold tabular-nums">{value}</p>
    </div>
  );
}
