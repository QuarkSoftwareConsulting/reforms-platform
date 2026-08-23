/**
 * Tests del formulario de publicacion.
 *
 * El que mas importa: sin marcar el consentimiento no se puede enviar. Es el
 * requisito legal del que depende poder ceder los datos del cliente.
 */

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Category } from "@/types/api";

const createLead = vi.fn();
const presignPhoto = vi.fn();

vi.mock("@/services/leads.service", () => ({
  leadsService: {
    create: (...args: unknown[]) => createLead(...args),
    presignPhoto: (...args: unknown[]) => presignPhoto(...args),
  },
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const { LeadWizard } = await import("@/components/features/LeadWizard");
const { renderWithIntl, messages } = await import("./render");

const CATEGORIES: Category[] = [
  {
    id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    slug: "carpinteria",
    name: "Carpinteria",
    lead_price: { amount_cents: 500, currency: "EUR", formatted: "5.00 €" },
  },
  {
    id: "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
    slug: "fontaneria",
    name: "Fontaneria",
    lead_price: { amount_cents: 700, currency: "EUR", formatted: "7.00 €" },
  },
];

const DESCRIPTION =
  "Se ha descolgado la puerta del armario alto de la cocina y necesito que la monten.";

async function fillUpToContactStep(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.click(screen.getByRole("radio", { name: /Carpinteria/i }));
  await user.click(screen.getByRole("button", { name: messages.common.next }));

  await user.type(screen.getByLabelText(/Resume el trabajo/i), "Reparar armario");
  await user.type(screen.getByLabelText(/Describe el trabajo/i), DESCRIPTION);
  await user.type(screen.getByLabelText(/Codigo postal/i), "28001");
  await user.click(screen.getByRole("button", { name: messages.common.next }));
}

describe("LeadWizard", () => {
  beforeEach(() => {
    createLead.mockReset();
    createLead.mockResolvedValue({
      id: "lead-1",
      status: "published",
      city: "Madrid",
      province: "Madrid",
      created_at: new Date().toISOString(),
    });
  });

  it("starts on the category step and lists the trades", () => {
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);

    expect(screen.getByText(new RegExp(messages.publish.steps.category))).toBeDefined();
    expect(screen.getByRole("radio", { name: /Carpinteria/i })).toBeDefined();
    expect(screen.getByRole("radio", { name: /Fontaneria/i })).toBeDefined();
  });

  it("does not advance without picking a trade", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);

    await user.click(screen.getByRole("button", { name: messages.common.next }));

    expect(await screen.findByText(messages.validation.categoryRequired)).toBeDefined();
    expect(screen.getByText(new RegExp(messages.publish.steps.category))).toBeDefined();
  });

  it("rejects a description that is too short for a professional to quote", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);

    await user.click(screen.getByRole("radio", { name: /Carpinteria/i }));
    await user.click(screen.getByRole("button", { name: messages.common.next }));
    await user.type(screen.getByLabelText(/Resume el trabajo/i), "Algo");
    await user.type(screen.getByLabelText(/Describe el trabajo/i), "corto");
    await user.type(screen.getByLabelText(/Codigo postal/i), "28001");
    await user.click(screen.getByRole("button", { name: messages.common.next }));

    expect(await screen.findByText(messages.validation.descriptionTooShort)).toBeDefined();
  });

  it("rejects a postal code from a province that does not exist", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);

    await user.click(screen.getByRole("radio", { name: /Carpinteria/i }));
    await user.click(screen.getByRole("button", { name: messages.common.next }));
    await user.type(screen.getByLabelText(/Resume el trabajo/i), "Reparar armario");
    await user.type(screen.getByLabelText(/Describe el trabajo/i), DESCRIPTION);
    await user.type(screen.getByLabelText(/Codigo postal/i), "99001");
    await user.click(screen.getByRole("button", { name: messages.common.next }));

    expect(await screen.findByText(messages.validation.postalCodeUnknown)).toBeDefined();
  });

  it("blocks submission until the privacy consent is accepted", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);
    await fillUpToContactStep(user);

    await user.type(screen.getByLabelText(/Tu nombre/i), "Ana Lopez");
    await user.type(screen.getByLabelText(/Telefono/i), "611223344");
    await user.click(screen.getByRole("button", { name: messages.publish.submit }));

    expect(await screen.findByText(messages.validation.consentRequired)).toBeDefined();
    expect(createLead).not.toHaveBeenCalled();
  });

  it("publishes once the consent is accepted", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);
    await fillUpToContactStep(user);

    await user.type(screen.getByLabelText(/Tu nombre/i), "Ana Lopez");
    await user.type(screen.getByLabelText(/Telefono/i), "611223344");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: messages.publish.submit }));

    await waitFor(() => expect(createLead).toHaveBeenCalledTimes(1));

    const payload = createLead.mock.calls[0]?.[0];
    expect(payload).toMatchObject({
      category_id: CATEGORIES[0]!.id,
      postal_code: "28001",
      client_name: "Ana Lopez",
      consent: { accepted: true },
    });
    expect(await screen.findByText(messages.publish.successTitle)).toBeDefined();
  });

  it("sends no email field when the client leaves it empty", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);
    await fillUpToContactStep(user);

    await user.type(screen.getByLabelText(/Tu nombre/i), "Ana Lopez");
    await user.type(screen.getByLabelText(/Telefono/i), "611223344");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: messages.publish.submit }));

    await waitFor(() => expect(createLead).toHaveBeenCalled());
    expect(createLead.mock.calls[0]?.[0]).toMatchObject({ client_email: null });
  });

  it("shows a translated message when the API rejects the request", async () => {
    const { ApiError } = await import("@/services/api");
    createLead.mockRejectedValue(
      new ApiError(422, { code: "UNKNOWN_POSTAL_CODE", message: "nope" }),
    );

    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);
    await fillUpToContactStep(user);

    await user.type(screen.getByLabelText(/Tu nombre/i), "Ana Lopez");
    await user.type(screen.getByLabelText(/Telefono/i), "611223344");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: messages.publish.submit }));

    expect(
      await screen.findByText(messages.errors.UNKNOWN_POSTAL_CODE),
    ).toBeDefined();
  });

  it("lets the user go back and keeps what they typed", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);
    await fillUpToContactStep(user);

    await user.click(screen.getByRole("button", { name: messages.common.back }));

    expect(screen.getByLabelText(/Resume el trabajo/i)).toHaveProperty(
      "value",
      "Reparar armario",
    );
  });
});
