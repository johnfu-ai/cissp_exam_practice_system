"use client";

import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import type { OptionDelivery, QuestionType, AnswerResult } from "@/lib/api/types";

export function OptionList({
  questionType,
  options,
  selected,
  onToggle,
  disabled = false,
  result = null,
}: {
  questionType: QuestionType;
  options: OptionDelivery[];
  selected: number[];
  onToggle: (orderIndex: number) => void;
  disabled?: boolean;
  result?: AnswerResult | null;
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
            <span className="text-sm">{o.content}</span>
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
          <span className="text-sm">{o.content}</span>
        </label>
      ))}
    </RadioGroup>
  );
}
