/**
 * Opciones cerradas del alta del profesional (F02).
 *
 * Reflejan los enums del backend (`ProfessionalType`, `DocumentKind`,
 * `VerificationStatus`); las etiquetas viven en `messages/*.json` por codigo.
 */

export const PROFESSIONAL_TYPES = ["self_employed", "company", "independent"] as const;
export type ProfessionalType = (typeof PROFESSIONAL_TYPES)[number];

export const DOCUMENT_KINDS = ["tax_registration", "identity"] as const;
export type DocumentKind = (typeof DOCUMENT_KINDS)[number];

export type VerificationStatus = "incomplete" | "pending" | "approved" | "rejected";

/** Que documento exige cada tipo de alta. Lo impone el backend; aqui se anticipa. */
export const REQUIRED_DOCUMENT: Record<ProfessionalType, DocumentKind> = {
  self_employed: "tax_registration",
  company: "tax_registration",
  independent: "identity",
};

export const MAX_WORK_PHOTOS = 8;
export const DOCUMENT_CONTENT_TYPES = [
  "application/pdf",
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/heic",
] as const;
