"use client";

import Link from "next/link";
import { useExamReview } from "@/lib/api/exam";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { cn } from "@/lib/utils";

export function ExamReview({ sessionId }: { sessionId: string }) {
  const review = useExamReview(sessionId);

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
          <Button asChild variant="outline">
            <Link href={`/exam/sessions/${sessionId}/report`}>Back to report</Link>
          </Button>
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
                <CardTitle className="mt-1 text-base font-medium leading-relaxed">{item.stem}</CardTitle>
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
                        <span className="flex-1">{o.content}</span>
                        {o.is_correct && <Badge variant="success">Correct</Badge>}
                        {chosen && !o.is_correct && <Badge variant="destructive">Your pick</Badge>}
                      </li>
                    );
                  })}
                </ul>
                {item.correct_rationale && (
                  <div className="rounded-md bg-muted/40 p-3 text-sm leading-relaxed">
                    {item.correct_rationale}
                  </div>
                )}
                {item.key_point_summary && (
                  <p className="text-sm text-muted-foreground">{item.key_point_summary}</p>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
