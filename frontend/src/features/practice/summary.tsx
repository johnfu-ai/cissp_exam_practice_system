"use client";

import Link from "next/link";
import { useSessionSummary } from "@/lib/api/practice";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";

function fmtPct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

function fmtDuration(ms: number): string {
  const totalSec = Math.round(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}m ${s}s`;
}

export function Summary({ sessionId }: { sessionId: string }) {
  const summary = useSessionSummary(sessionId);

  if (summary.isLoading) return <Loading label="Loading summary…" />;
  if (summary.isError || !summary.data) {
    return <ErrorState message="Could not load the session summary." />;
  }
  const s = summary.data;

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Session complete"
        description={`${s.answered_count} answered of ${s.total_questions} · ${s.correct_count} correct`}
        actions={
          <Button asChild>
            <Link href="/practice">Start another</Link>
          </Button>
        }
      />

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Accuracy</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{fmtPct(s.accuracy)}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Correct</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            {s.correct_count}/{s.answered_count}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Time spent</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{fmtDuration(s.total_time_spent_ms)}</CardContent>
        </Card>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>By domain</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {s.domains.length === 0 && <p className="text-sm text-muted-foreground">No domain data.</p>}
          {s.domains.map((d, i) => (
            <div key={d.domain_id ?? `none-${i}`} className="flex items-center justify-between text-sm">
              <span>{d.domain_name ?? "Unmapped"}</span>
              <span className="text-muted-foreground">
                {d.correct}/{d.answered} correct
              </span>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Wrong questions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {s.wrong_questions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No wrong answers — well done.</p>
          ) : (
            s.wrong_questions.map((w) => (
              <div key={w.question_id} className="rounded-md border p-3">
                <p className="text-sm">{w.stem}</p>
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
