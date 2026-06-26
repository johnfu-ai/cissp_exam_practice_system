"use client";

import Link from "next/link";
import { useSessionSummary, useSession } from "@/lib/api/practice";
import { localizedText } from "@/components/bilingual-text";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { cn } from "@/lib/utils";
import { CheckCircle2, XCircle } from "lucide-react";
import type { LanguageMode } from "@/lib/api/types";

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
  // Read the session's language mode (stored in `config`) so wrong-question
  // stems render in the language the session was practised in. Falls back to
  // English while the session query is still loading or if unset.
  const session = useSession(sessionId);
  const sessionMode: LanguageMode =
    (session.data?.config?.language_mode as LanguageMode | undefined) ?? "en";

  if (summary.isLoading) return <Loading label="Loading summary…" />;
  if (summary.isError || !summary.data) {
    return <ErrorState message="Could not load the session summary." />;
  }
  const s = summary.data;
  const passed = s.accuracy >= 0.7;
  const unanswered = Math.max(0, s.total_questions - s.answered_count);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        eyebrow="Practice"
        title="Session complete"
        description={`${s.answered_count} answered of ${s.total_questions} · ${s.correct_count} correct`}
        actions={
          <Button asChild size="pill">
            <Link href="/practice">Back to practice</Link>
          </Button>
        }
      />

      {/* Correctness banner */}
      <div
        className={cn(
          "flex items-center gap-3 rounded-lg border p-4",
          passed ? "border-success/30 bg-success/10" : "border-destructive/30 bg-destructive/10"
        )}
      >
        {passed ? (
          <CheckCircle2 className="h-6 w-6 shrink-0 text-success" />
        ) : (
          <XCircle className="h-6 w-6 shrink-0 text-destructive" />
        )}
        <div className="min-w-0 flex-1">
          <p className={cn("font-semibold", passed ? "text-success" : "text-destructive")}>
            {passed ? "Nice work" : "Keep practicing"}
          </p>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {fmtPct(s.accuracy)} accuracy · {s.correct_count}/{s.answered_count} correct
            {unanswered > 0 && ` · ${unanswered} unanswered`}
          </p>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Accuracy" value={fmtPct(s.accuracy)} />
        <StatCard label="Correct" value={`${s.correct_count}/${s.answered_count}`} />
        <StatCard label="Time spent" value={fmtDuration(s.total_time_spent_ms)} />
      </div>

      {/* By domain */}
      <Card>
        <CardHeader>
          <CardTitle>By domain</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {s.domains.length === 0 && <p className="text-sm text-muted-foreground">No domain data.</p>}
          {s.domains.map((d, i) => (
            <div key={d.domain_id ?? `none-${i}`} className="flex items-center justify-between text-sm">
              <span>{d.domain_name ?? "Unmapped"}</span>
              <span className="text-muted-foreground tabular-nums">
                {d.correct}/{d.answered} correct
              </span>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Wrong questions — per-question review */}
      <Card>
        <CardHeader>
          <CardTitle>Wrong questions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {s.wrong_questions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No wrong answers — well done.</p>
          ) : (
            s.wrong_questions.map((w) => (
              <div
                key={w.question_id}
                className="space-y-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3"
              >
                <p className="text-sm leading-relaxed">{localizedText(sessionMode, w.stem)}</p>
                <div className="flex flex-wrap gap-2 text-xs">
                  <Badge variant="destructive">Your answer: {w.selected_indexes.join(", ") || "—"}</Badge>
                  <Badge variant="success">Correct: {w.correct_indexes.join(", ")}</Badge>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      {/* Bottom CTA */}
      <div className="flex justify-center pt-2">
        <Button asChild size="pill">
          <Link href="/practice">Back to practice</Link>
        </Button>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
    </Card>
  );
}
