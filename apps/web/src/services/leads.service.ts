/** Endpoints de solicitudes. */

import { request } from "@/services/api";
import type {
  Category,
  CreatedLead,
  LeadDetail,
  LeadList,
  Locale,
  PostalCodeInfo,
  PresignedUpload,
} from "@/types/api";

export interface CreateLeadPayload {
  category_id: string;
  title: string;
  description: string;
  postal_code: string;
  client_name: string;
  client_phone: string;
  client_email: string | null;
  photo_keys: string[];
  consent: { accepted: boolean };
}

export interface LeadFilters {
  categoryIds?: string[];
  radiusKm?: number;
  limit?: number;
  offset?: number;
}

export const leadsService = {
  /** Publicacion publica: el cliente no necesita cuenta. */
  create(payload: CreateLeadPayload, locale: Locale): Promise<CreatedLead> {
    return request<CreatedLead>("/leads", {
      method: "POST",
      body: payload,
      locale,
      anonymous: true,
    });
  },

  presignPhoto(
    filename: string,
    contentType: string,
    sizeBytes: number,
  ): Promise<PresignedUpload> {
    return request<PresignedUpload>("/leads/photos/presign", {
      method: "POST",
      body: { filename, content_type: contentType, size_bytes: sizeBytes },
      anonymous: true,
    });
  },

  list(filters: LeadFilters, locale: Locale): Promise<LeadList> {
    const params = new URLSearchParams();
    filters.categoryIds?.forEach((id) => params.append("category_ids", id));
    if (filters.radiusKm) params.set("radius_km", String(filters.radiusKm));
    params.set("limit", String(filters.limit ?? 20));
    params.set("offset", String(filters.offset ?? 0));
    return request<LeadList>(`/leads?${params.toString()}`, { locale });
  },

  detail(leadId: string, locale: Locale): Promise<LeadDetail> {
    return request<LeadDetail>(`/leads/${leadId}`, { locale });
  },

  categories(locale: Locale): Promise<Category[]> {
    // El catalogo cambia muy poco: se cachea 5 minutos para las paginas SSR.
    return request<Category[]>("/categories", { locale, anonymous: true, revalidate: 300 });
  },

  postalCode(code: string): Promise<PostalCodeInfo> {
    return request<PostalCodeInfo>(`/postal-codes/${encodeURIComponent(code)}`, {
      anonymous: true,
    });
  },
};
