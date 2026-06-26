"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCreateExam } from "@/lib/api/exam";
import { useAuthStore } from "@/lib/auth-store";
import { ApiError } from "@/lib/api";
import { trackExam } from "./exam-tracker";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Eyebrow } from "@/components/eyebrow";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";
import { cn } from "@/lib/utils";
import { Clock, Forward, Check } from "lucide-react";
import type { ExamKind, LanguageMode } from "@/lib/api/types";

const LANGUAGE_MODES: LanguageMode[] = ["en", "zh", "bilingual"];
const LANGUAGE_LABELS: Record<LanguageMode, string> = {
  en: "English",
  zh: "中文",
  bilingual: "Both",
};

export function ExamStartForm() {
  const router = useRouter();
  const [kind, setKind] = useState<ExamKind>("fixed");
  const [count, setCount] = useState<string>("");
  const user = useAuthStore((s) => s.user);
  const [languageMode, setLanguageMode] = useState<LanguageMode>(
    user?.language_mode ?? "en",
  );
  const create = useCreateExam();

  function start() {
    // CAT: { kind, language_mode }. Fixed: include `count` only when the user
    // supplied one — a blank count means "full-length" and is omitted so the
    // backend applies the blueprint range.
    const body =
      kind === "cat"
        ? { kind, language_mode: languageMode }
        : count.trim() === ""
          ? { kind, language_mode: languageMode }
          : { kind, count: Math.max(1, Number(count) || 0), language_mode: languageMode };
    create.mutate(body, {
      onSuccess: (s) => {
        trackExam(s.id);
        router.push(`/exam/sessions/${s.id}`);
      },
      onError: (e) => {
        if (e instanceof ApiError && e.status === 422) {
          toast.error("Not enough published questions to assemble this exam.");
        } else {
          toast.error("Could not start the exam.");
        }
      },
    });
  }

  const startLabel = create.isPending
    ? "Starting…"
    : `Start ${kind === "cat" ? "CAT" : "fixed"} exam`;

  return (
    <div className="space-y-6">
      {/* Kind selector */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <KindCard
          selected={kind === "fixed"}
          onSelect={() => setKind("fixed")}
          title="Fixed mock exam"
          icon={<Clock className="h-5 w-5" />}
          meta="Timed · 3 hours"
          description="A blueprint-weighted, fixed-length exam. Timed, no feedback until you finish; you can revise answers before submitting."
        />
        <KindCard
          selected={kind === "cat"}
          onSelect={() => setKind("cat")}
          title="CAT mock exam"
          icon={<Forward className="h-5 w-5" />}
          meta="Adaptive · 100–150 items"
          description="Adaptive, forward-only delivery (100–150 items). You cannot revise a submitted answer. Study tool — not an official ISC2 score."
        />
      </div>

      {/* Confirm + start */}
      <Card>
        <CardHeader>
          <Eyebrow>Confirm</Eyebrow>
          <CardTitle>Configure and start</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="exam-language-mode">Language mode</Label>
              <Select
                value={languageMode}
                onValueChange={(v) => setLanguageMode(v as LanguageMode)}
              >
                <SelectTrigger id="exam-language-mode">
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
              <p className="text-xs text-muted-foreground">
                Choose how questions are displayed during the exam.
              </p>
            </div>

            {kind === "fixed" ? (
              <div className="space-y-2">
                <Label htmlFor="exam-count">Question count (optional)</Label>
                <Input
                  id="exam-count"
                  type="number"
                  min={1}
                  max={500}
                  placeholder="Full-length"
                  value={count}
                  onChange={(e) => setCount(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Leave blank for a full-length exam. Count is clamped to the blueprint range.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <Label>Duration</Label>
                <div className="flex h-10 items-center rounded-md border border-input bg-muted/40 px-3 text-sm text-muted-foreground">
                  Up to 3 hours · 100–150 adaptive items
                </div>
                <p className="text-xs text-muted-foreground">
                  The engine adapts to your ability and ends early on convergence.
                </p>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">
              {kind === "cat"
                ? "Forward-only · answers cannot be revised · study tool."
                : "Revisable answers · question palette · lazy auto-submit on time-up."}
            </p>
            <Button size="pill" onClick={start} disabled={create.isPending} className="sm:min-w-[180px]">
              {startLabel}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function KindCard({
  selected,
  onSelect,
  title,
  icon,
  meta,
  description,
}: {
  selected: boolean;
  onSelect: () => void;
  title: string;
  icon: React.ReactNode;
  meta: string;
  description: string;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        "group relative flex flex-col items-start gap-3 rounded-lg border p-5 text-left transition-all",
        selected
          ? "border-primary ring-1 ring-primary shadow-card"
          : "border-border hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-card",
      )}
    >
      <div className="flex w-full items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "flex h-9 w-9 items-center justify-center rounded-full",
              selected ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
            )}
          >
            {icon}
          </span>
          <h3 className="font-semibold">{title}</h3>
        </div>
        {selected && (
          <Badge>
            <Check className="h-3 w-3" /> Selected
          </Badge>
        )}
      </div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{meta}</p>
      <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
    </button>
  );
}
