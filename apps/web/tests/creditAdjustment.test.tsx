import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CreditAdjustmentForm } from "@/components/features/CreditAdjustmentForm";
import { parseAdjustment } from "@/helpers/credit";
import { adminService } from "@/services/admin.service";

import { messages, renderWithIntl } from "./render";

vi.mock("@/services/admin.service", () => ({
  adminService: { adjustCredit: vi.fn() },
}));

const eur = (cents: number) => ({ amount_cents: cents, currency: "EUR", formatted: "" });

describe("parseAdjustment", () => {
  it("turns a credit in euros with a comma into positive cents", () => {
    expect(parseAdjustment("credit", "12,50", " Compensación ")).toEqual({
      ok: true,
      amountCents: 1250,
      note: "Compensación",
    });
  });

  it("makes a debit negative", () => {
    expect(parseAdjustment("debit", "5", "Cargo por error")).toMatchObject({ amountCents: -500 });
  });

  it.each(["0", "", "-3", "abc", "1000,01", "1,234"])("refuses the amount %j", (amount) => {
    expect(parseAdjustment("credit", amount, "Motivo")).toEqual({
      ok: false,
      error: "adjustmentAmount",
    });
  });

  it("needs a reason", () => {
    expect(parseAdjustment("credit", "5", "  ")).toEqual({ ok: false, error: "adjustmentNote" });
  });
});

// Las etiquetas llevan el asterisco de obligatorio detras: se busca por prefijo.
const label = (text: string) => new RegExp(`^${text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`);

describe("CreditAdjustmentForm", () => {
  function fill(amount: string, note: string) {
    fireEvent.change(screen.getByLabelText(label(messages.admin.adjustment.amount)), {
      target: { value: amount },
    });
    fireEvent.change(screen.getByLabelText(label(messages.admin.adjustment.note)), {
      target: { value: note },
    });
  }

  it("sends the credit in cents and reports the debt that is left", async () => {
    vi.mocked(adminService.adjustCredit).mockResolvedValue({
      status: "active",
      is_active: true,
      balance: eur(0),
      debt: eur(200),
      current_period_end: null,
    });
    const onAdjusted = vi.fn();
    renderWithIntl(<CreditAdjustmentForm professionalId="pro-1" onAdjusted={onAdjusted} />);

    fill("3", "Regularización parcial");
    fireEvent.click(screen.getByRole("button", { name: messages.admin.adjustment.submit }));

    await waitFor(() => expect(onAdjusted).toHaveBeenCalledTimes(1));
    expect(adminService.adjustCredit).toHaveBeenCalledWith(
      "pro-1",
      300,
      "Regularización parcial",
      "es",
    );
    expect(screen.getByText(/2,00/)).toBeTruthy();
  });

  it("does not call the API with an invalid amount", async () => {
    vi.mocked(adminService.adjustCredit).mockClear();
    renderWithIntl(<CreditAdjustmentForm professionalId="pro-1" onAdjusted={vi.fn()} />);

    fill("0", "Motivo válido");
    fireEvent.click(screen.getByRole("button", { name: messages.admin.adjustment.submit }));

    expect(await screen.findByText(messages.validation.adjustmentAmount)).toBeTruthy();
    expect(adminService.adjustCredit).not.toHaveBeenCalled();
  });
});
