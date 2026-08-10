import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "@/test/render-with-providers";
import { KpDomainBindings } from "../knowledge-points-tab";

const bindMutate = vi.fn();
const unbindMutate = vi.fn();

vi.mock("@/lib/api/taxonomy", () => ({
  useDomains: () => ({
    data: [
      { id: "d1", blueprint_id: "bp", number: 1, name: "Security", weight_pct: 15 },
      { id: "d2", blueprint_id: "bp", number: 2, name: "Asset Security", weight_pct: 10 },
    ],
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/lib/api/taxonomy-admin", () => ({
  useKpDomains: () => ({
    data: [{ id: "d1", blueprint_id: "bp", number: 1, name: "Security", weight_pct: 15 }],
    isLoading: false,
    isError: false,
  }),
  useBindKpDomain: () => ({ mutate: bindMutate, isPending: false }),
  useUnbindKpDomain: () => ({ mutate: unbindMutate, isPending: false }),
}));

vi.mock("@/components/ui/sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() },
}));

describe("KpDomainBindings (FR-TAX-04/05)", () => {
  beforeEach(() => {
    bindMutate.mockReset();
    unbindMutate.mockReset();
  });

  it("renders domain checkboxes with bound domains checked", () => {
    renderWithProviders(<KpDomainBindings kpId="kp1" />);
    expect(screen.getByTestId("kp-domains-kp1")).toBeInTheDocument();
    const security = screen.getByLabelText("1. Security");
    const asset = screen.getByLabelText("2. Asset Security");
    expect(security).toBeChecked();
    expect(asset).not.toBeChecked();
  });

  it("binds an unbound domain when checked", () => {
    renderWithProviders(<KpDomainBindings kpId="kp1" />);
    fireEvent.click(screen.getByLabelText("2. Asset Security"));
    expect(bindMutate).toHaveBeenCalledWith(
      { kpId: "kp1", domainId: "d2" },
      expect.any(Object),
    );
    expect(unbindMutate).not.toHaveBeenCalled();
  });

  it("unbinds a bound domain when unchecked", () => {
    renderWithProviders(<KpDomainBindings kpId="kp1" />);
    fireEvent.click(screen.getByLabelText("1. Security"));
    expect(unbindMutate).toHaveBeenCalledWith(
      { kpId: "kp1", domainId: "d1" },
      expect.any(Object),
    );
    expect(bindMutate).not.toHaveBeenCalled();
  });
});
