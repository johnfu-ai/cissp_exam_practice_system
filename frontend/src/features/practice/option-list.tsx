"use client";

import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Checkbox } from "@/components/ui/checkbox";
import { BilingualText } from "@/components/bilingual-text";
import { cn } from "@/lib/utils";
import type { OptionDelivery, QuestionType, AnswerResult, LanguageMode } from "@/lib/api/types";

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

  if (isMulti) {
    return (
      <div className="space-y-2">
        {options.map((o) => (
          <label
            key={o.order_index}
            className={cn("flex cursor-pointer items-start gap-3 rounded-md border p-3", rowClass(o.order_index))}
          >
            <Checkbox
              checked={selected.includes(o.order_index)}
              disabled={disabled}
              onCheckedChange={() => onToggle(o.order_index)}
            />
            <BilingualText mode={mode} en={o.content.en} zh={o.content.zh} className="text-sm" />
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
          className={cn("flex cursor-pointer items-start gap-3 rounded-md border p-3", rowClass(o.order_index))}
        >
          <RadioGroupItem value={String(o.order_index)} />
          <BilingualText mode={mode} en={o.content.en} zh={o.content.zh} className="text-sm" />
        </label>
      ))}
    </RadioGroup>
  );
}
