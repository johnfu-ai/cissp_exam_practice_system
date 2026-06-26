"use client";

import { useState } from "react";
import {
  useDatasets,
  useCreateRun,
  useCommitRun,
  useRollbackRun,
} from "@/lib/api/etl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Eyebrow } from "@/components/eyebrow";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { toast } from "@/components/ui/sonner";
import type { EtlRun } from "@/lib/api/types";

function Count({ label, value, tone }: { label: string; value: number; tone?: "create" | "update" | "muted" | "error" }) {
  const color =
    tone === "create" ? "text-success" :
    tone === "update" ? "text-primary" :
    tone === "error" ? "text-destructive" : "text-foreground";
  return (
    <div className="rounded-md border p-3 text-center">
      <div className={`text-2xl font-semibold tabular-nums ${color}`}>{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

export function ImportWizard() {
  const datasets = useDatasets();
  const createRun = useCreateRun();
  const commit = useCommitRun();
  const rollback = useRollbackRun();
  const [run, setRun] = useState<EtlRun | null>(null);
  const [activeSlug, setActiveSlug] = useState<string | null>(null);

  function preview(slug: string) {
    setActiveSlug(slug);
    createRun.mutate(slug, {
      onSuccess: (r) => setRun(r),
      onError: () => toast.error("Could not generate a preview for this dataset."),
    });
  }

  function doCommit() {
    if (!run) return;
    commit.mutate(run.run_id, {
      onSuccess: (r) => {
        setRun((cur) => (cur ? { ...cur, phase: r.phase } : cur));
        toast.success("Import committed.");
      },
      onError: () => toast.error("Could not commit this import."),
    });
  }

  function doRollback() {
    if (!run) return;
    rollback.mutate(run.run_id, {
      onSuccess: (r) => {
        setRun((cur) => (cur ? { ...cur, phase: r.phase } : cur));
        toast.message("Import discarded.");
      },
      onError: () => toast.error("Could not discard this import."),
    });
  }

  if (datasets.isLoading) return <Loading label="Loading datasets…" />;
  if (datasets.isError) {
    return <ErrorState message="Could not load import datasets." onRetry={() => datasets.refetch()} />;
  }

  const summary = run?.preview_summary;

  return (
    <div className="space-y-8">
      <section>
        <Eyebrow className="mb-3">Datasets</Eyebrow>
        {datasets.data && datasets.data.length === 0 ? (
          <EmptyState title="No datasets available" description="Seeded import datasets will appear here." />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {datasets.data?.map((d) => (
              <Card key={d.id} hover>
                <CardHeader>
                  <CardTitle className="text-base">{d.name}</CardTitle>
                  <p className="text-xs text-muted-foreground">{d.source_path}</p>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex flex-wrap gap-2 text-xs">
                    <Badge variant="secondary">{d.total_questions} questions</Badge>
                    {d.languages.map((l) => (
                      <Badge key={l} variant="outline">{l}</Badge>
                    ))}
                  </div>
                  <Button
                    size="sm"
                    onClick={() => preview(d.slug)}
                    disabled={createRun.isPending && activeSlug === d.slug}
                  >
                    {createRun.isPending && activeSlug === d.slug ? "Previewing…" : "Preview import"}
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      {run && summary && (
        <section>
          <Eyebrow className="mb-3">Preview</Eyebrow>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Preview — {activeSlug}</CardTitle>
              <Badge variant={run.phase === "committed" ? "success" : run.phase === "rolled_back" ? "destructive" : "secondary"}>
                {run.phase}
              </Badge>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Count label="Would create" value={summary.would_create} tone="create" />
                <Count label="Would update" value={summary.would_update} tone="update" />
                <Count label="Unchanged" value={summary.unchanged} tone="muted" />
                <Count label="Errors" value={summary.errors.length} tone="error" />
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <h4 className="mb-1 text-sm font-medium">By type</h4>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    {Object.entries(summary.by_type).map(([k, v]) => (
                      <li key={k} className="flex justify-between">
                        <span>{k.replace(/_/g, " ")}</span>
                        <span>{v}</span>
                      </li>
                    ))}
                    {Object.keys(summary.by_type).length === 0 && <li>—</li>}
                  </ul>
                </div>
                <div>
                  <h4 className="mb-1 text-sm font-medium">By language</h4>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    {Object.entries(summary.by_language).map(([k, v]) => (
                      <li key={k} className="flex justify-between">
                        <span>{k}</span>
                        <span>{v}</span>
                      </li>
                    ))}
                    {Object.keys(summary.by_language).length === 0 && <li>—</li>}
                  </ul>
                </div>
              </div>

              {summary.errors.length > 0 && (
                <div>
                  <h4 className="mb-2 text-sm font-medium text-destructive">
                    Validation issues ({summary.errors.length})
                  </h4>
                  <div className="max-h-64 overflow-y-auto rounded-md border">
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 bg-muted/60">
                        <tr className="text-left text-muted-foreground">
                          <th className="px-3 py-2 font-medium">Row / ID</th>
                          <th className="px-3 py-2 font-medium">Language</th>
                          <th className="px-3 py-2 font-medium">Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.errors.map((e, i) => (
                          <tr key={`${e.external_id}-${i}`} className="border-t">
                            <td className="px-3 py-2 font-mono text-xs">{e.external_id ?? "—"}</td>
                            <td className="px-3 py-2">{e.language ?? "—"}</td>
                            <td className="px-3 py-2 text-muted-foreground">{e.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {run.phase === "preview" ? (
                <div className="flex flex-wrap gap-2">
                  <Button size="pill" onClick={doCommit} disabled={commit.isPending}>
                    {commit.isPending ? "Committing…" : `Commit import (${summary.would_create + summary.would_update} rows)`}
                  </Button>
                  <Button variant="outline" size="pill" onClick={doRollback} disabled={rollback.isPending}>
                    Discard
                  </Button>
                </div>
              ) : (
                <Alert>
                  <AlertTitle>{run.phase === "committed" ? "Import committed" : "Import discarded"}</AlertTitle>
                  <AlertDescription>
                    {run.phase === "committed"
                      ? "Questions have been imported. Manage them from the Questions page."
                      : "No changes were applied. You can preview again at any time."}
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  );
}
