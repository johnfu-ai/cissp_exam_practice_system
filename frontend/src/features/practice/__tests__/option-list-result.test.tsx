import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { OptionList } from "@/features/practice/option-list";
import type { OptionDelivery, AnswerResult } from "@/lib/api/types";

const options: OptionDelivery[] = [
  { id: "o0", order_index: 0, content: { en: "Alpha", zh: "阿尔法" }, content_format: { en: "plain", zh: "plain" } },
  { id: "o1", order_index: 1, content: { en: "Bravo", zh: "布拉沃" }, content_format: { en: "plain", zh: "plain" } },
  { id: "o2", order_index: 2, content: { en: "Charlie", zh: "查理" }, content_format: { en: "plain", zh: "plain" } },
];

// option 1 is the correct answer; option 0 is the user's wrong pick.
const result: AnswerResult = {
  is_correct: false,
  correct_indexes: [1],
  selected_indexes: [0],
  correct_rationale: { en: null, zh: null },
  key_point_summary: { en: null, zh: null },
  per_option: [],
  mapping: {},
  history: [],
};

describe("OptionList result-mode non-color cues (#34 NFR-UX-05)", () => {
  it("shows a check icon on the correct option and an X on a wrong pick", () => {
    const { container } = render(
      <OptionList
        questionType="single_choice"
        options={options}
        selected={[0]}
        onToggle={() => {}}
        result={result}
      />
    );
    // option 1 is correct -> check; option 0 is a wrong pick -> X; option 2 neither.
    expect(container.querySelectorAll("svg.text-success")).toHaveLength(1);
    expect(container.querySelectorAll("svg.text-destructive")).toHaveLength(1);
    // radio roles + option text are unchanged.
    expect(screen.getAllByRole("radio")).toHaveLength(3);
    expect(screen.getByText("Alpha")).toBeInTheDocument();
  });

  it("renders no result icons when there is no result", () => {
    const { container } = render(
      <OptionList questionType="single_choice" options={options} selected={[0]} onToggle={() => {}} />
    );
    expect(container.querySelector("svg.text-success")).toBeNull();
    expect(container.querySelector("svg.text-destructive")).toBeNull();
  });
});
