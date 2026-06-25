import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OptionList } from "@/features/practice/option-list";
import type { OptionDelivery } from "@/lib/api/types";

const options: OptionDelivery[] = [
  { id: "o0", order_index: 0, content: "Alpha", content_format: "plain" },
  { id: "o1", order_index: 1, content: "Bravo", content_format: "plain" },
  { id: "o2", order_index: 2, content: "Charlie", content_format: "plain" },
];

describe("OptionList", () => {
  it("renders single_choice options as radios with their content", () => {
    render(
      <OptionList questionType="single_choice" options={options} selected={[]} onToggle={() => {}} />
    );
    expect(screen.getAllByRole("radio")).toHaveLength(3);
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Charlie")).toBeInTheDocument();
  });

  it("renders multiple_choice options as checkboxes", () => {
    render(
      <OptionList questionType="multiple_choice" options={options} selected={[]} onToggle={() => {}} />
    );
    expect(screen.getAllByRole("checkbox")).toHaveLength(3);
  });

  it("renders true_false options as radios", () => {
    const tf: OptionDelivery[] = [
      { id: "t", order_index: 0, content: "True", content_format: "plain" },
      { id: "f", order_index: 1, content: "False", content_format: "plain" },
    ];
    render(<OptionList questionType="true_false" options={tf} selected={[]} onToggle={() => {}} />);
    expect(screen.getAllByRole("radio")).toHaveLength(2);
  });

  it("calls onToggle with the option order_index when a radio is clicked", async () => {
    const onToggle = vi.fn();
    render(
      <OptionList questionType="single_choice" options={options} selected={[]} onToggle={onToggle} />
    );
    await userEvent.click(screen.getAllByRole("radio")[1]);
    expect(onToggle).toHaveBeenCalledWith(1);
  });

  it("calls onToggle when a checkbox is clicked", async () => {
    const onToggle = vi.fn();
    render(
      <OptionList questionType="multiple_choice" options={options} selected={[0]} onToggle={onToggle} />
    );
    await userEvent.click(screen.getAllByRole("checkbox")[2]);
    expect(onToggle).toHaveBeenCalledWith(2);
  });
});
