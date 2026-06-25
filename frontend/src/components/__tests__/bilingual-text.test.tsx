import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BilingualText } from "@/components/bilingual-text";

describe("BilingualText", () => {
  it("en mode shows english only", () => {
    render(<BilingualText mode="en" en="Hello" zh="你好" />);
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.queryByText("你好")).not.toBeInTheDocument();
  });

  it("zh mode shows chinese only", () => {
    render(<BilingualText mode="zh" en="Hello" zh="你好" />);
    expect(screen.getByText("你好")).toBeInTheDocument();
  });

  it("bilingual shows both", () => {
    render(<BilingualText mode="bilingual" en="Hello" zh="你好" />);
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByText("你好")).toBeInTheDocument();
  });

  it("falls back to other language when one is null", () => {
    render(<BilingualText mode="en" en={null} zh="你好" />);
    expect(screen.getByText("你好")).toBeInTheDocument();
  });
});
