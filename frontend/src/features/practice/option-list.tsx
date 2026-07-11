"use client";

import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Checkbox } from "@/components/ui/checkbox";
import { BilingualText } from "@/components/bilingual-text";
import { cn } from "@/lib/utils";
import { CheckCircle2, XCircle } from "lucide-react";
import type { ReactNode } from "react";
import type { OptionDelivery, QuestionType, AnswerResult, LanguageMode } from "@/lib/api/types";

// #34 / NFR-UX-04: highlight the whole option row when its inner control is
// keyboard-focused, not just the 20px radio/checkbox dot.
const FOCUS_RING =
  "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring " +
  "has-[:focus-visible]:ring-offset-2 has-[:focus-visible]:ring-offset-background";

export function OptionList({
  questionType,
  options,
  selected,
  onToggle,
  disabled = false,
  result = null,
  mode = "en",
}: {
  questionType: QuestionType;
  options: OptionDelivery[];
  selected: number[];
  onToggle: (orderIndex: number) => void;
  disabled?: boolean;
  result?: AnswerResult | null;
  /**
   * Language mode used to render each option's content. Defaults to `"en"` so
   * callers that have not been migrated to bilingual delivery (e.g. the exam
   * runners in T13) keep typechecking and rendering English.
   */
  mode?: LanguageMode;
}) {
  const isMulti = questionType === "multiple_choice";
  const correct = new Set(result?.correct_indexes ?? []);

  function rowClass(orderIndex: number): string {
    if (!result) {
      return selected.includes(orderIndex) ? "border-primary" : "border-border";
    }
    if (correct.has(orderIndex)) return "border-success bg-success/10";
    if (selected.includes(orderIndex)) return "border-destructive bg-destructive/10";
    return "border-border";
  }

  // #34 / NFR-UX-05: a non-color cue (icon) for per-option correctness in
  // result mode, so the green/red border isn't the only signal. Decorative
  // (aria-hidden) - the overall result text/icons live in the runner's panel.
  function resultIcon(orderIndex: number): ReactNode {
    if (!result) return null;
    if (correct.has(orderIndex)) {
      return <CheckCircle2 className="ml-auto h-5 w-5 shrink-0 text-success" aria-hidden="true" />;
    }
    if (selected.includes(orderIndex)) {
      return <XCircle className="ml-auto h-5 w-5 shrink-0 text-destructive" aria-hidden="true" />;
    }
    return null;
  }

  if (isMulti) {
    return (
      <div className="space-y-2">
        {options.map((o) => (
          <label
            key={o.order_index}
            className={cn("flex cursor-pointer items-start gap-3 rounded-md border p-3", FOCUS_RING, rowClass(o.order_index))}
          >
            <Checkbox
              checked={selected.includes(o.order_index)}
              disabled={disabled}
              onCheckedChange={() => onToggle(o.order_index)}
            />
            <BilingualText mode={mode} en={o.content.en} zh={o.content.zh} className="text-sm" />
            {resultIcon(o.order_index)}
          </label>
        ))}
      </div>
    );
  }

  return (
    <RadioGroup
      value={selected[0] != null ? String(selected[0]) : undefined}
      disabled={disabled}
      onValueChange={(v) => onToggle(Number(v))}
      className="space-y-2"
    >
      {options.map((o) => (
        <label
          key={o.order_index}
          className={cn("flex cursor-pointer items-start gap-3 rounded-md border p-3", FOCUS_RING, rowClass(o.order_index))}
        >
          <RadioGroupItem value={String(o.order_index)} />
          <BilingualText mode={mode} en={o.content.en} zh={o.content.zh} className="text-sm" />
          {resultIcon(o.order_index)}
        </label>
      ))}
    </RadioGroup>
  );
}
