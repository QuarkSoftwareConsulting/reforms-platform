/**
 * Esquemas de validacion compartidos por los formularios.
 *
 * Duplican a proposito las reglas del backend: validar en cliente da respuesta
 * inmediata, pero el backend nunca confia en ello y vuelve a validar.
 */

import { z } from "zod";

export const MIN_DESCRIPTION_LENGTH = 20;
export const MAX_DESCRIPTION_LENGTH = 4000;
export const MAX_PHOTOS = 8;
export const MAX_PHOTO_BYTES = 10 * 1024 * 1024;
export const ALLOWED_PHOTO_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/heic",
] as const;

/** Codigo postal espanol: cinco digitos, del 01000 al 52999. */
export const spanishPostalCode = z
  .string()
  .trim()
  .regex(/^\d{5}$/, "postalCodeFormat")
  .refine((value) => {
    const province = Number(value.slice(0, 2));
    return province >= 1 && province <= 52;
  }, "postalCodeUnknown");

/** Telefono espanol: movil (6/7) o fijo (8/9), con prefijo +34 opcional. */
export const phoneNumber = z
  .string()
  .trim()
  .transform((value) => value.replace(/[\s\-().]/g, ""))
  .refine((value) => /^(\+34)?[6789]\d{8}$/.test(value), "phoneFormat");

export const optionalEmail = z
  .union([z.literal(""), z.string().trim().email("emailFormat")])
  .transform((value) => (value === "" ? null : value.toLowerCase()));

export const leadStepCategorySchema = z.object({
  categoryId: z.string().uuid("categoryRequired"),
});

export const leadStepDetailsSchema = z.object({
  title: z.string().trim().min(3, "titleTooShort").max(140, "titleTooLong"),
  description: z
    .string()
    .trim()
    .min(MIN_DESCRIPTION_LENGTH, "descriptionTooShort")
    .max(MAX_DESCRIPTION_LENGTH, "descriptionTooLong"),
  postalCode: spanishPostalCode,
});

export const leadStepContactSchema = z.object({
  clientName: z.string().trim().min(2, "nameTooShort").max(200, "nameTooLong"),
  clientPhone: phoneNumber,
  clientEmail: optionalEmail,
  // El consentimiento no es un campo mas: sin el no hay base legal para publicar.
  consentAccepted: z.literal(true, {
    errorMap: () => ({ message: "consentRequired" }),
  }),
});

export const leadFormSchema = leadStepCategorySchema
  .merge(leadStepDetailsSchema)
  .merge(leadStepContactSchema);

export type LeadFormValues = z.infer<typeof leadFormSchema>;

export const professionalProfileSchema = z.object({
  businessName: z.string().trim().min(2, "businessNameTooShort").max(200, "businessNameTooLong"),
  phone: phoneNumber,
  postalCode: spanishPostalCode,
  serviceRadiusKm: z.coerce.number().int().min(1, "radiusTooSmall").max(300, "radiusTooLarge"),
  categoryIds: z.array(z.string().uuid()).min(1, "categoriesRequired").max(12, "tooManyCategories"),
});

export type ProfessionalProfileValues = z.infer<typeof professionalProfileSchema>;

export interface PhotoRejection {
  filename: string;
  reason: "type" | "size" | "count";
}

/** Filtra los archivos que el backend rechazaria, sin subirlos. */
export function validatePhotos(
  files: File[],
  alreadyUploaded = 0,
): { accepted: File[]; rejected: PhotoRejection[] } {
  const accepted: File[] = [];
  const rejected: PhotoRejection[] = [];

  for (const file of files) {
    if (accepted.length + alreadyUploaded >= MAX_PHOTOS) {
      rejected.push({ filename: file.name, reason: "count" });
      continue;
    }
    if (!ALLOWED_PHOTO_TYPES.includes(file.type as (typeof ALLOWED_PHOTO_TYPES)[number])) {
      rejected.push({ filename: file.name, reason: "type" });
      continue;
    }
    if (file.size > MAX_PHOTO_BYTES) {
      rejected.push({ filename: file.name, reason: "size" });
      continue;
    }
    accepted.push(file);
  }
  return { accepted, rejected };
}
