"use client";

// Paper library (题库) — PRD v1.4 FR-PAPER-03: browse published papers and
// launch practice/exam sessions in one click.

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiJson } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loading } from "@/components/loading";
import { usePapers } from "@/lib/api/papers";

export function PapersView() {
  const t = useT();
  const router = useRouter();
  const { data, isLoading, isError } = usePapers();
  const [launching, setLaunching] = useState<string | null>(null);

  async function start(paperId: string, mode: "practice" | "exam") {
    const key = `${paperId}:${mode}`;
    setLaunching(key);
    try {
      const session = await apiJson<{ id: string }>(`/api/papers/${paperId}/sessions`, {
        method: "POST",
        body: JSON.stringify({ mode }),
      });
      router.push(`/paper-play/${session.id}?kind=${mode}&paper=${paperId}`);
    } catch {
      setLaunching(null);
    }
  }

  if (isLoading) {
    return (
      <div className="p-8">
        <Loading label={t("common.loading")} />
      </div>
    );
  }

  const papers = data?.items ?? [];

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 p-6">
      <PageHeader
        eyebrow={t("papersPage.eyebrow")}
        title={t("papersPage.title")}
        description={t("papersPage.subtitle")}
      />
      {isError && <p className="text-sm text-destructive">{t("error.generic")}</p>}
      {!isError && papers.length === 0 && (
        <Card className="p-6 text-sm text-muted-foreground">
          {t("papersPage.empty")}
        </Card>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {papers.map((p) => (
          <Card key={p.id} hover className="flex flex-col gap-3 p-5">
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-semibold leading-snug">{p.name}</h3>
              {p.domain_number != null && (
                <Badge variant="secondary">
                  {t("papersPage.domain", { number: p.domain_number })}
                </Badge>
              )}
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
              <span>{t("papersPage.questionCount", { count: p.question_count })}</span>
              {p.duration_minutes != null && (
                <span>{t("papersPage.duration", { minutes: p.duration_minutes })}</span>
              )}
              <span>{t("papersPage.score", { score: p.total_score })}</span>
              {p.attempts > 0 && (
                <span>
                  {t("papersPage.attempts", { count: p.attempts })}
                  {p.best_score != null &&
                    ` · ${t("papersPage.best", { score: p.best_score })}`}
                </span>
              )}
            </div>
            <div className="mt-auto flex gap-2 pt-2">
              <Button
                size="sm"
                disabled={launching !== null}
                onClick={() => start(p.id, "practice")}
                aria-label={`${t("papersPage.startPractice")}: ${p.name}`}
              >
                {launching === `${p.id}:practice`
                  ? t("papersPage.starting")
                  : t("papersPage.startPractice")}
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={launching !== null}
                onClick={() => start(p.id, "exam")}
                aria-label={`${t("papersPage.startExam")}: ${p.name}`}
              >
                {launching === `${p.id}:exam`
                  ? t("papersPage.starting")
                  : t("papersPage.startExam")}
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
