"use client";

// Wrong-question book (错题集) — PRD v1.4 FR-WRONG-02..04: three tabs
// (wrongs / bookmarked / flagged), paper filter, inline explanations,
// re-practice, mark-mastered.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useT } from "@/lib/i18n/provider";
import { usePreferences } from "@/lib/api/preferences";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Loading } from "@/components/loading";
import { enumLabel } from "@/features/shared/enum-label";
import { localizedText } from "@/components/bilingual-text";
import { usePapers } from "@/lib/api/papers";
import { useSetQuestionState } from "@/lib/api/sessions";
import { useWrongBook, useWrongBookPractice, type WrongBookTab } from "@/lib/api/wrong-book";
import type { LanguageMode } from "@/lib/api/types";

const TABS: WrongBookTab[] = ["wrong", "bookmarked", "flagged"];

export function WrongBookView() {
  const t = useT();
  const router = useRouter();
  const { data: prefs } = usePreferences();
  const mode: LanguageMode = prefs?.language_mode ?? "en";
  const [tab, setTab] = useState<WrongBookTab>("wrong");
  const [paperId, setPaperId] = useState<string>("");
  const [openId, setOpenId] = useState<string | null>(null);

  const wrongBook = useWrongBook(tab, paperId || null);
  const papers = usePapers();
  const setState = useSetQuestionState();
  const rePractice = useWrongBookPractice();

  const tabLabel: Record<WrongBookTab, string> = {
    wrong: t("wrongBookPage.tabWrong"),
    bookmarked: t("wrongBookPage.tabBookmarked"),
    flagged: t("wrongBookPage.tabFlagged"),
  };

  async function startRePractice() {
    const session = await rePractice.mutateAsync({
      ...(paperId ? { paper_id: paperId } : {}),
      count: 50,
    });
    router.push(`/paper-play/${session.id}?kind=practice`);
  }

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 p-6">
      <PageHeader
        eyebrow={t("wrongBookPage.eyebrow")}
        title={t("wrongBookPage.title")}
        description={t("wrongBookPage.subtitle")}
        actions={
          tab === "wrong" ? (
            <Button size="sm" onClick={startRePractice} disabled={rePractice.isPending}>
              {t("wrongBookPage.rePracticeAll")}
            </Button>
          ) : undefined
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        {TABS.map((key) => (
          <Button
            key={key}
            size="sm"
            variant={tab === key ? "default" : "outline"}
            onClick={() => setTab(key)}
            aria-pressed={tab === key}
          >
            {tabLabel[key]}
          </Button>
        ))}
        <select
          value={paperId}
          onChange={(e) => setPaperId(e.target.value)}
          aria-label="paper filter"
          className="ml-auto h-9 rounded-md border bg-background px-3 text-sm"
        >
          <option value="">{t("wrongBookPage.allPapers")}</option>
          {(papers.data?.items ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      {wrongBook.isLoading && (
        <div className="p-4">
          <Loading label={t("common.loading")} />
        </div>
      )}

      {!wrongBook.isLoading && (wrongBook.data?.items.length ?? 0) === 0 && (
        <Card className="p-6 text-sm text-muted-foreground">
          {t("wrongBookPage.empty")}
        </Card>
      )}

      <div className="space-y-2">
        {(wrongBook.data?.items ?? []).map((item) => {
          const open = openId === item.question_id;
          return (
            <Card key={item.question_id} className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">
                    {enumLabel(t, "qType", item.question_type as never)}
                  </Badge>
                  {item.wrong_count > 0 && (
                    <Badge variant="destructive">
                      {t("wrongBookPage.wrongNTimes", { count: item.wrong_count })}
                    </Badge>
                  )}
                  {item.is_mastered && (
                    <Badge variant="secondary">{t("wrongBookPage.mastered")}</Badge>
                  )}
                  {item.papers.length > 0 && (
                    <span className="text-xs text-muted-foreground">
                      {t("wrongBookPage.inPapers", { papers: item.papers.join("、") })}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setOpenId(open ? null : item.question_id)}
                    aria-expanded={open}
                  >
                    {open
                      ? t("paperPlay.hideAnswer")
                      : t("wrongBookPage.viewAnswer")}
                  </Button>
                  {tab === "wrong" && !item.is_mastered && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        setState.mutate({
                          question_id: item.question_id,
                          is_mastered: true,
                        })
                      }
                    >
                      {t("wrongBookPage.markMastered")}
                    </Button>
                  )}
                </div>
              </div>
              <p className="mt-2 line-clamp-2 text-sm">{localizedText(mode, item.stem)}</p>

              {open && (
                <div className="mt-3 space-y-3 border-t pt-3 text-sm">
                  <div>{localizedText(mode, item.stem)}</div>
                  {item.options.map((o) => (
                    <div
                      key={o.order_index}
                      className={`rounded border p-2 ${
                        item.correct_indexes.includes(o.order_index)
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
                  {item.question_type === "essay" && item.reference_answer && (
                    <div>
                      <div className="font-medium">
                        {t("paperPlay.referenceAnswer")}
                      </div>
                      <p>{localizedText(mode, item.reference_answer)}</p>
                    </div>
                  )}
                  {(item.rationale.en || item.rationale.zh) && (
                    <div>
                      <div className="font-medium">{t("paperPlay.rationale")}</div>
                      <p className="text-muted-foreground">
                        {localizedText(mode, item.rationale)}
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
  );
}
