"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useDomains, useBooks, useChapters, useTags } from "@/lib/api/taxonomy";
import { useCreateSession } from "@/lib/api/practice";
import { ApiError } from "@/lib/api";
import {
  buildSessionPayload,
  defaultSessionFormState,
  type SessionFormState,
} from "./session-payload";
import { trackSession } from "./session-tracker";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import type { Subset, OrderMode, QuestionType } from "@/lib/api/types";

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

  return (
    <Card>
      <CardHeader>
        <CardTitle>New practice session</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-5 md:grid-cols-2">
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

        <div className="md:col-span-2">
          <Button onClick={start} disabled={!countValid || create.isPending} className="w-full md:w-auto">
            {create.isPending ? "Starting…" : "Start practice"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
