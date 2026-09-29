/** Endpoints del perfil profesional y de su alta (F02). */

import type { DocumentKind, ProfessionalType } from "@/helpers/professionalOptions";
import { request } from "@/services/api";
import type {
  Locale,
  Me,
  PresignedUpload,
  Professional,
  ProfessionalDocument,
} from "@/types/api";

export interface ProfilePayload {
  business_name: string;
  phone: string;
  postal_code: string;
  service_radius_km: number;
  category_ids: string[];
  service_ids: string[];
  professional_type: ProfessionalType | null;
  legal_name: string | null;
  tax_id: string | null;
  address: string | null;
  profile_photo_key: string | null;
  logo_key: string | null;
  work_photo_keys: string[];
}

/** `media` va al bucket publico; `document`, al privado. */
export type UploadPurpose = "media" | "document";

export const professionalService = {
  me(locale: Locale): Promise<Me> {
    return request<Me>("/me", { locale });
  },

  upsertProfile(payload: ProfilePayload, locale: Locale): Promise<Professional> {
    return request<Professional>("/me/professional", { method: "PUT", body: payload, locale });
  },

  requestUpload(purpose: UploadPurpose, file: File): Promise<PresignedUpload> {
    return request<PresignedUpload>("/me/professional/uploads", {
      method: "POST",
      body: {
        purpose,
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
      },
    });
  },

  addDocument(
    kind: DocumentKind,
    storageKey: string,
    filename: string,
  ): Promise<ProfessionalDocument> {
    return request<ProfessionalDocument>("/me/professional/documents", {
      method: "POST",
      body: { kind, storage_key: storageKey, filename },
    });
  },

  removeDocument(documentId: string): Promise<void> {
    return request<void>(`/me/professional/documents/${documentId}`, { method: "DELETE" });
  },

  /** 409 PROFILE_INCOMPLETE con `details.missing` si falta algo. */
  submitForReview(locale: Locale): Promise<Professional> {
    return request<Professional>("/me/professional/submit", { method: "POST", locale });
  },
};
