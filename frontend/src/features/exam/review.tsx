"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useExamReview, useExamSession } from "@/lib/api/exam";
import { BilingualText } from "@/components/bilingual-text";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Eyebrow } from "@/components/eyebrow";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { cn } from "@/lib/utils";
import { CheckCircle2, XCircle, MinusCircle } from "lucide-react";
import type { LanguageMode, Localized } from "@/lib/api/types";

const LANGUAGE_MODES: LanguageMode[] = ["en", "zh", "bilingual"];
const LANGUAGE_LABELS: Record<LanguageMode, string> = {
  en: "English",
  zh: "中文",
  bilingual: "Both",
};

/** True when a Localized slot carries any translatable content. */
function hasContent(loc: Localized | null | undefined): boolean {
  return !!loc && (loc.en != null || loc.zh != null);
}

function optionLetter(orderIndex: number): string {
  return String.fromCharCode(65 + orderIndex);
}

export function ExamReview({ sessionId }: { sessionId: string }) {
  const review = useExamReview(sessionId);
  const session = useExamSession(sessionId);

  // Default the display mode to the language mode the exam was taken in
  // (frozen into the session config at creation); allow the user to override.
  const [mode, setMode] = useState<LanguageMode>("en");
  useEffect(() => {
    const m = session.data?.config?.language_mode;
    if (m) setMode(m as LanguageMode);
  }, [session.data?.config?.language_mode]); // eslint-disable-line react-hooks/exhaustive-deps

  if (review.isLoading) return <Loading label="Loading review…" />;
  if (review.isError || !review.data) {
    return <ErrorState message="Could not load the exam review." />;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        eyebrow="Exam"
        title="Answer review"
        description={`${review.data.length} questions`}
        actions={
          <div className="flex items-center gap-2">
            <Select value={mode} onValueChange={(v) => setMode(v as LanguageMode)}>
              <SelectTrigger className="h-9 w-[130px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LANGUAGE_MODES.map((m) => (
                  <SelectItem key={m} value={m}>
                    {LANGUAGE_LABELS[m]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button asChild variant="outline">
              <Link href={`/exam/sessions/${sessionId}/report`}>Back to report</Link>
            </Button>
          </div>
        }
      />

      <div className="space-y-6">
        {review.data.map((item) => {
          const selected = item.your_answer?.selected ?? [];
          const correctSet = new Set(
            item.options.filter((o) => o.is_correct).map((o) => o.order_index),
          );
          const answered = item.your_answer != null && selected.length > 0;
          const isCorrect =
            answered &&
            selected.length === correctSet.size &&
            selected.every((i) => correctSet.has(i));

          return (
            <Card key={item.question_id}>
              <CardHeader>
                {/* Correctness banner */}
                <div
                  className={cn(
                    "flex items-center gap-3 rounded-lg border p-3",
                    !answered
                      ? "border-border bg-muted/40"
                      : isCorrect
                        ? "border-success/30 bg-success/10"
                        : "border-destructive/30 bg-destructive/10",
                  )}
                >
                  {!answered ? (
                    <MinusCircle className="h-5 w-5 shrink-0 text-muted-foreground" />
                  ) : isCorrect ? (
                    <CheckCircle2 className="h-5 w-5 shrink-0 text-success" />
                  ) : (
                    <XCircle className="h-5 w-5 shrink-0 text-destructive" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p
                      className={cn(
                        "text-sm font-semibold",
                        !answered
                          ? "text-muted-foreground"
                          : isCorrect
                            ? "text-success"
                            : "text-destructive",
                      )}
                    >
                      {!answered ? "Not answered" : isCorrect ? "Correct" : "Incorrect"}
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      Q{item.position + 1}
                      {item.time_spent_ms != null && (
                        <> · {Math.round(item.time_spent_ms / 1000)}s</>
                      )}
                    </p>
                  </div>
                </div>
                <CardTitle className="mt-3 text-base font-medium leading-relaxed">
                  <BilingualText mode={mode} en={item.stem.en} zh={item.stem.zh} />
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Per-option review */}
                <ul className="space-y-2">
                  {item.options.map((o) => {
                    const chosen = selected.includes(o.order_index);
                    const letter = optionLetter(o.order_index);
                    return (
                      <li
                        key={o.order_index}
                        className={cn(
                          "flex items-start gap-3 rounded-lg border p-3 text-sm",
                          o.is_correct && "border-success/50 bg-success/10",
                          chosen && !o.is_correct && "border-destructive/50 bg-destructive/10",
                          !o.is_correct && !chosen && "border-border",
                        )}
                      >
                        <span
                          className={cn(
                            "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold",
                            o.is_correct
                              ? "bg-success text-success-foreground"
                              : chosen
                                ? "bg-destructive text-destructive-foreground"
                                : "border border-border bg-background text-muted-foreground",
                          )}
                        >
                          {o.is_correct ? <CheckCircle2 className="h-3.5 w-3.5" /> : letter}
                        </span>
                        <BilingualText
                          mode={mode}
                          en={o.content.en}
                          zh={o.content.zh}
                          className="flex-1 pt-0.5"
                        />
                        {o.is_correct && (
                          <Badge variant="success" className="shrink-0">
                            Correct
                          </Badge>
                        )}
                        {chosen && !o.is_correct && (
                          <Badge variant="destructive" className="shrink-0">
                            Your pick
                          </Badge>
                        )}
                      </li>
                    );
                  })}
                </ul>

                {/* Explanation prose */}
                {hasContent(item.correct_rationale) && (
                  <div className="rounded-lg border border-border bg-muted/30 p-4">
                    <Eyebrow className="mb-2">Explanation</Eyebrow>
                    <BilingualText
                      mode={mode}
                      en={item.correct_rationale.en}
                      zh={item.correct_rationale.zh}
                      className="text-sm leading-relaxed"
                    />
                  </div>
                )}
                {hasContent(item.key_point_summary) && (
                  <div className="flex items-start gap-2 text-sm text-muted-foreground">
                    <span className="font-medium text-foreground">Key point:</span>
                    <BilingualText
                      mode={mode}
                      en={item.key_point_summary.en}
                      zh={item.key_point_summary.zh}
                    />
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
