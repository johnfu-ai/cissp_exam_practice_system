"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCreateExam } from "@/lib/api/exam";
import { ApiError } from "@/lib/api";
import { trackExam } from "./exam-tracker";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/sonner";
import type { ExamKind } from "@/lib/api/types";

export function ExamStartForm() {
  const router = useRouter();
  const [kind, setKind] = useState<ExamKind>("fixed");
  const [count, setCount] = useState<string>("");
  const create = useCreateExam();

  function start() {
    const body =
      kind === "cat"
        ? { kind }
        : { kind, count: count.trim() === "" ? null : Math.max(1, Number(count) || 0) };
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
