import { describe, expect, it } from "vitest";

import { formatCents, formatMoney, toUnits } from "@/helpers/currency";
import { formatRelative, minutesUntil } from "@/helpers/date";
import { formatDistance } from "@/helpers/distance";
import { taxIdKind } from "@/helpers/taxId";
import {
  MAX_PHOTO_BYTES,
  leadFormSchema,
  phoneNumber,
  professionalProfileSchema,
  spanishPostalCode,
  validatePhotos,
} from "@/helpers/validators";

const FIVE_EUR = { amount_cents: 500, currency: "EUR", formatted: "5.00 €" };

describe("currency", () => {
  it("converts cents to units", () => {
    expect(toUnits(500, "EUR")).toBe(5);
    expect(toUnits(500, "JPY")).toBe(500);
  });

  it("places the euro symbol per locale convention", () => {
    // El separador de Intl es un espacio no separable, no un espacio normal.
    expect(formatMoney(FIVE_EUR, "es").replace(/ /g, " ")).toBe("5,00 €");
    expect(formatMoney(FIVE_EUR, "en")).toBe("€5.00");
  });

  it("drops the cents of a round amount only when asked", () => {
    expect(formatMoney(FIVE_EUR, "es", { trimZeroCents: true }).replace(/\u00a0/g, " ")).toBe("5 €");
    expect(formatMoney(FIVE_EUR, "en", { trimZeroCents: true })).toBe("€5");
    // Un importe con centimos los conserva: recortarlos lo redondearia.
    expect(
      formatMoney({ amount_cents: 1250, currency: "EUR", formatted: "" }, "en", {
        trimZeroCents: true,
      }),
    ).toBe("€12.50");
  });

  it("renders unknown but well-formed currency codes as-is", () => {
    // Intl acepta cualquier codigo de tres letras: no hace falta fallback aqui.
    expect(formatMoney({ amount_cents: 500, currency: "XYZ", formatted: "" })).toContain("XYZ");
  });

  it("falls back to the backend string when the code is malformed", () => {
    // Un codigo que no son tres letras hace que Intl lance RangeError.
    expect(formatMoney({ amount_cents: 500, currency: "EU", formatted: "5.00 EU" })).toBe(
      "5.00 EU",
    );
  });

  it("formats raw cents", () => {
    expect(formatCents(1200, "EUR", "en")).toBe("€12.00");
  });
});

describe("dates", () => {
  const now = new Date("2026-03-01T12:00:00Z").getTime();

  it("renders relative times in the requested language", () => {
    expect(formatRelative("2026-03-01T09:00:00Z", "es", now)).toContain("hace 3 horas");
    expect(formatRelative("2026-03-01T09:00:00Z", "en", now)).toContain("3 hours ago");
  });

  it("uses minutes for very recent leads", () => {
    expect(formatRelative("2026-03-01T11:45:00Z", "es", now)).toContain("minutos");
  });

  it("returns empty string for invalid dates", () => {
    expect(formatRelative("no-es-una-fecha")).toBe("");
  });

  it("counts minutes left on a reservation", () => {
    expect(minutesUntil("2026-03-01T12:30:00Z", now)).toBe(30);
    expect(minutesUntil("2026-03-01T11:00:00Z", now)).toBe(0);
    expect(minutesUntil(null, now)).toBe(0);
  });
});

describe("distance", () => {
  it("avoids fake precision below one kilometre", () => {
    expect(formatDistance(0.4, "es")).toBe("menos de 1 km");
    expect(formatDistance(0.4, "en")).toBe("less than 1 km");
  });

  it("keeps one decimal under ten km and rounds above", () => {
    expect(formatDistance(3.47, "en")).toBe("3.5 km");
    expect(formatDistance(28.6, "en")).toBe("29 km");
  });

  it("returns empty string when distance is unknown", () => {
    expect(formatDistance(null)).toBe("");
  });
});

describe("postal code validation", () => {
  it("accepts valid Spanish codes", () => {
    expect(spanishPostalCode.parse(" 28001 ")).toBe("28001");
    expect(spanishPostalCode.parse("08001")).toBe("08001");
  });

  it("rejects codes with a province out of range", () => {
    expect(spanishPostalCode.safeParse("99001").success).toBe(false);
    expect(spanishPostalCode.safeParse("00123").success).toBe(false);
  });

  it("rejects wrong lengths and non-digits", () => {
    expect(spanishPostalCode.safeParse("2800").success).toBe(false);
    expect(spanishPostalCode.safeParse("2800A").success).toBe(false);
  });
});

describe("phone validation", () => {
  it("strips separators and accepts the +34 prefix", () => {
    expect(phoneNumber.parse("+34 611-22 33 44")).toBe("+34611223344");
    expect(phoneNumber.parse("611 223 344")).toBe("611223344");
  });

  it("rejects numbers that are not Spanish mobiles or landlines", () => {
    expect(phoneNumber.safeParse("123456789").success).toBe(false);
    expect(phoneNumber.safeParse("61122334").success).toBe(false);
  });
});

describe("lead form schema", () => {
  const valid = {
    categoryId: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    serviceIds: [],
    propertyType: "flat",
    schedule: "asap",
    title: "Reparar armario",
    description: "Se ha descolgado la puerta del armario alto de la cocina y hay que montarla.",
    postalCode: "28001",
    clientName: "Ana Lopez",
    clientPhone: "+34611223344",
    clientEmail: "ana@example.com",
    consentAccepted: true as const,
  };

  it("accepts a complete form", () => {
    expect(leadFormSchema.safeParse(valid).success).toBe(true);
  });

  it("blocks submission without consent", () => {
    const result = leadFormSchema.safeParse({ ...valid, consentAccepted: false });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("consentRequired");
    }
  });

  it("requires a description long enough to be useful to a professional", () => {
    const result = leadFormSchema.safeParse({ ...valid, description: "arreglar" });
    expect(result.success).toBe(false);
  });

  it("only accepts postal codes from the Community of Madrid", () => {
    const result = leadFormSchema.safeParse({ ...valid, postalCode: "08001" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("postalCodeNotCovered");
    }
    expect(leadFormSchema.safeParse({ ...valid, postalCode: "28500" }).success).toBe(true);
  });

  it("rejects a property type the API does not know", () => {
    const result = leadFormSchema.safeParse({ ...valid, propertyType: "castillo" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("propertyTypeRequired");
    }
  });

  it("treats an empty email as absent rather than invalid", () => {
    const result = leadFormSchema.safeParse({ ...valid, clientEmail: "" });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.clientEmail).toBeNull();
    }
  });
});

describe("professional profile schema", () => {
  const valid = {
    businessName: "Carpinteria Lopez",
    phone: "+34600111222",
    postalCode: "28001",
    serviceRadiusKm: 25,
    categoryIds: ["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    serviceIds: [],
    professionalType: "self_employed" as const,
    legalName: "Ana Lopez Garcia",
    taxId: "12.345.678-z",
    address: "Calle Mayor 1",
    workPhotoKeys: [],
  };

  it("accepts a complete profile and normalises the tax id", () => {
    const result = professionalProfileSchema.safeParse(valid);
    expect(result.success).toBe(true);
    if (result.success) expect(result.data.taxId).toBe("12345678Z");
  });

  it("leaves the registration details optional until submitting", () => {
    const result = professionalProfileSchema.safeParse({
      ...valid,
      professionalType: null,
      legalName: "",
      taxId: "",
      address: "",
    });
    expect(result.success).toBe(true);
    if (result.success) expect(result.data.taxId).toBeNull();
  });

  it("needs a Spanish mobile and a base in Madrid", () => {
    const landline = professionalProfileSchema.safeParse({ ...valid, phone: "912345678" });
    expect(landline.success).toBe(false);
    if (!landline.success) expect(landline.error.issues[0]?.message).toBe("mobileFormat");
    const barcelona = professionalProfileSchema.safeParse({ ...valid, postalCode: "08001" });
    expect(barcelona.success).toBe(false);
  });

  it("rejects a mistyped tax id and a company without CIF", () => {
    const typo = professionalProfileSchema.safeParse({ ...valid, taxId: "12345678A" });
    expect(typo.success).toBe(false);
    if (!typo.success) expect(typo.error.issues[0]?.message).toBe("taxIdInvalid");
    const company = professionalProfileSchema.safeParse({ ...valid, professionalType: "company" });
    expect(company.success).toBe(false);
    if (!company.success) expect(company.error.issues[0]?.message).toBe("companyNeedsCif");
  });

  it("requires at least one trade", () => {
    const result = professionalProfileSchema.safeParse({ ...valid, categoryIds: [] });
    expect(result.success).toBe(false);
  });

  it("caps the service radius", () => {
    expect(professionalProfileSchema.safeParse({ ...valid, serviceRadiusKm: 500 }).success).toBe(
      false,
    );
    expect(professionalProfileSchema.safeParse({ ...valid, serviceRadiusKm: 0 }).success).toBe(
      false,
    );
  });

  it("coerces the radius coming from a text input", () => {
    const result = professionalProfileSchema.safeParse({ ...valid, serviceRadiusKm: "40" });
    expect(result.success).toBe(true);
    if (result.success) expect(result.data.serviceRadiusKm).toBe(40);
  });
});

describe("photo validation", () => {
  const photo = (name: string, type: string, size: number): File => {
    const file = new File(["x"], name, { type });
    Object.defineProperty(file, "size", { value: size });
    return file;
  };

  it("accepts supported image types", () => {
    const { accepted, rejected } = validatePhotos([photo("a.jpg", "image/jpeg", 1000)]);
    expect(accepted).toHaveLength(1);
    expect(rejected).toHaveLength(0);
  });

  it("rejects non-images before uploading them", () => {
    const { accepted, rejected } = validatePhotos([
      photo("doc.pdf", "application/pdf", 1000),
    ]);
    expect(accepted).toHaveLength(0);
    expect(rejected[0]?.reason).toBe("type");
  });

  it("rejects photos over the size limit", () => {
    const { rejected } = validatePhotos([
      photo("huge.jpg", "image/jpeg", MAX_PHOTO_BYTES + 1),
    ]);
    expect(rejected[0]?.reason).toBe("size");
  });

  it("respects the maximum number of photos already uploaded", () => {
    const { accepted, rejected } = validatePhotos(
      [photo("a.jpg", "image/jpeg", 100), photo("b.jpg", "image/jpeg", 100)],
      7,
    );
    expect(accepted).toHaveLength(1);
    expect(rejected[0]?.reason).toBe("count");
  });
});

describe("tax id", () => {
  it.each([
    ["12345678Z", "dni"],
    ["x1234567l", "nie"],
    ["B12345674", "cif"],
    ["Q2826000H", "cif"],
  ])("recognises %s", (raw, kind) => {
    expect(taxIdKind(raw)).toBe(kind);
  });

  it.each(["12345678A", "B12345670", "B1234567D", "Q2826000A", "1234", ""])(
    "rejects %s",
    (raw) => {
      expect(taxIdKind(raw)).toBeNull();
    },
  );
});
