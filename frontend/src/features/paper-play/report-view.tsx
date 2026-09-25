"use client";

// Paper exam report + unified review (PRD v1.4 FR-PAPER-06 / FR-ESSAY-03):
// raw paper score, pass line, wrong list, per-question review with essay
// reference answers + post-finish self-assessment.

import { useState } from "react";
import Link from "next/link";
import { useT } from "@/lib/i18n/provider";
import { usePreferences } from "@/lib/api/preferences";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Loading } from "@/components/loading";
import { enumLabel } from "@/features/shared/enum-label";
import {
  useExamReport,
  useExamReview,
  useExamSelfAssess,
} from "@/lib/api/sessions";
import { localizedText } from "@/components/bilingual-text";
import type { LanguageMode } from "@/lib/api/types";

export function PaperReportView({ sessionId }: { sessionId: string }) {
  const t = useT();
  const { data: prefs } = usePreferences();
  const mode: LanguageMode = prefs?.language_mode ?? "en";
  const report = useExamReport(sessionId);
  const review = useExamReview(sessionId, !report.isLoading);
  const selfAssess = useExamSelfAssess(sessionId);
  const [openPosition, setOpenPosition] = useState<number | null>(null);

  if (report.isLoading) {
    return (
      <div className="p-8">
        <Loading label={t("common.loading")} />
      </div>
    );
  }

  const r = report.data;
  if (!r) {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-4 p-6">
        <p className="text-sm text-destructive">{t("error.generic")}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 p-6">
      <PageHeader eyebrow={t("paperPlay.examMode")} title={t("paperPlay.reportTitle")} />

      <Card className="space-y-3 p-6">
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-4xl font-semibold tabular-nums">
            {r.scaled_score}
          </span>
          <span className="text-muted-foreground">/ {r.max_score}</span>
          <Badge variant={r.passed ? "default" : "destructive"}>
            {r.passed ? t("paperPlay.passed") : t("paperPlay.failed")}
          </Badge>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
          <span>
            {t("paperPlay.correct")}: {r.correct_count}/{r.total_questions}
          </span>
          <span>
            {t("paperPlay.accuracy")}: {(r.accuracy * 100).toFixed(0)}%
          </span>
          <span>
            {t("papersPage.score", { score: r.passing_score })}
          </span>
        </div>
        <Button asChild size="sm" variant="outline">
          <Link href="/papers">{t("paperPlay.backToPapers")}</Link>
        </Button>
      </Card>

      <div>
        <h2 className="mb-3 text-lg font-semibold">{t("paperPlay.reviewTitle")}</h2>
        {review.isLoading && (
          <div className="p-4">
            <Loading label={t("common.loading")} />
          </div>
        )}
        <div className="space-y-2">
          {(review.data ?? []).map((item) => {
            const open = openPosition === item.position;
            const isEssay = item.question_type === "essay";
            const assessed = item.your_answer?.is_correct != null;
            return (
              <Card key={item.position} className="p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">
                      {enumLabel(t, "qType", item.question_type as never)}
                    </Badge>
                    <span className="text-sm font-medium">
                      {t("paperPlay.question", {
                        n: item.position + 1,
                        total: review.data?.length ?? 0,
                      })}
                    </span>
                    {item.your_answer && (
                      <Badge
                        variant={
                          item.your_answer.is_correct === true
                            ? "default"
                            : item.your_answer.is_correct === false
                              ? "destructive"
                              : "secondary"
                        }
                      >
                        {item.your_answer.is_correct === true
                          ? t("paperPlay.correct")
                          : item.your_answer.is_correct === false
                            ? t("paperPlay.incorrect")
                            : "—"}
                      </Badge>
                    )}
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setOpenPosition(open ? null : item.position)}
                    aria-expanded={open}
                  >
                    {open
                      ? t("paperPlay.hideAnswer")
                      : t("paperPlay.showAnswer")}
                  </Button>
                </div>
                <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                  {localizedText(mode, item.stem)}
                </p>

                {open && (
                  <div className="mt-3 space-y-3 border-t pt-3 text-sm">
                    <div>{localizedText(mode, item.stem)}</div>
                    {item.options.map((o) => (
                      <div
                        key={o.order_index}
                        className={`rounded border p-2 ${
                          o.is_correct
                            ? "border-success bg-success/10"
                            : "border-transparent"
                        }`}
                      >
                        <span className="mr-2 font-semibold">
                          {String.fromCharCode(65 + o.order_index)}.
                        </span>
                        {localizedText(mode, o.content)}
                        {(o.explanation.en || o.explanation.zh) && (
                          <div className="mt-1 text-xs text-muted-foreground">
                            {localizedText(mode, o.explanation)}
                          </div>
                        )}
                      </div>
                    ))}
                    {isEssay && (
                      <div className="space-y-2">
                        {item.your_answer?.text && (
                          <div>
                            <div className="font-medium">
                              {t("paperPlay.yourText")}
                            </div>
                            <p className="text-muted-foreground">
                              {item.your_answer.text}
                            </p>
                          </div>
                        )}
                        {item.reference_answer &&
                          (item.reference_answer.en || item.reference_answer.zh) && (
                            <div>
                              <div className="font-medium">
                                {t("paperPlay.referenceAnswer")}
                              </div>
                              <p>{localizedText(mode, item.reference_answer)}</p>
                            </div>
                          )}
                        {!assessed && (
                          <div className="flex items-center gap-2">
                            <span className="text-muted-foreground">
                              {t("paperPlay.pendingSelfAssess")}
                            </span>
                            <Button
                              size="sm"
                              onClick={() =>
                                selfAssess.mutate({
                                  position: item.position,
                                  correct: true,
                                })
                              }
                            >
                              {t("paperPlay.iWasRight")}
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                selfAssess.mutate({
                                  position: item.position,
                                  correct: false,
                                })
                              }
                            >
                              {t("paperPlay.iWasWrong")}
                            </Button>
                          </div>
                        )}
                      </div>
                    )}
                    {(item.correct_rationale.en || item.correct_rationale.zh) && (
                      <div>
                        <div className="font-medium">{t("paperPlay.rationale")}</div>
                        <p className="text-muted-foreground">
                          {localizedText(mode, item.correct_rationale)}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
