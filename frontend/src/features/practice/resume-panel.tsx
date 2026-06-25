"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useQueries } from "@tanstack/react-query";
import { apiJson, ApiError } from "@/lib/api";
import { qk } from "@/lib/api/keys";
import type { SessionOut } from "@/lib/api/types";
import { getTrackedSessionIds, untrackSession } from "./session-tracker";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";

export function ResumePanel() {
  const [ids, setIds] = useState<string[]>([]);
  useEffect(() => {
    setIds(getTrackedSessionIds());
  }, []);

  const results = useQueries({
    queries: ids.map((id) => ({
      queryKey: qk.session(id),
      queryFn: () => apiJson<SessionOut>(`/api/practice/sessions/${id}`),
      retry: false,
    })),
  });

  // Untrack ids that no longer resolve or are no longer in progress.
  useEffect(() => {
    results.forEach((r, i) => {
      const id = ids[i];
      if (!id) return;
      if (r.isError && r.error instanceof ApiError && r.error.status === 404) {
        untrackSession(id);
      }
      if (r.data && r.data.status !== "in_progress") {
        untrackSession(id);
      }
    });
  }, [results, ids]);

  const active = useMemo(
    () =>
      results
        .map((r) => r.data)
        .filter((s): s is SessionOut => !!s && s.status === "in_progress"),
    [results]
  );

  if (ids.length === 0 || (results.every((r) => !r.isLoading) && active.length === 0)) {
    return (
      <EmptyState
        title="No sessions in progress"
        description="Create a new practice session from the New tab to get started."
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {active.map((s) => {
        const answered = s.config && Array.isArray((s.config as { question_ids?: unknown[] }).question_ids)
          ? null
          : null;
        return (
          <Card key={s.id}>
            <CardHeader>
              <CardTitle className="text-base">Practice session</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">
                {s.correct_count} correct of {s.total_questions} questions
              </p>
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-primary"
                  style={{
                    width: `${
                      s.total_questions > 0
                        ? Math.round((s.correct_count / s.total_questions) * 100)
                        : 0
                    }%`,
                  }}
                />
              </div>
              <Button asChild size="sm">
                <Link href={`/practice/sessions/${s.id}`}>Resume</Link>
              </Button>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
