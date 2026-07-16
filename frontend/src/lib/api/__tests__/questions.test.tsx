import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import * as apiModule from "@/lib/api";
import { useCreateQuestion, useDeleteQuestion, useReviewQuestion } from "@/lib/api/questions";

// #31: question mutations must invalidate the questions LIST cache so list
// views don't show stale rows after a create/delete/review.

vi.mock("@/lib/api");

function wrapper(qc: QueryClient) {
  function TestWrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return TestWrapper;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("question mutation cache invalidation (#31)", () => {
  it("useCreateQuestion invalidates the questions list on success", async () => {
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    vi.mocked(apiModule.apiJson).mockResolvedValueOnce({ id: "q1" } as never);

    const { result } = renderHook(() => useCreateQuestion(), { wrapper: wrapper(qc) });
    result.current.mutate({} as never);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(spy).toHaveBeenCalledWith({ queryKey: ["questions", "list"] });
  });

  it("useDeleteQuestion invalidates the list + removes the detail", async () => {
    const qc = new QueryClient();
    const invSpy = vi.spyOn(qc, "invalidateQueries");
    const remSpy = vi.spyOn(qc, "removeQueries");
    vi.mocked(apiModule.apiJson).mockResolvedValueOnce({ deleted: "q1" } as never);

    const { result } = renderHook(() => useDeleteQuestion(), { wrapper: wrapper(qc) });
    result.current.mutate("q1");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invSpy).toHaveBeenCalledWith({ queryKey: ["questions", "list"] });
    expect(remSpy).toHaveBeenCalledWith({ queryKey: ["questions", "detail", "q1"] });
  });

  it("useReviewQuestion invalidates the list on success (status changes)", async () => {
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    vi.mocked(apiModule.apiJson).mockResolvedValueOnce({ id: "q1" } as never);

    const { result } = renderHook(() => useReviewQuestion("q1"), { wrapper: wrapper(qc) });
    result.current.mutate({ action: "approve" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(spy).toHaveBeenCalledWith({ queryKey: ["questions", "list"] });
  });
});
