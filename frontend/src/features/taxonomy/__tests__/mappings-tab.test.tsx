import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "@/test/render-with-providers";
import { MappingsTab } from "../mappings-tab";

const createMutate = vi.fn();

vi.mock("@/lib/api/etl", () => ({
  useMappings: () => ({
    data: [
      {
        id: "m1",
        dataset_slug: "osg10",
        chapter_number: 1,
        chapter_title: "Security and Risk Management",
        domain_id: "d1",
      },
    ],
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useCreateMapping: () => ({ mutate: createMutate, isPending: false }),
  useUpdateMapping: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteMapping: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock("@/lib/api/taxonomy", () => ({
  useDomains: () => ({
    data: [{ id: "d1", blueprint_id: "bp", number: 1, name: "Security and Risk Management", weight_pct: 15 }],
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/components/ui/sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() },
}));

describe("MappingsTab (FR-ETL-15)", () => {
  beforeEach(() => {
    createMutate.mockReset();
    window.HTMLElement.prototype.hasPointerCapture = vi.fn();
    window.HTMLElement.prototype.releasePointerCapture = vi.fn();
    window.HTMLElement.prototype.setPointerCapture = vi.fn();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it("lists existing mappings and create form fields", () => {
    renderWithProviders(<MappingsTab />);
    expect(screen.getByText("New chapter→domain mapping")).toBeInTheDocument();
    expect(screen.getByLabelText("Dataset slug")).toBeInTheDocument();
    expect(screen.getByLabelText("Chapter #")).toBeInTheDocument();
    expect(screen.getByLabelText("Chapter title")).toBeInTheDocument();
    expect(screen.getByText("Security and Risk Management")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add mapping" })).toBeEnabled();
  });

  it("does not create when required fields are empty", () => {
    renderWithProviders(<MappingsTab />);
    fireEvent.click(screen.getByRole("button", { name: "Add mapping" }));
    expect(createMutate).not.toHaveBeenCalled();
  });

  it("creates a mapping with dataset slug, chapter number, title, and domain", () => {
    renderWithProviders(<MappingsTab />);
    fireEvent.change(screen.getByLabelText("Dataset slug"), { target: { value: "osg10" } });
    fireEvent.change(screen.getByLabelText("Chapter #"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Chapter title"), { target: { value: "Asset Security" } });
    fireEvent.click(screen.getByRole("button", { name: "Add mapping" }));
    expect(createMutate).toHaveBeenCalledTimes(1);
    expect(createMutate.mock.calls[0][0]).toEqual({
      dataset_slug: "osg10",
      chapter_number: 2,
      chapter_title: "Asset Security",
      domain_id: null,
    });
  });
});
