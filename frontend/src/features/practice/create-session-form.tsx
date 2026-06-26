"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useDomains, useBooks, useChapters, useTags } from "@/lib/api/taxonomy";
import { useCreateSession } from "@/lib/api/practice";
import { useAuthStore } from "@/lib/auth-store";
import { ApiError } from "@/lib/api";
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
const LANGUAGE_LABELS: Record<LanguageMode, string> = {
  en: "English",
  zh: "中文",
  bilingual: "Both",
};

function labelize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function CreateSessionForm() {
  const router = useRouter();
  const [form, setForm] = useState<SessionFormState>(defaultSessionFormState);
  const domains = useDomains();
  const books = useBooks();
  const chapters = useChapters(form.bookId);
  const tags = useTags();
  const create = useCreateSession();
  const user = useAuthStore((s) => s.user);

  // Pre-select the user's preferred language mode once it is available. The
  // select itself also falls back to this value while `form.languageMode` is
  // still null, so the UI never shows an empty selection before the effect runs.
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
            ? "No questions match the selected filters."
            : "Could not start the session. Please try again.";
        toast.error(msg);
      },
    });
  }

  const countValid = Number.isFinite(form.count) && form.count >= 1 && form.count <= 200;

  const activeLanguage = form.languageMode ?? user?.language_mode ?? "en";
  const domainLabel = form.domainId
    ? (domains.data ?? []).find((d) => d.id === form.domainId)?.name ?? "Selected domain"
    : "Any domain";

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      {/* Left column: configuration */}
      <Card>
        <CardHeader>
          <Eyebrow>Configure</Eyebrow>
          <CardTitle className="text-xl">New practice session</CardTitle>
        </CardHeader>
        <CardContent className="space-y-8">
          <section className="space-y-4">
            <Eyebrow>Scope</Eyebrow>
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Domain</Label>
                <Select
                  value={form.domainId ?? ANY}
                  onValueChange={(v) => set("domainId", v === ANY ? null : v)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Any domain" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ANY}>Any domain</SelectItem>
                    {(domains.data ?? []).map((d) => (
                      <SelectItem key={d.id} value={d.id}>
                        {d.number}. {d.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Subset</Label>
                <Select value={form.subset} onValueChange={(v) => set("subset", v as Subset)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SUBSETS.map((s) => (
                      <SelectItem key={s} value={s}>
                        {labelize(s)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Book</Label>
                <Select
                  value={form.bookId ?? ANY}
                  onValueChange={(v) =>
                    setForm((f) => ({ ...f, bookId: v === ANY ? null : v, chapterIds: [] }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Any book" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ANY}>Any book</SelectItem>
                    {(books.data ?? []).map((b) => (
                      <SelectItem key={b.id} value={b.id}>
                        {b.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Chapter</Label>
                <Select
                  value={form.chapterIds[0] ?? ANY}
                  disabled={!form.bookId}
                  onValueChange={(v) => set("chapterIds", v === ANY ? [] : [v])}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={form.bookId ? "Any chapter" : "Select a book first"} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ANY}>Any chapter</SelectItem>
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
            <Eyebrow>Questions</Eyebrow>
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="count">Number of questions</Label>
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
                <Label>Question type</Label>
                <Select
                  value={form.questionType ?? ANY}
                  onValueChange={(v) => set("questionType", v === ANY ? null : v)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Any type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ANY}>Any type</SelectItem>
                    {TYPES.map((t) => (
                      <SelectItem key={t} value={t}>
                        {labelize(t)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Difficulty</Label>
                <Select
                  value={form.difficulty != null ? String(form.difficulty) : ANY}
                  onValueChange={(v) => set("difficulty", v === ANY ? null : Number(v))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Any difficulty" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ANY}>Any difficulty</SelectItem>
                    {[1, 2, 3, 4, 5].map((d) => (
                      <SelectItem key={d} value={String(d)}>
                        Level {d}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Tag</Label>
                <Select value={form.tagId ?? ANY} onValueChange={(v) => set("tagId", v === ANY ? null : v)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Any tag" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ANY}>Any tag</SelectItem>
                    {(tags.data ?? []).map((t) => (
                      <SelectItem key={t.id} value={t.id}>
                        {t.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </section>

          <section className="space-y-4">
            <Eyebrow>Delivery</Eyebrow>
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Order</Label>
                <Select value={form.orderMode} onValueChange={(v) => set("orderMode", v as OrderMode)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ORDERS.map((o) => (
                      <SelectItem key={o} value={o}>
                        {labelize(o)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Language mode</Label>
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
                        {LANGUAGE_LABELS[m]}
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
          <CardTitle>Session summary</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <dl className="space-y-3 text-sm">
            <SummaryRow label="Questions" value={String(form.count)} />
            <SummaryRow label="Domain" value={domainLabel} />
            <SummaryRow label="Source" value={labelize(form.subset)} />
            <SummaryRow label="Order" value={labelize(form.orderMode)} />
            <SummaryRow label="Language" value={LANGUAGE_LABELS[activeLanguage]} />
          </dl>
          <Button
            size="pill"
            onClick={start}
            disabled={!countValid || create.isPending}
            className="w-full"
          >
            {create.isPending ? "Starting…" : "Start practice"}
          </Button>
          {!countValid && (
            <p className="text-center text-xs text-muted-foreground">
              Choose between 1 and 200 questions.
            </p>
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
