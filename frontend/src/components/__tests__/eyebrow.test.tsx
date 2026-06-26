import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Eyebrow } from "@/components/eyebrow";

describe("Eyebrow", () => {
  it("renders its children", () => {
    render(<Eyebrow>Section Label</Eyebrow>);
    expect(screen.getByText("Section Label")).toBeInTheDocument();
  });

  it("applies the eyebrow class", () => {
    render(<Eyebrow>X</Eyebrow>);
    const el = screen.getByText("X");
    expect(el.className).toContain("eyebrow");
    expect(el.className).toContain("uppercase");
    expect(el.className).toContain("text-muted-foreground");
  });

  it("renders as a paragraph by default", () => {
    render(<Eyebrow>X</Eyebrow>);
    expect(screen.getByText("X").tagName).toBe("P");
  });

  it("forwards additional className", () => {
    render(<Eyebrow className="extra">X</Eyebrow>);
    expect(screen.getByText("X").className).toContain("extra");
  });
});
