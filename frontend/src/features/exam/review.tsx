"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useExamReview, useExamSession } from "@/lib/api/exam";
import { BilingualText } from "@/components/bilingual-text";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
    <div className="mx-auto max-w-3xl">
      <PageHeader
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
          return (
            <Card key={item.question_id}>
              <CardHeader>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span>Q{item.position + 1}</span>
                  {item.time_spent_ms != null && (
                    <span>· {Math.round(item.time_spent_ms / 1000)}s</span>
                  )}
                </div>
                <CardTitle className="mt-1 text-base font-medium leading-relaxed">
                  <BilingualText mode={mode} en={item.stem.en} zh={item.stem.zh} />
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <ul className="space-y-2">
                  {item.options.map((o) => {
                    const chosen = selected.includes(o.order_index);
                    return (
                      <li
                        key={o.order_index}
                        className={cn(
                          "flex items-start gap-2 rounded-md border p-2 text-sm",
                          o.is_correct && "border-success/50 bg-success/10",
                          chosen && !o.is_correct && "border-destructive/50 bg-destructive/10"
                        )}
                      >
                        <span className="font-mono text-xs text-muted-foreground">{o.order_index}</span>
                        <BilingualText
                          mode={mode}
                          en={o.content.en}
                          zh={o.content.zh}
                          className="flex-1"
                        />
                        {o.is_correct && <Badge variant="success">Correct</Badge>}
                        {chosen && !o.is_correct && <Badge variant="destructive">Your pick</Badge>}
                      </li>
                    );
                  })}
                </ul>
                {hasContent(item.correct_rationale) && (
                  <div className="rounded-md bg-muted/40 p-3 text-sm leading-relaxed">
                    <BilingualText
                      mode={mode}
                      en={item.correct_rationale.en}
                      zh={item.correct_rationale.zh}
                    />
                  </div>
                )}
                {hasContent(item.key_point_summary) && (
                  <BilingualText
                    mode={mode}
                    en={item.key_point_summary.en}
                    zh={item.key_point_summary.zh}
                    className="text-sm text-muted-foreground"
                  />
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
