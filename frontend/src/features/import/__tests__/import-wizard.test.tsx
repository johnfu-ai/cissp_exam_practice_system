import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nProvider } from "@/lib/i18n/provider";
import { ImportWizard } from "../import-wizard";

const uploadMutate = vi.fn();

vi.mock("@/lib/api/etl", () => ({
  useDatasets: () => ({ data: [], isLoading: false, isError: false }),
  useCreateRun: () => ({ mutate: vi.fn(), isPending: false }),
  useCommitRun: () => ({ mutate: vi.fn(), isPending: false }),
  useRollbackRun: () => ({ mutate: vi.fn(), isPending: false }),
  useUploadDataset: () => ({ mutate: uploadMutate, isPending: false }),
}));

// sonner toasts render into a portal; stub them so the test never depends on it.
vi.mock("@/components/ui/sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() },
}));

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <I18nProvider initialLocale="en">{ui}</I18nProvider>
    </QueryClientProvider>,
  );
}

describe("ImportWizard upload (#35)", () => {
  beforeEach(() => {
    uploadMutate.mockReset();
  });

  it("renders the upload card with dataset-name + file inputs and the button", () => {
    wrap(<ImportWizard />);
    expect(screen.getByLabelText("Dataset name")).toBeInTheDocument();
    expect(screen.getByLabelText("CSV, XLSX, or JSON")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload & preview" })).toBeEnabled();
  });

  it("does not call upload when the dataset name is missing", () => {
    wrap(<ImportWizard />);
    fireEvent.click(screen.getByRole("button", { name: "Upload & preview" }));
    expect(uploadMutate).not.toHaveBeenCalled();
  });

  it("uploads slug + file when both are provided", () => {
    wrap(<ImportWizard />);
    fireEvent.change(screen.getByLabelText("Dataset name"), {
      target: { value: "my-batch" },
    });
    const file = new File(["question_text\n"], "q.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText("CSV, XLSX, or JSON"), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload & preview" }));
    expect(uploadMutate).toHaveBeenCalledTimes(1);
    const [args] = uploadMutate.mock.calls[0];
    expect(args).toEqual({ file, datasetSlug: "my-batch" });
  });

  it("trims the dataset slug before uploading", () => {
    wrap(<ImportWizard />);
    fireEvent.change(screen.getByLabelText("Dataset name"), {
      target: { value: "  spaced  " },
    });
    const file = new File(["x\n"], "q.json", { type: "application/json" });
    fireEvent.change(screen.getByLabelText("CSV, XLSX, or JSON"), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload & preview" }));
    expect(uploadMutate.mock.calls[0][0].datasetSlug).toBe("spaced");
  });
});
