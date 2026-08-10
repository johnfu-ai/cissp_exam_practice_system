import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import * as apiModule from "@/lib/api";
import { useCreateMapping, useDeleteMapping, useUpdateMapping } from "@/lib/api/etl";
import { useBindKpDomain, useUnbindKpDomain } from "@/lib/api/taxonomy-admin";

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

describe("ETL mapping mutation cache invalidation (FR-ETL-15)", () => {
  it("useCreateMapping invalidates mappings on success", async () => {
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    vi.mocked(apiModule.apiJson).mockResolvedValueOnce({ id: "m1", dataset_slug: "osg10", chapter_number: 1 } as never);

    const { result } = renderHook(() => useCreateMapping(), { wrapper: wrapper(qc) });
    result.current.mutate({
      dataset_slug: "osg10",
      chapter_number: 1,
      chapter_title: "Security",
      domain_id: "d1",
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(apiModule.apiJson).toHaveBeenCalledWith(
      "/api/etl/mappings",
      expect.objectContaining({ method: "POST" }),
    );
    expect(spy).toHaveBeenCalledWith({ queryKey: ["etl", "mappings"] });
  });

  it("useUpdateMapping PUTs by id and invalidates mappings", async () => {
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    vi.mocked(apiModule.apiJson).mockResolvedValueOnce({ id: "m1" } as never);

    const { result } = renderHook(() => useUpdateMapping(), { wrapper: wrapper(qc) });
    result.current.mutate({
      id: "m1",
      body: {
        dataset_slug: "osg10",
        chapter_number: 1,
        chapter_title: "Updated",
        domain_id: null,
      },
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(apiModule.apiJson).toHaveBeenCalledWith(
      "/api/etl/mappings/m1",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(spy).toHaveBeenCalledWith({ queryKey: ["etl", "mappings"] });
  });

  it("useDeleteMapping DELETEs by id and invalidates mappings", async () => {
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    vi.mocked(apiModule.apiJson).mockResolvedValueOnce({ deleted: "m1" } as never);

    const { result } = renderHook(() => useDeleteMapping(), { wrapper: wrapper(qc) });
    result.current.mutate("m1");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(apiModule.apiJson).toHaveBeenCalledWith(
      "/api/etl/mappings/m1",
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(spy).toHaveBeenCalledWith({ queryKey: ["etl", "mappings"] });
  });
});

describe("KP domain binding mutation cache invalidation (FR-TAX-04/05)", () => {
  it("useBindKpDomain POSTs BindingIn and invalidates kp domains", async () => {
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    vi.mocked(apiModule.apiJson).mockResolvedValueOnce({
      id: "d1", blueprint_id: "bp", number: 1, name: "Security", weight_pct: 15,
    } as never);

    const { result } = renderHook(() => useBindKpDomain(), { wrapper: wrapper(qc) });
    result.current.mutate({ kpId: "kp1", domainId: "d1" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(apiModule.apiJson).toHaveBeenCalledWith(
      "/api/admin/knowledge-points/kp1/domains",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ domain_id: "d1" }),
      }),
    );
    expect(spy).toHaveBeenCalledWith({ queryKey: ["knowledge-points", "kp1", "domains"] });
  });

  it("useUnbindKpDomain DELETEs and invalidates kp domains", async () => {
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    vi.mocked(apiModule.apiJson).mockResolvedValueOnce({ deleted: "d1" } as never);

    const { result } = renderHook(() => useUnbindKpDomain(), { wrapper: wrapper(qc) });
    result.current.mutate({ kpId: "kp1", domainId: "d1" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(apiModule.apiJson).toHaveBeenCalledWith(
      "/api/admin/knowledge-points/kp1/domains/d1",
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(spy).toHaveBeenCalledWith({ queryKey: ["knowledge-points", "kp1", "domains"] });
  });
});
