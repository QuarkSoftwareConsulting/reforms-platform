/**
 * El usuario tiene que saber QUE corregir: cada codigo con su texto y, en los errores de
 * campo del esquema, el campo y la regla. El `message` del backend no se muestra nunca.
 */

import { renderHook } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import messages from "../messages/es.json";

const { useApiError } = await import("@/hooks/useApiError");
const { ApiError } = await import("@/services/api");

function wrapper({ children }: { children: ReactNode }) {
  return (
    <NextIntlClientProvider locale="es" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

function translate(error: unknown): string {
  const { result } = renderHook(() => useApiError(), { wrapper });
  return result.current(error);
}

function schemaError(errors: unknown[]): InstanceType<typeof ApiError> {
  return new ApiError(422, {
    code: "VALIDATION_ERROR",
    message: "Los datos enviados no son validos",
    details: { errors },
  });
}

describe("useApiError", () => {
  it("shows the specific text of a domain code, not the generic validation one", () => {
    const error = new ApiError(422, {
      code: "CONSENT_DATE_IN_FUTURE",
      message: "La fecha del consentimiento no puede estar en el futuro",
      details: null,
    });

    expect(translate(error)).toBe(messages.errors.CONSENT_DATE_IN_FUTURE);
    expect(translate(error)).not.toBe(messages.errors.VALIDATION_ERROR);
  });

  it("puts the limits sent in `details` into the message", () => {
    const error = new ApiError(422, {
      code: "DESCRIPTION_LENGTH_INVALID",
      message: "x",
      details: { min: 20, max: 4000 },
    });

    expect(translate(error)).toContain("20");
    expect(translate(error)).toContain("4000");
    expect(translate(error)).not.toContain("{");
  });

  it("names the field and the rule of each schema error", () => {
    const text = translate(
      schemaError([
        { field: "description", type: "string_too_short", message: "x", limits: { min_length: 20 } },
        { field: "client_phone", type: "missing", message: "x", limits: {} },
      ]),
    );

    expect(text).toContain(messages.errors.fields.description);
    expect(text).toContain("20");
    expect(text).toContain(messages.errors.fields.client_phone);
    expect(text).not.toBe(messages.errors.VALIDATION_ERROR);
  });

  it("maps nested fields and list items to their label", () => {
    const text = translate(
      schemaError([
        { field: "consent.accepted_at", type: "datetime_parsing", message: "x", limits: {} },
        { field: "photo_keys.2", type: "value_error", message: "x", limits: {} },
      ]),
    );

    expect(text).toContain(messages.errors.fields.consent_accepted_at);
    expect(text).toContain(messages.errors.fields.photo_keys);
  });

  it("keeps the generic validation text when no field is recognised", () => {
    const text = translate(
      schemaError([{ field: "campo_desconocido", type: "missing", message: "x", limits: {} }]),
    );

    expect(text).toBe(messages.errors.VALIDATION_ERROR);
  });

  it("never leaks the backend message for an unknown code", () => {
    const error = new ApiError(400, {
      code: "ALGO_NUEVO",
      message: "detalle tecnico interno",
      details: null,
    });

    expect(translate(error)).toBe(messages.errors.generic);
  });

  it("translates every code the lead forms can raise", () => {
    const codes = [
      "INVALID_PHONE",
      "INVALID_EMAIL",
      "INVALID_POSTAL_CODE",
      "CLIENT_NAME_REQUIRED",
      "CONSENT_DATE_IN_FUTURE",
      "TITLE_LENGTH_INVALID",
      "DESCRIPTION_LENGTH_INVALID",
      "PURCHASE_NOT_FOUND",
      "PURCHASE_NOT_PAYABLE",
    ];
    for (const code of codes) {
      const error = new ApiError(422, { code, message: "x", details: { min: 1, max: 2 } });
      expect(translate(error), code).not.toBe(messages.errors.generic);
    }
  });
});
