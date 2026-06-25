"use client";

import Link from "next/link";
import {
  useDashboard,
  useWeakAreas,
  useRecommendation,
  useDomainMastery,
} from "@/lib/api/analytics";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { fmtPct, fmtDuration, fmtDate, accuracyColor } from "./format";

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-normal text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent className="text-2xl font-semibold">{value}</CardContent>
    </Card>
  );
}

export function Dashboard() {
  const dashboard = useDashboard();
  const weak = useWeakAreas();
  const rec = useRecommendation();
  const domains = useDomainMastery();

  if (dashboard.isLoading) return <Loading label="Loading your dashboard…" />;
  if (dashboard.isError || !dashboard.data) {
    return <ErrorState message="Could not load your dashboard." onRetry={() => dashboard.refetch()} />;
  }
  const d = dashboard.data;
  const fresh = d.total_answered === 0;

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title="Dashboard"
        description="Your CISSP study overview at a glance."
        actions={
          <Button asChild>
            <Link href="/practice">Continue practice</Link>
          </Button>
        }
      />

      {fresh ? (
        <Card>
          <CardContent className="py-10 text-center">
            <h3 className="text-base font-medium">No activity yet</h3>
            <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
              Start a practice session to see your accuracy, weak domains, and a tailored review plan here.
            </p>
            <Button asChild className="mt-4">
              <Link href="/practice">Start practicing</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard label="Accuracy" value={fmtPct(d.accuracy)} />
            <StatCard label="Answered" value={`${d.correct_count}/${d.total_answered}`} />
            <StatCard label="Study time" value={fmtDuration(d.study_time_ms)} />
            <StatCard label="Streak" value={`${d.streak_days}d`} />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Weak domains</CardTitle>
                <Button asChild variant="ghost" size="sm">
                  <Link href="/analytics">View all</Link>
                </Button>
              </CardHeader>
              <CardContent className="space-y-3">
                {weak.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
                {weak.data && weak.data.weak_domains.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No weak domains detected. Keep practicing to maintain mastery.
                  </p>
                )}
                {weak.data?.weak_domains.map((w) => (
                  <div key={w.domain_id ?? w.label} className="space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <span>{w.label}</span>
                      <span className="text-muted-foreground">
                        {fmtPct(w.accuracy)} ({w.correct}/{w.answered})
                      </span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                      <div
                        className={`h-full ${accuracyColor(w.accuracy)}`}
                        style={{ width: `${Math.round(w.accuracy * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Today&apos;s recommendation</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {rec.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
                {rec.data && (
                  <>
                    <p className="text-sm">{rec.data.rationale}</p>
                    <div className="flex flex-wrap gap-2 text-xs">
                      {rec.data.focus_domain && (
                        <Badge variant="secondary">Focus: {rec.data.focus_domain.label}</Badge>
                      )}
                      <Badge variant="outline">
                        {rec.data.wrong_to_review.length} to review
                      </Badge>
                      <Badge variant="outline">
                        {rec.data.next_practice_question_ids.length} suggested
                      </Badge>
                    </div>
                    <div className="flex gap-2">
                      <Button asChild size="sm">
                        <Link href="/review">Review wrong questions</Link>
                      </Button>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="mt-6">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Domain mastery</CardTitle>
              <span className="text-xs text-muted-foreground">
                Last active {fmtDate(d.last_active_at)}
              </span>
            </CardHeader>
            <CardContent className="space-y-3">
              {domains.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
              {domains.data && domains.data.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No exam blueprint configured yet.
                </p>
              )}
              {domains.data?.map((m) => (
                <div key={m.domain_id} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span>
                      {m.number}. {m.name}
                    </span>
                    <span className="text-muted-foreground">
                      {m.answered === 0 ? "—" : `${fmtPct(m.accuracy)} (${m.correct}/${m.answered})`}
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className={`h-full ${accuracyColor(m.accuracy)}`}
                      style={{ width: `${Math.round(m.accuracy * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
