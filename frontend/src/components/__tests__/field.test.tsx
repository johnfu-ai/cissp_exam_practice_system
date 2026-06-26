import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Mail } from "lucide-react";
import { Field } from "@/components/field";
import { Input } from "@/components/ui/input";

describe("Field", () => {
  it("renders the label and input", () => {
    render(
      <Field label="Email" htmlFor="e">
        <Input id="e" />
      </Field>
    );
    expect(screen.getByText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
  });

  it("renders a leading icon when provided", () => {
    render(
      <Field icon={Mail} htmlFor="e">
        <Input id="e" />
      </Field>
    );
    // lucide renders an <svg>; presence of svg inside the field surface
    expect(document.querySelector(".field-surface svg")).toBeInTheDocument();
  });

  it("omits the surface wrapper class when no icon", () => {
    render(
      <Field htmlFor="e">
        <Input id="e" />
      </Field>
    );
    expect(document.querySelector(".field-surface")).toBeNull();
  });

  it("forwards wrapper className", () => {
    render(
      <Field htmlFor="e" className="my-4">
        <Input id="e" />
      </Field>
    );
    // No label is rendered in this case, so getByLabelText("") cannot resolve.
    // Traverse from the input (stable id) up to the outer wrapper div that
    // receives the forwarded className.
    const wrapper = document.getElementById("e")?.parentElement?.parentElement;
    expect(wrapper?.className).toContain("my-4");
  });
});
