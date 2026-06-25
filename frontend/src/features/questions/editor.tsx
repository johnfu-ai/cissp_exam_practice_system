"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCreateQuestion, useUpdateQuestion } from "@/lib/api/questions";
import { useDomains } from "@/lib/api/taxonomy";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";
import { ApiError } from "@/lib/api";
import { Trash2, Plus } from "lucide-react";
import type {
  QuestionDetail,
  QuestionType,
  LicenseStatus,
  QuestionOption,
  QuestionCreateInput,
} from "@/lib/api/types";

const ANY = "__none__";
const TYPES: QuestionType[] = ["single_choice", "multiple_choice", "true_false", "scenario"];
const LICENSES: LicenseStatus[] = ["user_owned", "third_party_licensed", "public_domain", "unconfirmed"];

function labelize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

interface OptionRow {
  content: string;
  is_correct: boolean;
  explanation: string;
}

export function QuestionEditor({ initial }: { initial?: QuestionDetail }) {
  const router = useRouter();
  const domains = useDomains();
  const create = useCreateQuestion();
  const update = useUpdateQuestion(initial?.id ?? "");

  const [type, setType] = useState<QuestionType>(initial?.question_type ?? "single_choice");
  const [stem, setStem] = useState(initial?.stem ?? "");
  const [difficulty, setDifficulty] = useState<string>(initial?.difficulty != null ? String(initial.difficulty) : "");
  const [language, setLanguage] = useState(initial?.language ?? "en");
  const [source, setSource] = useState(initial?.source ?? "");
  const [license, setLicense] = useState<LicenseStatus>(initial?.license_status ?? "unconfirmed");
  const [domainId, setDomainId] = useState<string | null>(initial?.mappings.domain_id ?? null);
  const [options, setOptions] = useState<OptionRow[]>(
    initial?.options.map((o) => ({
      content: o.content,
      is_correct: o.is_correct,
      explanation: o.explanation ?? "",
    })) ?? [
      { content: "", is_correct: true, explanation: "" },
      { content: "", is_correct: false, explanation: "" },
    ]
  );
  const [rationale, setRationale] = useState(initial?.explanation?.correct_answer_rationale ?? "");
  const [keyPoint, setKeyPoint] = useState(initial?.explanation?.key_point_summary ?? "");

  const isMulti = type === "multiple_choice";

  function setOption(i: number, patch: Partial<OptionRow>) {
    setOptions((prev) => prev.map((o, idx) => (idx === i ? { ...o, ...patch } : o)));
  }
  function setCorrect(i: number, checked: boolean) {
    setOptions((prev) =>
      prev.map((o, idx) =>
        isMulti ? (idx === i ? { ...o, is_correct: checked } : o) : { ...o, is_correct: idx === i }
      )
    );
  }
  function addOption() {
    setOptions((prev) => [...prev, { content: "", is_correct: false, explanation: "" }]);
  }
  function removeOption(i: number) {
    setOptions((prev) => prev.filter((_, idx) => idx !== i));
  }

  function validate(): string | null {
    if (!stem.trim()) return "Stem is required.";
    const filled = options.filter((o) => o.content.trim());
    if (filled.length < 2) return "Provide at least two options.";
    const correct = filled.filter((o) => o.is_correct).length;
    if (correct === 0) return "Mark at least one correct option.";
    if (!isMulti && correct !== 1) return "Single-answer questions need exactly one correct option.";
    if (!rationale.trim()) return "An answer rationale is required.";
    return null;
  }

  function buildPayload(): QuestionCreateInput {
    const opts: QuestionOption[] = options
      .filter((o) => o.content.trim())
      .map((o, idx) => ({
        content: o.content.trim(),
        is_correct: o.is_correct,
        order_index: idx,
        explanation: o.explanation.trim() || null,
      }));
    return {
      question_type: type,
      stem: stem.trim(),
      difficulty: difficulty.trim() === "" ? null : Number(difficulty),
      language: language.trim() || "en",
      source: source.trim() || null,
      license_status: license,
      options: opts,
      explanation: {
        correct_answer_rationale: rationale.trim(),
        key_point_summary: keyPoint.trim() || null,
      },
      mappings: domainId ? { domain_id: domainId } : {},
    };
  }

  function save() {
    const err = validate();
    if (err) {
      toast.error(err);
      return;
    }
    const payload = buildPayload();
    const onErr = (e: unknown) =>
      toast.error(e instanceof ApiError && e.status === 422 ? "Validation failed — check your inputs." : "Could not save the question.");

    if (initial) {
      update.mutate(payload, {
        onSuccess: (q) => {
          toast.success("Question updated.");
          router.push(`/questions/${q.id}`);
        },
        onError: onErr,
      });
    } else {
      create.mutate(payload, {
        onSuccess: (q) => {
          toast.success("Question created.");
          router.push(`/questions/${q.id}`);
        },
        onError: onErr,
      });
    }
  }

  const pending = create.isPending || update.isPending;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Card>
        <CardHeader><CardTitle>Question</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label>Type</Label>
              <Select value={type} onValueChange={(v) => setType(v as QuestionType)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{TYPES.map((t) => <SelectItem key={t} value={t}>{labelize(t)}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="difficulty">Difficulty (1–5)</Label>
              <Input id="difficulty" type="number" min={1} max={5} value={difficulty} onChange={(e) => setDifficulty(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="language">Language</Label>
              <Input id="language" value={language} onChange={(e) => setLanguage(e.target.value)} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="stem">Stem</Label>
            <Textarea id="stem" rows={4} value={stem} onChange={(e) => setStem(e.target.value)} placeholder="The question text…" />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label>Domain</Label>
              <Select value={domainId ?? ANY} onValueChange={(v) => setDomainId(v === ANY ? null : v)}>
                <SelectTrigger><SelectValue placeholder="Unmapped" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={ANY}>Unmapped</SelectItem>
                  {domains.data?.map((d) => <SelectItem key={d.id} value={d.id}>{d.number}. {d.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>License</Label>
              <Select value={license} onValueChange={(v) => setLicense(v as LicenseStatus)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{LICENSES.map((l) => <SelectItem key={l} value={l}>{labelize(l)}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="source">Source</Label>
              <Input id="source" value={source} onChange={(e) => setSource(e.target.value)} placeholder="e.g. OSG ch.1" />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Options</CardTitle>
          <Button variant="outline" size="sm" onClick={addOption}><Plus className="h-4 w-4" /> Add option</Button>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-muted-foreground">
            {isMulti ? "Check all correct options." : "Select the single correct option."}
          </p>
          {options.map((o, i) => (
            <div key={i} className="flex items-start gap-3 rounded-md border p-3">
              <div className="pt-2">
                <Checkbox
                  checked={o.is_correct}
                  onCheckedChange={(c) => setCorrect(i, c === true)}
                  aria-label="Correct option"
                />
              </div>
              <div className="flex-1 space-y-2">
                <Input value={o.content} onChange={(e) => setOption(i, { content: e.target.value })} placeholder={`Option ${i + 1}`} />
                <Input value={o.explanation} onChange={(e) => setOption(i, { explanation: e.target.value })} placeholder="Why this option is right/wrong (optional)" className="text-sm" />
              </div>
              <Button variant="ghost" size="sm" onClick={() => removeOption(i)} disabled={options.length <= 2} aria-label="Remove option">
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Explanation</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="rationale">Correct-answer rationale</Label>
            <Textarea id="rationale" rows={3} value={rationale} onChange={(e) => setRationale(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="keypoint">Key-point summary (optional)</Label>
            <Textarea id="keypoint" rows={2} value={keyPoint} onChange={(e) => setKeyPoint(e.target.value)} />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={() => router.back()}>Cancel</Button>
        <Button onClick={save} disabled={pending}>
          {pending ? "Saving…" : initial ? "Save changes" : "Create question"}
        </Button>
      </div>
    </div>
  );
}
