"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCreateExam } from "@/lib/api/exam";
import { useAuthStore } from "@/lib/auth-store";
import { ApiError } from "@/lib/api";
import { trackExam } from "./exam-tracker";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <button
        type="button"
        onClick={() => setKind("fixed")}
        className={`rounded-lg border p-5 text-left transition-colors ${
          kind === "fixed" ? "border-primary ring-1 ring-primary" : "hover:bg-accent"
        }`}
      >
        <div className="flex items-center justify-between">
          <h3 className="font-medium">Fixed mock exam</h3>
          {kind === "fixed" && <Badge>Selected</Badge>}
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          A blueprint-weighted, fixed-length exam. Timed, no feedback until you finish; you can revise answers before submitting.
        </p>
      </button>

      <button
        type="button"
        onClick={() => setKind("cat")}
        className={`rounded-lg border p-5 text-left transition-colors ${
          kind === "cat" ? "border-primary ring-1 ring-primary" : "hover:bg-accent"
        }`}
      >
        <div className="flex items-center justify-between">
          <h3 className="font-medium">CAT mock exam</h3>
          {kind === "cat" && <Badge>Selected</Badge>}
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Adaptive, forward-only delivery (100–150 items). You cannot revise a submitted answer. Study tool — not an official ISC2 score.
        </p>
      </button>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Confirm and start</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="max-w-xs space-y-1.5">
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
          {kind === "fixed" && (
            <div className="max-w-xs space-y-1.5">
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
          )}
          <Button onClick={start} disabled={create.isPending}>
            {create.isPending ? "Starting…" : `Start ${kind === "cat" ? "CAT" : "fixed"} exam`}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
