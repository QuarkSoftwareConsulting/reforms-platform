/**
 * Esquemas de validacion compartidos por los formularios.
 *
 * Duplican a proposito las reglas del backend: validar en cliente da respuesta
 * inmediata, pero el backend nunca confia en ello y vuelve a validar.
 */

import { z } from "zod";

import { PROJECT_SCHEDULES, PROPERTY_TYPES } from "@/helpers/leadOptions";
import { MAX_WORK_PHOTOS, PROFESSIONAL_TYPES } from "@/helpers/professionalOptions";
import { taxIdKind } from "@/helpers/taxId";

export const MIN_DESCRIPTION_LENGTH = 20;
export const MAX_DESCRIPTION_LENGTH = 4000;
export const MAX_PHOTOS = 8;
export const MAX_SERVICES_PER_LEAD = 10;
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

/**
 * CP donde se pueden publicar solicitudes: en la Etapa 1, solo la Comunidad de
 * Madrid. La regla la impone el backend (`ServiceArea`); aqui se avisa antes.
 */
export const coveredPostalCode = spanishPostalCode.refine(
  (value) => value.startsWith("28"),
  "postalCodeNotCovered",
);

/** Telefono espanol: movil (6/7) o fijo (8/9), con prefijo +34 opcional. */
export const phoneNumber = z
  .string()
  .trim()
  .transform((value) => value.replace(/[\s\-().]/g, ""))
  .refine((value) => /^(\+34)?[6789]\d{8}$/.test(value), "phoneFormat");

/** Movil espanol (6/7): el unico al que se puede verificar por SMS. */
export const spanishMobile = z
  .string()
  .trim()
  .transform((value) => value.replace(/[\s\-().]/g, ""))
  .refine((value) => /^(\+34|0034)?[67]\d{8}$/.test(value), "mobileFormat");

const optionalText = (max: number, tooLong: string) =>
  z
    .string()
    .trim()
    .max(max, tooLong)
    .transform((value) => (value === "" ? null : value));

export const optionalEmail = z
  .union([z.literal(""), z.string().trim().email("emailFormat")])
  .transform((value) => (value === "" ? null : value.toLowerCase()));

export const leadStepCategorySchema = z.object({
  categoryId: z.string().uuid("categoryRequired"),
  // Opcionales: el cliente puede no encontrar su servicio exacto en el catalogo.
  serviceIds: z.array(z.string().uuid()).max(MAX_SERVICES_PER_LEAD, "tooManyServices"),
});

export const leadStepDetailsSchema = z.object({
  title: z.string().trim().min(3, "titleTooShort").max(140, "titleTooLong"),
  description: z
    .string()
    .trim()
    .min(MIN_DESCRIPTION_LENGTH, "descriptionTooShort")
    .max(MAX_DESCRIPTION_LENGTH, "descriptionTooLong"),
  propertyType: z.enum(PROPERTY_TYPES, { errorMap: () => ({ message: "propertyTypeRequired" }) }),
  schedule: z.enum(PROJECT_SCHEDULES, { errorMap: () => ({ message: "scheduleRequired" }) }),
  postalCode: coveredPostalCode,
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

/**
 * Lead que el admin ingresa a mano (captado por un canal externo). Las claves son las
 * del `<form>` y las del API, no las del formulario publico. Reusa las reglas del
 * formulario del cliente y añade las del consentimiento, que aqui se registra a mano.
 */
export const adminLeadSchema = z.object({
  category_id: leadStepCategorySchema.shape.categoryId,
  title: leadStepDetailsSchema.shape.title,
  description: leadStepDetailsSchema.shape.description,
  postal_code: coveredPostalCode,
  client_name: leadStepContactSchema.shape.clientName,
  client_phone: phoneNumber,
  client_email: optionalEmail,
  channel: z.string().trim().min(2, "channelRequired").max(120, "channelTooLong"),
  policy_version: z.string().trim().min(1, "policyRequired").max(40, "policyTooLong"),
  campaign_reference: optionalText(200, "campaignTooLong"),
  // Lo que da un `datetime-local`: hora local sin zona. El backend rechaza el futuro.
  accepted_at: z
    .string()
    .min(1, "acceptedAtRequired")
    .refine((value) => !Number.isNaN(new Date(value).getTime()), "acceptedAtInvalid")
    .refine((value) => new Date(value).getTime() <= Date.now(), "acceptedAtFuture"),
});

export type AdminLeadValues = z.infer<typeof adminLeadSchema>;

export const professionalProfileSchema = z
  .object({
    businessName: z
      .string()
      .trim()
      .min(2, "businessNameTooShort")
      .max(200, "businessNameTooLong"),
    phone: spanishMobile,
    // En la Etapa 1 la base del profesional tambien tiene que estar en Madrid (F02).
    postalCode: coveredPostalCode,
    serviceRadiusKm: z.coerce.number().int().min(1, "radiusTooSmall").max(300, "radiusTooLarge"),
    categoryIds: z
      .array(z.string().uuid())
      .min(1, "categoriesRequired")
      .max(12, "tooManyCategories"),
    serviceIds: z.array(z.string().uuid()).max(100),
    // Los datos de alta son opcionales al guardar: se exigen al enviar a revision.
    professionalType: z.enum(PROFESSIONAL_TYPES).nullable(),
    legalName: optionalText(200, "legalNameTooLong"),
    taxId: z
      .string()
      .trim()
      .transform((value) => (value === "" ? null : value.replace(/[\s.-]/g, "").toUpperCase()))
      .refine((value) => value === null || taxIdKind(value) !== null, "taxIdInvalid"),
    address: optionalText(300, "addressTooLong"),
    workPhotoKeys: z.array(z.string()).max(MAX_WORK_PHOTOS, "tooManyWorkPhotos"),
  })
  .refine(
    (values) =>
      values.professionalType !== "company" ||
      values.taxId === null ||
      taxIdKind(values.taxId) === "cif",
    { message: "companyNeedsCif", path: ["taxId"] },
  );

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
