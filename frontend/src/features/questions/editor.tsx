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
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
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
  QuestionCreateInput,
  LanguageCode,
  Translation,
} from "@/lib/api/types";

const ANY = "__none__";
const TYPES: QuestionType[] = ["single_choice", "multiple_choice", "true_false", "scenario"];
const LICENSES: LicenseStatus[] = ["user_owned", "third_party_licensed", "public_domain", "unconfirmed"];

function labelize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Per-language content for stem / each option / rationale / key point. */
interface LangContent {
  stem: string;
  rationale: string;
  opts: string[];
  keyPoint: string;
}

function emptyLang(optCount: number): LangContent {
  return {
    stem: "",
    rationale: "",
    opts: Array.from({ length: optCount }, () => ""),
    keyPoint: "",
  };
}

function fromTranslation(t: Translation): LangContent {
  return {
    stem: t.stem,
    rationale: t.correct_answer_rationale,
    opts: t.options.map((o) => o.content),
    keyPoint: t.key_point_summary ?? "",
  };
}

export function QuestionEditor({ initial }: { initial?: QuestionDetail }) {
  const router = useRouter();
  const domains = useDomains();
  const create = useCreateQuestion();
  const update = useUpdateQuestion(initial?.id ?? "");

  const initOpts = initial?.options ?? [{ is_correct: true }, { is_correct: false }];
  const initEn = initial?.translations.find((t) => t.language === "en");
  const initZh = initial?.translations.find((t) => t.language === "zh");

  const [type, setType] = useState<QuestionType>(initial?.question_type ?? "single_choice");
  const [difficulty, setDifficulty] = useState<string>(
    initial?.difficulty != null ? String(initial.difficulty) : "",
  );
  const [source, setSource] = useState(initial?.source ?? "");
  const [license, setLicense] = useState<LicenseStatus>(initial?.license_status ?? "unconfirmed");
  const [domainId, setDomainId] = useState<string | null>(initial?.mappings.domain_id ?? null);

  // Canonical options: shared correctness + order across languages.
  const [options, setOptions] = useState<{ is_correct: boolean }[]>(
    initOpts.map((o) => ({ is_correct: o.is_correct })),
  );
  // Per-language content. English is always present; Chinese is null until the
  // author opts in via "Add Chinese version".
  const [en, setEn] = useState<LangContent>(
    initEn ? fromTranslation(initEn) : emptyLang(initOpts.length),
  );
  const [zh, setZh] = useState<LangContent | null>(initZh ? fromTranslation(initZh) : null);
  const [tab, setTab] = useState<LanguageCode>("en");

  const isMulti = type === "multiple_choice";

  function setCorrect(i: number, checked: boolean) {
    setOptions((prev) =>
      prev.map((o, idx) =>
        isMulti ? (idx === i ? { ...o, is_correct: checked } : o) : { ...o, is_correct: idx === i },
      ),
    );
  }
  function addOption() {
    setOptions((prev) => [...prev, { is_correct: false }]);
    setEn((prev) => ({ ...prev, opts: [...prev.opts, ""] }));
    setZh((prev) => (prev ? { ...prev, opts: [...prev.opts, ""] } : prev));
  }
  function removeOption(i: number) {
    setOptions((prev) => prev.filter((_, idx) => idx !== i));
    setEn((prev) => ({ ...prev, opts: prev.opts.filter((_, idx) => idx !== i) }));
    setZh((prev) => (prev ? { ...prev, opts: prev.opts.filter((_, idx) => idx !== i) } : prev));
  }

  function enableZh() {
    setZh(emptyLang(options.length));
    setTab("zh");
  }
  function disableZh() {
    setZh(null);
    setTab("en");
  }

  // English setters.
  const setEnStem = (v: string) => setEn((p) => ({ ...p, stem: v }));
  const setEnRationale = (v: string) => setEn((p) => ({ ...p, rationale: v }));
  const setEnKeyPoint = (v: string) => setEn((p) => ({ ...p, keyPoint: v }));
  const setEnOpt = (i: number, v: string) =>
    setEn((p) => ({ ...p, opts: p.opts.map((c, idx) => (idx === i ? v : c)) }));
  // Chinese setters (no-op when zh is null — the zh tab body is only rendered
  // when zh is set, so these are never called with a null zh).
  const setZhStem = (v: string) => setZh((p) => (p ? { ...p, stem: v } : p));
  const setZhRationale = (v: string) => setZh((p) => (p ? { ...p, rationale: v } : p));
  const setZhKeyPoint = (v: string) => setZh((p) => (p ? { ...p, keyPoint: v } : p));
  const setZhOpt = (i: number, v: string) =>
    setZh((p) => (p ? { ...p, opts: p.opts.map((c, idx) => (idx === i ? v : c)) } : p));

  function validate(): string | null {
    if (!en.stem.trim()) return "English stem is required.";
    const enFilled = en.opts.filter((c) => c.trim());
    if (enFilled.length < 2) return "Provide at least two options with content.";
    const correct = options.filter((o) => o.is_correct).length;
    if (correct === 0) return "Mark at least one correct option.";
    if (!isMulti && correct !== 1) return "Single-answer questions need exactly one correct option.";
    if (!en.rationale.trim()) return "An English answer rationale is required.";
    // Completeness: when a Chinese version is enabled, every field must be filled
    // (mirrors the backend publish rule FR-LANG-09).
    if (zh) {
      if (!zh.stem.trim()) return "Chinese stem is required when a Chinese version is enabled.";
      if (zh.opts.some((c) => !c.trim())) return "All Chinese option contents are required.";
      if (!zh.rationale.trim()) return "Chinese answer rationale is required.";
    }
    return null;
  }

  function buildPayload(): QuestionCreateInput {
    const canonical = options.map((o, i) => ({ order_index: i, is_correct: o.is_correct }));
    const translations: Translation[] = [
      {
        language: "en",
        stem: en.stem.trim(),
        correct_answer_rationale: en.rationale.trim(),
        key_point_summary: en.keyPoint.trim() || null,
        options: en.opts.map((c, i) => ({ order_index: i, content: c.trim() })),
      },
    ];
    if (zh) {
      translations.push({
        language: "zh",
        stem: zh.stem.trim(),
        correct_answer_rationale: zh.rationale.trim(),
        key_point_summary: zh.keyPoint.trim() || null,
        options: zh.opts.map((c, i) => ({ order_index: i, content: c.trim() })),
      });
    }
    return {
      question_type: type,
      difficulty: difficulty.trim() === "" ? null : Number(difficulty),
      source: source.trim() || null,
      license_status: license,
      options: canonical,
      translations,
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
      toast.error(
        e instanceof ApiError && e.status === 422
          ? "Validation failed — check your inputs."
          : "Could not save the question.",
      );

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

  /** Render the stem / options / rationale inputs for one language. */
  function renderLangContent(
    lang: LanguageCode,
    c: LangContent,
    onStem: (v: string) => void,
    onOpt: (i: number, v: string) => void,
    onRationale: (v: string) => void,
    onKeyPoint: (v: string) => void,
  ) {
    return (
      <div className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor={`stem-${lang}`}>Stem</Label>
          <Textarea
            id={`stem-${lang}`}
            rows={4}
            value={c.stem}
            onChange={(e) => onStem(e.target.value)}
            placeholder="The question text…"
          />
        </div>

        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            {isMulti ? "Check all correct options." : "Select the single correct option."}
          </p>
          {options.map((o, i) => (
            <div key={i} className="flex items-start gap-3 rounded-md border p-3">
              <div className="pt-2">
                <Checkbox
                  checked={o.is_correct}
                  onCheckedChange={(ck) => setCorrect(i, ck === true)}
                  aria-label={`Option ${i + 1} correct`}
                />
              </div>
              <div className="flex-1">
                <Input
                  value={c.opts[i] ?? ""}
                  onChange={(e) => onOpt(i, e.target.value)}
                  aria-label={`Option ${i + 1} content`}
                  placeholder={`Option ${i + 1}`}
                />
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removeOption(i)}
                disabled={options.length <= 2}
                aria-label={`Remove option ${i + 1}`}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={addOption}>
            <Plus className="h-4 w-4" /> Add option
          </Button>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor={`rationale-${lang}`}>Correct-answer rationale</Label>
          <Textarea
            id={`rationale-${lang}`}
            rows={3}
            value={c.rationale}
            onChange={(e) => onRationale(e.target.value)}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor={`keypoint-${lang}`}>Key point summary</Label>
          <Textarea
            id={`keypoint-${lang}`}
            rows={2}
            value={c.keyPoint}
            onChange={(e) => onKeyPoint(e.target.value)}
            placeholder="Optional one-line takeaway…"
          />
        </div>
      </div>
    );
  }

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
              <Label>Domain</Label>
              <Select value={domainId ?? ANY} onValueChange={(v) => setDomainId(v === ANY ? null : v)}>
                <SelectTrigger><SelectValue placeholder="Unmapped" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={ANY}>Unmapped</SelectItem>
                  {domains.data?.map((d) => <SelectItem key={d.id} value={d.id}>{d.number}. {d.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle>Content</CardTitle>
          {zh ? (
            <Button variant="ghost" size="sm" onClick={disableZh}>Remove Chinese version</Button>
          ) : (
            <Button variant="outline" size="sm" onClick={enableZh}>Add Chinese version</Button>
          )}
        </CardHeader>
        <CardContent>
          <Tabs value={tab} onValueChange={(v) => setTab(v as LanguageCode)}>
            <TabsList>
              <TabsTrigger value="en">English</TabsTrigger>
              <TabsTrigger value="zh" disabled={!zh}>中文</TabsTrigger>
            </TabsList>
            <TabsContent value="en">
              {renderLangContent("en", en, setEnStem, setEnOpt, setEnRationale, setEnKeyPoint)}
            </TabsContent>
            <TabsContent value="zh">
              {zh && renderLangContent("zh", zh, setZhStem, setZhOpt, setZhRationale, setZhKeyPoint)}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <div className="flex justify-end gap-2">
        <Button variant="outline" size="pill" onClick={() => router.back()}>Cancel</Button>
        <Button size="pill" onClick={save} disabled={pending}>
          {pending ? "Saving…" : initial ? "Save changes" : "Create question"}
        </Button>
      </div>
    </div>
  );
}
