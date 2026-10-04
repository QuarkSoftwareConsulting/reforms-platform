/**
 * Tests del formulario de publicacion.
 *
 * El que mas importa: sin marcar el consentimiento no se puede enviar. Es el
 * requisito legal del que depende poder ceder los datos del cliente.
 */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CatalogCategory } from "@/types/api";

const createLead = vi.fn();
const presignPhoto = vi.fn();
const startPhoneVerification = vi.fn();

vi.mock("@/services/leads.service", () => ({
  leadsService: {
    create: (...args: unknown[]) => createLead(...args),
    presignPhoto: (...args: unknown[]) => presignPhoto(...args),
    startPhoneVerification: (...args: unknown[]) => startPhoneVerification(...args),
  },
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const { LeadWizard } = await import("@/components/features/LeadWizard");
const { renderWithIntl, messages } = await import("./render");

/** La etiqueta del campo lleva el asterisco de obligatorio pegado detras. */
const label = (text: string): RegExp => new RegExp(text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i");

const WARDROBES = "6f1c2a8e-3d5b-4c7a-9e2f-1a2b3c4d5e6f";
const DOORS = "7a2d3b9f-4e6c-4d8b-8f3a-2b3c4d5e6f70";

const CATEGORIES: CatalogCategory[] = [
  {
    id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    slug: "carpinteria",
    name: "Carpinteria",
    suggested_lead_price: { amount_cents: 500, currency: "EUR", formatted: "5.00 €" },
    services: [
      { id: WARDROBES, slug: "armarios", name: "Armarios a medida" },
      { id: DOORS, slug: "puertas", name: "Puertas" },
    ],
  },
  {
    id: "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
    slug: "fontaneria",
    name: "Fontaneria",
    suggested_lead_price: { amount_cents: 700, currency: "EUR", formatted: "7.00 €" },
    services: [],
  },
];

const DESCRIPTION =
  "Se ha descolgado la puerta del armario alto de la cocina y necesito que la monten.";

async function fillUpToContactStep(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.click(screen.getByRole("radio", { name: /Carpinteria/i }));
  await user.click(screen.getByRole("button", { name: messages.common.next }));

  await user.type(screen.getByLabelText(label(messages.publish.titleLabel)), "Reparar armario");
  await user.type(screen.getByLabelText(label(messages.publish.descriptionLabel)), DESCRIPTION);
  await pickProjectData(user);
  await user.type(screen.getByLabelText(label(messages.publish.postalCodeLabel)), "28001");
  await user.click(screen.getByRole("button", { name: messages.common.next }));
}

async function pickProjectData(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.click(screen.getByRole("radio", { name: messages.project.propertyTypes.flat }));
  await user.click(
    screen.getByRole("radio", { name: messages.project.schedules.within_weeks }),
  );
}

describe("LeadWizard", () => {
  beforeEach(() => {
    // Por defecto, como hoy en produccion: el entorno no verifica por SMS.
    startPhoneVerification.mockReset();
    startPhoneVerification.mockResolvedValue({ required: false });
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
    await user.type(screen.getByLabelText(label(messages.publish.titleLabel)), "Algo");
    await user.type(screen.getByLabelText(label(messages.publish.descriptionLabel)), "corto");
    await user.type(screen.getByLabelText(label(messages.publish.postalCodeLabel)), "28001");
    await user.click(screen.getByRole("button", { name: messages.common.next }));

    expect(await screen.findByText(messages.validation.descriptionTooShort)).toBeDefined();
  });

  it("rejects a postal code from a province that does not exist", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);

    await user.click(screen.getByRole("radio", { name: /Carpinteria/i }));
    await user.click(screen.getByRole("button", { name: messages.common.next }));
    await user.type(screen.getByLabelText(label(messages.publish.titleLabel)), "Reparar armario");
    await user.type(screen.getByLabelText(label(messages.publish.descriptionLabel)), DESCRIPTION);
    await pickProjectData(user);
    await user.type(screen.getByLabelText(label(messages.publish.postalCodeLabel)), "99001");
    await user.click(screen.getByRole("button", { name: messages.common.next }));

    expect(await screen.findByText(messages.validation.postalCodeUnknown)).toBeDefined();
  });

  it("only accepts postal codes from the Community of Madrid", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);

    await user.click(screen.getByRole("radio", { name: /Carpinteria/i }));
    await user.click(screen.getByRole("button", { name: messages.common.next }));
    await user.type(screen.getByLabelText(label(messages.publish.titleLabel)), "Reparar armario");
    await user.type(screen.getByLabelText(label(messages.publish.descriptionLabel)), DESCRIPTION);
    await pickProjectData(user);
    await user.type(screen.getByLabelText(label(messages.publish.postalCodeLabel)), "08001");
    await user.click(screen.getByRole("button", { name: messages.common.next }));

    expect(await screen.findByText(messages.validation.postalCodeNotCovered)).toBeDefined();
  });

  it("requires the property type and the project timing", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);

    await user.click(screen.getByRole("radio", { name: /Carpinteria/i }));
    await user.click(screen.getByRole("button", { name: messages.common.next }));
    await user.type(screen.getByLabelText(label(messages.publish.titleLabel)), "Reparar armario");
    await user.type(screen.getByLabelText(label(messages.publish.descriptionLabel)), DESCRIPTION);
    await user.type(screen.getByLabelText(label(messages.publish.postalCodeLabel)), "28001");
    await user.click(screen.getByRole("button", { name: messages.common.next }));

    expect(await screen.findByText(messages.validation.propertyTypeRequired)).toBeDefined();
    expect(screen.getByText(messages.validation.scheduleRequired)).toBeDefined();
    // La pregunta es la que pidio el cliente, no la del mockup.
    expect(screen.getByText(label(messages.publish.scheduleLabel))).toBeDefined();
  });

  it("shows the services of the chosen category and clears them on switching", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);

    expect(screen.queryByRole("checkbox", { name: "Puertas" })).toBeNull();
    await user.click(screen.getByRole("radio", { name: /Carpinteria/i }));
    await user.click(screen.getByRole("checkbox", { name: "Puertas" }));
    expect(screen.getByRole("checkbox", { name: "Puertas" })).toHaveProperty("checked", true);

    // Fontaneria no tiene servicios: el panel desaparece y la seleccion se pierde.
    await user.click(screen.getByRole("radio", { name: /Fontaneria/i }));
    expect(screen.queryByRole("checkbox", { name: "Puertas" })).toBeNull();
    await user.click(screen.getByRole("radio", { name: /Carpinteria/i }));
    expect(screen.getByRole("checkbox", { name: "Puertas" })).toHaveProperty("checked", false);
  });

  it("blocks submission until the privacy consent is accepted", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);
    await fillUpToContactStep(user);

    await user.type(screen.getByLabelText(label(messages.publish.nameLabel)), "Ana Lopez");
    await user.type(screen.getByLabelText(label(messages.publish.phoneLabel)), "611223344");
    await user.click(screen.getByRole("button", { name: messages.publish.submit }));

    expect(await screen.findByText(messages.validation.consentRequired)).toBeDefined();
    expect(createLead).not.toHaveBeenCalled();
  });

  it("publishes once the consent is accepted", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);
    await user.click(screen.getByRole("radio", { name: /Carpinteria/i }));
    await user.click(screen.getByRole("checkbox", { name: "Puertas" }));
    await user.click(screen.getByRole("checkbox", { name: "Armarios a medida" }));
    await fillUpToContactStep(user);

    await user.type(screen.getByLabelText(label(messages.publish.nameLabel)), "Ana Lopez");
    await user.type(screen.getByLabelText(label(messages.publish.phoneLabel)), "611223344");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: messages.publish.submit }));

    await waitFor(() => expect(createLead).toHaveBeenCalledTimes(1));

    const payload = createLead.mock.calls[0]?.[0];
    expect(payload).toMatchObject({
      category_id: CATEGORIES[0]!.id,
      postal_code: "28001",
      client_name: "Ana Lopez",
      // En el orden en que el cliente los marco.
      service_ids: [DOORS, WARDROBES],
      property_type: "flat",
      schedule: "within_weeks",
      consent: { accepted: true },
    });
    expect(await screen.findByText(messages.publish.successTitle)).toBeDefined();
  });

  it("sends no email field when the client leaves it empty", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);
    await fillUpToContactStep(user);

    await user.type(screen.getByLabelText(label(messages.publish.nameLabel)), "Ana Lopez");
    await user.type(screen.getByLabelText(label(messages.publish.phoneLabel)), "611223344");
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

    await user.type(screen.getByLabelText(label(messages.publish.nameLabel)), "Ana Lopez");
    await user.type(screen.getByLabelText(label(messages.publish.phoneLabel)), "611223344");
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

    expect(screen.getByLabelText(label(messages.publish.titleLabel))).toHaveProperty(
      "value",
      "Reparar armario",
    );
  });

  describe("SMS verification", () => {
    async function submitContact(user: ReturnType<typeof userEvent.setup>, phone: string) {
      const phoneField = screen.getByLabelText(label(messages.publish.phoneLabel));
      await user.clear(phoneField);
      await user.type(phoneField, phone);
      await user.click(screen.getByRole("button", { name: messages.publish.submit }));
    }

    beforeEach(() => startPhoneVerification.mockResolvedValue({ required: true }));

    it("asks for the SMS code before publishing", async () => {
      const user = userEvent.setup();
      renderWithIntl(<LeadWizard categories={CATEGORIES} />);
      await fillUpToContactStep(user);
      await user.type(screen.getByLabelText(label(messages.publish.nameLabel)), "Ana Lopez");
      await user.click(screen.getByRole("checkbox"));

      await submitContact(user, "611223344");

      expect(startPhoneVerification).toHaveBeenCalledWith("611223344");
      expect(await screen.findByLabelText(label(messages.publish.phoneCodeLabel))).toBeDefined();
      expect(createLead).not.toHaveBeenCalled();

      await user.type(screen.getByLabelText(label(messages.publish.phoneCodeLabel)), "246810");
      await user.click(screen.getByRole("button", { name: messages.publish.submit }));

      await waitFor(() => expect(createLead).toHaveBeenCalledTimes(1));
      expect(createLead.mock.calls[0]?.[0]).toMatchObject({ phone_verification_code: "246810" });
      expect(startPhoneVerification).toHaveBeenCalledTimes(1);
    });

    it("rejects a code that is not six digits without calling the API", async () => {
      const user = userEvent.setup();
      renderWithIntl(<LeadWizard categories={CATEGORIES} />);
      await fillUpToContactStep(user);
      await user.type(screen.getByLabelText(label(messages.publish.nameLabel)), "Ana Lopez");
      await user.click(screen.getByRole("checkbox"));
      await submitContact(user, "611223344");

      await user.type(await screen.findByLabelText(label(messages.publish.phoneCodeLabel)), "12");
      await user.click(screen.getByRole("button", { name: messages.publish.submit }));

      expect(await screen.findByText(messages.validation.phoneCodeFormat)).toBeDefined();
      expect(createLead).not.toHaveBeenCalled();
    });

    it("sends a new code when the phone changes after the first SMS", async () => {
      const user = userEvent.setup();
      renderWithIntl(<LeadWizard categories={CATEGORIES} />);
      await fillUpToContactStep(user);
      await user.type(screen.getByLabelText(label(messages.publish.nameLabel)), "Ana Lopez");
      await user.click(screen.getByRole("checkbox"));
      await submitContact(user, "611223344");
      await screen.findByLabelText(label(messages.publish.phoneCodeLabel));

      await submitContact(user, "622334455");

      await waitFor(() => expect(startPhoneVerification).toHaveBeenLastCalledWith("622334455"));
      expect(createLead).not.toHaveBeenCalled();
    });
  });
});

/**
 * Errores lejos del boton. El formulario es por pasos y el boton esta abajo: un error
 * fuera de pantalla, o de un paso anterior que rechazo el servidor, hacia que pulsar
 * "Publicar" pareciera no hacer nada.
 */
describe("LeadWizard: errores de formulario", () => {
  const SUMMARY = /^Revisa \d+ campos? para continuar$/;

  /** El contenedor del resumen: es lo que toma el foco tras un intento fallido. */
  function summary(): HTMLElement {
    return screen.getByText(SUMMARY).closest("[tabindex]") as HTMLElement;
  }

  async function submitContact(user: ReturnType<typeof userEvent.setup>): Promise<void> {
    await fillUpToContactStep(user);
    await user.type(screen.getByLabelText(label(messages.publish.nameLabel)), "Ana Lopez");
    await user.type(screen.getByLabelText(label(messages.publish.phoneLabel)), "611223344");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: messages.publish.submit }));
  }

  beforeEach(() => {
    startPhoneVerification.mockReset();
    startPhoneVerification.mockResolvedValue({ required: false });
    createLead.mockReset();
  });

  it("lists the step's errors next to the button and moves focus there", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);
    await user.click(screen.getByRole("radio", { name: /Carpinteria/i }));
    await user.click(screen.getByRole("button", { name: messages.common.next }));

    await user.click(screen.getByRole("button", { name: messages.common.next }));

    const box = summary();
    expect(document.activeElement).toBe(box);
    expect(within(box).getByRole("button", { name: messages.errors.fields.title })).toBeTruthy();
    expect(
      within(box).getByRole("button", { name: messages.errors.fields.schedule }),
    ).toBeTruthy();
  });

  it("takes the user back to the step of a field the server rejected", async () => {
    const { ApiError } = await import("@/services/api");
    createLead.mockRejectedValue(
      new ApiError(422, { code: "POSTAL_CODE_NOT_COVERED", message: "x", details: null }),
    );
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);

    await submitContact(user);

    const postalCode = await screen.findByLabelText(label(messages.publish.postalCodeLabel));
    expect(postalCode.getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByText(new RegExp(messages.publish.steps.details))).toBeDefined();
    expect(document.activeElement).toBe(summary());
    // Esta en su campo: no se repite como aviso general.
    expect(screen.getAllByText(messages.errors.POSTAL_CODE_NOT_COVERED)).toHaveLength(1);
  });

  it("keeps a rejected field of a later step and leads to it from the summary", async () => {
    const { ApiError } = await import("@/services/api");
    createLead.mockRejectedValue(
      new ApiError(422, {
        code: "VALIDATION_ERROR",
        message: "x",
        details: {
          errors: [
            { field: "title", type: "string_too_long", limits: { max_length: 140 } },
            { field: "client_phone", type: "string_too_short", limits: { min_length: 6 } },
          ],
        },
      }),
    );
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);
    await submitContact(user);

    // Vuelve al primer paso con error; el del telefono sigue en el resumen.
    const box = await waitFor(summary);
    expect(screen.getByText(new RegExp(messages.publish.steps.details))).toBeDefined();
    await user.click(within(box).getByRole("button", { name: messages.publish.phoneLabel }));

    const phone = await screen.findByLabelText(label(messages.publish.phoneLabel));
    await waitFor(() => expect(document.activeElement).toBe(phone));
    expect(phone.getAttribute("aria-invalid")).toBe("true");
  });

  it("keeps errors without a field as a general alert", async () => {
    const { ApiError } = await import("@/services/api");
    createLead.mockRejectedValue(
      new ApiError(429, { code: "TOO_MANY_VERIFICATION_ATTEMPTS", message: "x", details: null }),
    );
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);

    await submitContact(user);

    expect(await screen.findByText(messages.errors.TOO_MANY_VERIFICATION_ATTEMPTS)).toBeDefined();
    expect(screen.queryByText(SUMMARY)).toBeNull();
  });

  it("links a group's error to the group so the screen reader reads it", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);
    await user.click(screen.getByRole("radio", { name: /Carpinteria/i }));
    await user.click(screen.getByRole("button", { name: messages.common.next }));

    await user.click(screen.getByRole("button", { name: messages.common.next }));

    const schedule = document.querySelector('[data-field="schedule"]');
    const description = document.getElementById(
      schedule?.getAttribute("aria-describedby") ?? "",
    );
    expect(description?.textContent).toBe(messages.validation.scheduleRequired);
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });

  it("flags a filled field when the user leaves it, without waiting for Next", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);
    await user.click(screen.getByRole("radio", { name: /Carpinteria/i }));
    await user.click(screen.getByRole("button", { name: messages.common.next }));

    await user.type(screen.getByLabelText(label(messages.publish.postalCodeLabel)), "08001");
    await user.tab();

    expect(screen.getByText(messages.validation.postalCodeNotCovered)).toBeDefined();
    // El resumen es para los intentos de envio: aqui el error ya se ve en su campo.
    expect(screen.queryByText(/para continuar$/)).toBeNull();
  });

  it("does not flag an empty field the user only tabbed through", async () => {
    const user = userEvent.setup();
    renderWithIntl(<LeadWizard categories={CATEGORIES} />);
    await user.click(screen.getByRole("radio", { name: /Carpinteria/i }));
    await user.click(screen.getByRole("button", { name: messages.common.next }));

    await user.click(screen.getByLabelText(label(messages.publish.titleLabel)));
    await user.tab();

    expect(screen.queryByText(messages.validation.titleTooShort)).toBeNull();
  });
});
