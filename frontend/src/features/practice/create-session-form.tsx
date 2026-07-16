"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useDomains, useBooks, useChapters, useTags } from "@/lib/api/taxonomy";
import { useCreateSession } from "@/lib/api/practice";
import { useAuthStore } from "@/lib/auth-store";
import { ApiError } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { enumLabel } from "@/features/shared/enum-label";
import {
  buildSessionPayload,
  defaultSessionFormState,
  type SessionFormState,
} from "./session-payload";
import { trackSession } from "./session-tracker";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Eyebrow } from "@/components/eyebrow";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";
import type { Subset, OrderMode, QuestionType, LanguageMode } from "@/lib/api/types";

const ANY = "__any__";
const SUBSETS: Subset[] = ["all", "unpracticed", "wrong", "bookmarked", "needs_review"];
const ORDERS: OrderMode[] = ["random", "sequential", "easy_to_hard"];
const TYPES: QuestionType[] = [
  "single_choice",
  "multiple_choice",
  "true_false",
  "scenario",
  "ordering",
  "drag_drop",
  "hotspot",
];
const LANGUAGE_MODES: LanguageMode[] = ["en", "zh", "bilingual"];

export function CreateSessionForm() {
  const t = useT();
  const router = useRouter();
  const [form, setForm] = useState<SessionFormState>(defaultSessionFormState);
  const domains = useDomains();
  const books = useBooks();
  const chapters = useChapters(form.bookId);
  const tags = useTags();
  const create = useCreateSession();
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    if (form.languageMode === null && user?.language_mode) {
      set("languageMode", user.language_mode);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.language_mode]);

  function set<K extends keyof SessionFormState>(key: K, value: SessionFormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function start() {
    const payload = buildSessionPayload(form);
    create.mutate(payload, {
      onSuccess: (session) => {
        trackSession(session.id);
        router.push(`/practice/sessions/${session.id}`);
      },
      onError: (e) => {
        const msg =
          e instanceof ApiError && e.status === 422
            ? t("practiceForm.noMatch")
            : t("practiceForm.couldNotStart");
        toast.error(msg);
      },
    });
  }

  const countValid = Number.isFinite(form.count) && form.count >= 1 && form.count <= 200;

  const activeLanguage = form.languageMode ?? user?.language_mode ?? "en";
  const domainLabel = form.domainId
    ? (domains.data ?? []).find((d) => d.id === form.domainId)?.name ?? t("practiceForm.selectedDomain")
    : t("practiceForm.anyDomain");

  const langLabel = (m: LanguageMode) => t(`lang.${m}`);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      {/* Left column: configuration */}
      <Card>
        <CardHeader>
          <Eyebrow>{t("practiceForm.configure")}</Eyebrow>
          <CardTitle className="text-xl">{t("practiceForm.newSession")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-8">
          <section className="space-y-4">
            <Eyebrow>{t("practiceForm.scope")}</Eyebrow>
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>{t("practiceForm.domain")}</Label>
                <Select
                  value={form.domainId ?? ANY}
                  onValueChange={(v) => set("domainId", v === ANY ? null : v)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t("practiceForm.anyDomain")} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ANY}>{t("practiceForm.anyDomain")}</SelectItem>
                    {(domains.data ?? []).map((d) => (
                      <SelectItem key={d.id} value={d.id}>
                        {d.number}. {d.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>{t("practiceForm.subset")}</Label>
                <Select value={form.subset} onValueChange={(v) => set("subset", v as Subset)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SUBSETS.map((s) => (
                      <SelectItem key={s} value={s}>
                        {enumLabel(t, "subset", s)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>{t("practiceForm.book")}</Label>
                <Select
                  value={form.bookId ?? ANY}
                  onValueChange={(v) =>
                    setForm((f) => ({ ...f, bookId: v === ANY ? null : v, chapterIds: [] }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t("practiceForm.anyBook")} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ANY}>{t("practiceForm.anyBook")}</SelectItem>
                    {(books.data ?? []).map((b) => (
                      <SelectItem key={b.id} value={b.id}>
                        {b.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>{t("practiceForm.chapter")}</Label>
                <Select
                  value={form.chapterIds[0] ?? ANY}
                  disabled={!form.bookId}
                  onValueChange={(v) => set("chapterIds", v === ANY ? [] : [v])}
                >
                  <SelectTrigger>
                    <SelectValue
                      placeholder={form.bookId ? t("practiceForm.anyChapter") : t("practiceForm.selectBookFirst")}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ANY}>{t("practiceForm.anyChapter")}</SelectItem>
                    {(chapters.data ?? []).map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.order_index}. {c.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </section>

          <section className="space-y-4">
            <Eyebrow>{t("practiceForm.questions")}</Eyebrow>
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="count">{t("practiceForm.numQuestions")}</Label>
                <Input
                  id="count"
                  type="number"
                  min={1}
                  max={200}
                  value={Number.isNaN(form.count) ? "" : form.count}
                  onChange={(e) => set("count", e.target.value === "" ? NaN : Number(e.target.value))}
                />
              </div>

              <div className="space-y-2">
                <Label>{t("practiceForm.questionType")}</Label>
                <Select
                  value={form.questionType ?? ANY}
                  onValueChange={(v) => set("questionType", v === ANY ? null : v)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t("practiceForm.anyType")} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ANY}>{t("practiceForm.anyType")}</SelectItem>
                    {TYPES.map((qt) => (
                      <SelectItem key={qt} value={qt}>
                        {enumLabel(t, "qType", qt)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>{t("practiceForm.difficulty")}</Label>
                <Select
                  value={form.difficulty != null ? String(form.difficulty) : ANY}
                  onValueChange={(v) => set("difficulty", v === ANY ? null : Number(v))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t("practiceForm.anyDifficulty")} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ANY}>{t("practiceForm.anyDifficulty")}</SelectItem>
                    {[1, 2, 3, 4, 5].map((d) => (
                      <SelectItem key={d} value={String(d)}>
                        {t("practiceForm.levelN", { n: d })}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>{t("practiceForm.tag")}</Label>
                <Select value={form.tagId ?? ANY} onValueChange={(v) => set("tagId", v === ANY ? null : v)}>
                  <SelectTrigger>
                    <SelectValue placeholder={t("practiceForm.anyTag")} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ANY}>{t("practiceForm.anyTag")}</SelectItem>
                    {(tags.data ?? []).map((tg) => (
                      <SelectItem key={tg.id} value={tg.id}>
                        {tg.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </section>

          <section className="space-y-4">
            <Eyebrow>{t("practiceForm.delivery")}</Eyebrow>
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>{t("practiceForm.order")}</Label>
                <Select value={form.orderMode} onValueChange={(v) => set("orderMode", v as OrderMode)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ORDERS.map((o) => (
                      <SelectItem key={o} value={o}>
                        {enumLabel(t, "orderMode", o)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>{t("practiceForm.languageMode")}</Label>
                <Select
                  value={form.languageMode ?? user?.language_mode ?? "en"}
                  onValueChange={(v) => set("languageMode", v as LanguageMode)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {LANGUAGE_MODES.map((m) => (
                      <SelectItem key={m} value={m}>
                        {langLabel(m)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </section>
        </CardContent>
      </Card>

      {/* Right column: summary + start CTA */}
      <Card className="lg:sticky lg:top-6 lg:self-start">
        <CardHeader>
          <CardTitle>{t("practiceForm.sessionSummary")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <dl className="space-y-3 text-sm">
            <SummaryRow label={t("practiceForm.summaryQuestions")} value={String(form.count)} />
            <SummaryRow label={t("practiceForm.summaryDomain")} value={domainLabel} />
            <SummaryRow label={t("practiceForm.summarySource")} value={enumLabel(t, "subset", form.subset)} />
            <SummaryRow label={t("practiceForm.summaryOrder")} value={enumLabel(t, "orderMode", form.orderMode)} />
            <SummaryRow label={t("practiceForm.summaryLanguage")} value={langLabel(activeLanguage)} />
          </dl>
          <Button
            size="pill"
            onClick={start}
            disabled={!countValid || create.isPending}
            className="w-full"
          >
            {create.isPending ? t("practiceForm.starting") : t("practiceForm.startPractice")}
          </Button>
          {!countValid && (
            <p className="text-center text-xs text-muted-foreground">{t("practiceForm.countHint")}</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-t border-border pt-3 first:border-0 first:pt-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium tabular-nums">{value}</dd>
    </div>
  );
}
