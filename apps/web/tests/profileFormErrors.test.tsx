/**
 * Errores del formulario de perfil profesional.
 *
 * El fallo que cubren: el formulario es largo, el boton esta abajo y el error arriba.
 * Sin resumen junto al boton, pulsar "Crear perfil" con un error parecia no hacer
 * nada. Y un error del backend con campo (NIF, CP) salia como aviso suelto sin marcar
 * el campo que habia que corregir.
 */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/services/api";
import type { CatalogCategory } from "@/types/api";

const upsertProfile = vi.fn();
const refreshMe = vi.fn();

vi.mock("@/services/professional.service", () => ({
  professionalService: {
    upsertProfile: (...args: unknown[]) => upsertProfile(...args),
    submitForReview: vi.fn(),
  },
}));
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ me: { professional: null }, refreshMe }),
}));
vi.mock("@/hooks/useProfessionalFiles", () => ({
  useProfessionalFiles: () => ({
    uploading: false,
    error: null,
    rejected: null,
    uploadMedia: vi.fn(),
    uploadDocument: vi.fn(),
    removeDocument: vi.fn(),
  }),
}));

const { ProfileForm } = await import("@/components/features/ProfileForm");
const { renderWithIntl, messages } = await import("./render");

const t = messages.profile;

const CARPENTRY = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
const WARDROBES = "6f1c2a8e-3d5b-4c7a-9e2f-1a2b3c4d5e6f";

const CATEGORIES: CatalogCategory[] = [
  {
    id: CARPENTRY,
    slug: "carpinteria",
    name: "Carpinteria",
    suggested_lead_price: { amount_cents: 500, currency: "EUR", formatted: "5.00 €" },
    services: [{ id: WARDROBES, slug: "armarios", name: "Armarios a medida" }],
  },
];

/** La etiqueta lleva el asterisco de obligatorio pegado detras. */
const field = (label: string): HTMLElement =>
  screen.getByLabelText(new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`));

function summary(): HTMLElement {
  return screen
    .getByText(/^Revisa \d+ campos? para continuar$/)
    .closest("[tabindex]") as HTMLElement;
}

async function fillValidProfile(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.type(field(t.businessNameLabel), "Reformas Lopez");
  await user.type(field(t.phoneLabel), "612345678");
  await user.type(field(t.postalCodeLabel), "28001");
  await user.click(screen.getByRole("checkbox", { name: /Carpinteria/ }));
}

function render() {
  return renderWithIntl(<ProfileForm categories={CATEGORIES} />);
}

describe("ProfileForm: errores al guardar", () => {
  beforeEach(() => {
    upsertProfile.mockReset();
    refreshMe.mockReset();
  });

  it("lists what to fix next to the button and moves focus there", async () => {
    const user = userEvent.setup();
    render();

    await user.click(screen.getByRole("button", { name: t.create }));

    const box = summary();
    expect(document.activeElement).toBe(box);
    expect(within(box).getByRole("button", { name: t.businessNameLabel })).toBeTruthy();
    expect(within(box).getByRole("button", { name: t.categoriesLabel })).toBeTruthy();
    expect(upsertProfile).not.toHaveBeenCalled();
  });

  it("takes the user to the field from the summary", async () => {
    const user = userEvent.setup();
    render();
    await user.click(screen.getByRole("button", { name: t.create }));

    await user.click(within(summary()).getByRole("button", { name: t.phoneLabel }));

    expect(document.activeElement).toBe(field(t.phoneLabel));
  });

  it("drops a field from the summary once it is corrected", async () => {
    const user = userEvent.setup();
    render();
    await user.click(screen.getByRole("button", { name: t.create }));

    await user.type(field(t.businessNameLabel), "Reformas Lopez");

    expect(within(summary()).queryByRole("button", { name: t.businessNameLabel })).toBeNull();
  });

  it("marks the tax id field when the backend rejects it", async () => {
    upsertProfile.mockRejectedValue(
      new ApiError(422, { code: "INVALID_TAX_ID", message: "NIF no valido", details: null }),
    );
    const user = userEvent.setup();
    render();
    await fillValidProfile(user);

    await user.click(screen.getByRole("button", { name: t.create }));

    await waitFor(() => expect(field(t.taxIdLabel).getAttribute("aria-invalid")).toBe("true"));
    const box = summary();
    expect(document.activeElement).toBe(box);
    expect(within(box).getByText(new RegExp(messages.errors.INVALID_TAX_ID))).toBeTruthy();
    // Atribuido a su campo, no se repite como aviso general.
    expect(screen.getAllByText(messages.errors.INVALID_TAX_ID)).toHaveLength(1);
  });

  it("puts a schema error from the backend on its field with the limit", async () => {
    upsertProfile.mockRejectedValue(
      new ApiError(422, {
        code: "VALIDATION_ERROR",
        message: "Los datos enviados no son validos",
        details: {
          errors: [{ field: "business_name", type: "string_too_short", limits: { min_length: 2 } }],
        },
      }),
    );
    const user = userEvent.setup();
    render();
    await fillValidProfile(user);

    await user.click(screen.getByRole("button", { name: t.create }));

    await waitFor(() =>
      expect(field(t.businessNameLabel).getAttribute("aria-invalid")).toBe("true"),
    );
    expect(screen.queryByText(messages.errors.VALIDATION_ERROR)).toBeNull();
  });

  it("shows the services error, which had nowhere to appear before", async () => {
    upsertProfile.mockRejectedValue(
      new ApiError(422, { code: "INVALID_SERVICE", message: "x", details: null }),
    );
    const user = userEvent.setup();
    render();
    await fillValidProfile(user);
    await user.click(screen.getByRole("checkbox", { name: "Armarios a medida" }));

    await user.click(screen.getByRole("button", { name: t.create }));

    const box = await waitFor(summary);
    await user.click(within(box).getByRole("button", { name: t.servicesShortLabel }));
    const group = document.querySelector<HTMLElement>('[data-field="serviceIds"]');
    expect(document.activeElement).toBe(group);
    expect(within(group!).getByText(messages.errors.INVALID_SERVICE)).toBeTruthy();
  });

  it("keeps errors without a field as a general alert", async () => {
    upsertProfile.mockRejectedValue(
      new ApiError(409, { code: "VERIFICATION_LOCKED", message: "x", details: null }),
    );
    const user = userEvent.setup();
    render();
    await fillValidProfile(user);

    await user.click(screen.getByRole("button", { name: t.create }));

    expect(await screen.findByText(messages.errors.VERIFICATION_LOCKED)).toBeTruthy();
    expect(screen.queryByText(/para continuar$/)).toBeNull();
  });
});
