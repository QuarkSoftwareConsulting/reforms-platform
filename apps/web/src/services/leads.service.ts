/** Endpoints de solicitudes. */

import { CATALOG_TAG, DAILY_REVALIDATE_SECONDS, PRICING_TAG } from "@/helpers/cacheTags";
import type { ProjectSchedule, PropertyType } from "@/helpers/leadOptions";
import { apiBaseUrl, request } from "@/services/api";
import type {
  CatalogCategory,
  CreatedLead,
  LeadDetail,
  LeadList,
  Locale,
  Money,
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
  service_ids: string[];
  property_type: PropertyType;
  schedule: ProjectSchedule;
  /** Codigo del SMS; `null` si el entorno no verifica por SMS. */
  phone_verification_code: string | null;
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

  /** Pide el SMS de verificacion. `required: false` = este entorno no verifica. */
  startPhoneVerification(phone: string): Promise<{ required: boolean }> {
    return request<{ required: boolean }>("/leads/phone-verification", {
      method: "POST",
      body: { phone },
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

  categories(locale: Locale): Promise<CatalogCategory[]> {
    // Se regenera cuando el admin cambia el catalogo; un dia como respaldo.
    return request<CatalogCategory[]>("/categories", {
      locale,
      anonymous: true,
      revalidate: DAILY_REVALIDATE_SECONDS,
      tags: [CATALOG_TAG],
    });
  },

  /** Foto de la tarjeta de un servicio destacado: URL estable que redirige al bucket. */
  serviceImageUrl(serviceId: string): string {
    return `${apiBaseUrl}/catalog/services/${serviceId}/image`;
  },

  /** Mensualidad vigente, para anunciarla en la landing. `amount` null: aun sin fijar. */
  subscriptionPrice(locale: Locale): Promise<{ amount: Money | null }> {
    return request<{ amount: Money | null }>("/subscription-price", {
      locale,
      anonymous: true,
      revalidate: DAILY_REVALIDATE_SECONDS,
      tags: [PRICING_TAG],
    });
  },

  postalCode(code: string): Promise<PostalCodeInfo> {
    return request<PostalCodeInfo>(`/postal-codes/${encodeURIComponent(code)}`, {
      anonymous: true,
    });
  },
};
