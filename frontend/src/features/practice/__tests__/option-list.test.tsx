import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OptionList } from "@/features/practice/option-list";
import type { OptionDelivery } from "@/lib/api/types";

const options: OptionDelivery[] = [
  { id: "o0", order_index: 0, content: { en: "Alpha", zh: "阿尔法" }, content_format: { en: "plain", zh: "plain" } },
  { id: "o1", order_index: 1, content: { en: "Bravo", zh: "布拉沃" }, content_format: { en: "plain", zh: "plain" } },
  { id: "o2", order_index: 2, content: { en: "Charlie", zh: "查理" }, content_format: { en: "plain", zh: "plain" } },
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
      { id: "t", order_index: 0, content: { en: "True", zh: "对" }, content_format: { en: "plain", zh: "plain" } },
      { id: "f", order_index: 1, content: { en: "False", zh: "错" }, content_format: { en: "plain", zh: "plain" } },
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

  it("renders both en and zh content in bilingual mode", () => {
    render(
      <OptionList
        mode="bilingual"
        questionType="single_choice"
        options={options}
        selected={[]}
        onToggle={() => {}}
      />
    );
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("阿尔法")).toBeInTheDocument();
    expect(screen.getByText("Charlie")).toBeInTheDocument();
    expect(screen.getByText("查理")).toBeInTheDocument();
  });

  it("renders only en content in en mode", () => {
    render(
      <OptionList
        mode="en"
        questionType="single_choice"
        options={options}
        selected={[]}
        onToggle={() => {}}
      />
    );
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.queryByText("阿尔法")).not.toBeInTheDocument();
  });

  it("renders only zh content in zh mode", () => {
    render(
      <OptionList
        mode="zh"
        questionType="single_choice"
        options={options}
        selected={[]}
        onToggle={() => {}}
      />
    );
    expect(screen.queryByText("Alpha")).not.toBeInTheDocument();
    expect(screen.getByText("阿尔法")).toBeInTheDocument();
  });

  it("defaults to en mode when mode is omitted (back-compat for exam callers)", () => {
    render(
      <OptionList questionType="single_choice" options={options} selected={[]} onToggle={() => {}} />
    );
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.queryByText("阿尔法")).not.toBeInTheDocument();
  });
});
