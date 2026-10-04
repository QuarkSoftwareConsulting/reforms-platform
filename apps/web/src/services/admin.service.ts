/** Cliente HTTP del backoffice. */

import type { VerificationStatus } from "@/helpers/professionalOptions";
import { request } from "@/services/api";
import type {
  AdminLeadList,
  AdminMetrics,
  AdminProfessionalList,
  AdminPurchase,
  AdminPurchaseList,
  AdminUser,
  AdminUserList,
  Category,
  CreatedLead,
  Locale,
  MetricsTimeseries,
  Professional,
  PurchaseStatus,
  Rejection,
  SubscriptionPrice,
  UserRole,
  UserRoleEvent,
  VerificationDossier,
} from "@/types/api";

export interface AdminLeadFilters {
  categoryId?: string;
  status?: "published" | "exhausted" | "disabled";
  source?: "organic" | "admin";
}

export interface AdminLeadPayload {
  category_id: string;
  title: string;
  description: string;
  postal_code: string;
  client_name: string;
  client_phone: string;
  client_email: string | null;
  photo_keys: string[];
  consent: {
    policy_version: string;
    accepted_at: string;
    channel: string;
    campaign_reference: string | null;
  };
}

export interface Page {
  limit: number;
  offset: number;
}

export interface AdminUserFilters extends Page {
  query?: string;
  role?: UserRole;
  verificationStatus?: VerificationStatus;
}

export interface AdminPurchaseFilters extends Page {
  status?: PurchaseStatus;
  /** `YYYY-MM-DD` en hora de Madrid, incluido. */
  from?: string;
  /** `YYYY-MM-DD` en hora de Madrid, incluido. */
  to?: string;
}

function query(entries: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(entries)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  return params.toString();
}

function paramsFor(filters: AdminLeadFilters): string {
  const params = new URLSearchParams();
  if (filters.categoryId) params.set("category_id", filters.categoryId);
  if (filters.status) params.set("status", filters.status);
  if (filters.source) params.set("source", filters.source);
  return params.toString();
}

export const adminService = {
  metrics(locale: Locale): Promise<AdminMetrics> {
    return request<AdminMetrics>("/admin/metrics", { locale });
  },

  subscriptionPrice(locale: Locale): Promise<SubscriptionPrice> {
    return request<SubscriptionPrice>("/admin/subscription-price", { locale });
  },

  /** Crea un precio nuevo en Stripe: solo afecta a las suscripciones nuevas. */
  setSubscriptionPrice(amountCents: number, locale: Locale): Promise<SubscriptionPrice> {
    return request<SubscriptionPrice>("/admin/subscription-price", {
      method: "PUT",
      body: { amount_cents: amountCents },
      locale,
    });
  },

  leads(filters: AdminLeadFilters, locale: Locale): Promise<AdminLeadList> {
    const params = paramsFor(filters);
    return request<AdminLeadList>(`/admin/leads${params ? `?${params}` : ""}`, { locale });
  },

  createLead(payload: AdminLeadPayload, locale: Locale): Promise<CreatedLead> {
    return request<CreatedLead>("/admin/leads", { method: "POST", body: payload, locale });
  },

  disableLead(leadId: string, locale: Locale): Promise<{ id: string; status: string }> {
    return request<{ id: string; status: string }>(`/admin/leads/${leadId}/disable`, {
      method: "POST",
      locale,
    });
  },

  republishLead(leadId: string, locale: Locale): Promise<{ id: string; status: string }> {
    return request<{ id: string; status: string }>(`/admin/leads/${leadId}/republish`, {
      method: "POST",
      locale,
    });
  },

  setLeadPrice(leadId: string, amountCents: number | null, locale: Locale): Promise<void> {
    return request<void>(`/admin/leads/${leadId}/price`, {
      method: "PUT",
      body: { amount_cents: amountCents },
      locale,
    });
  },

  setCategoryPrice(categoryId: string, amountCents: number, locale: Locale): Promise<Category> {
    return request<Category>(`/admin/categories/${categoryId}/suggested-price`, {
      method: "PUT",
      body: { amount_cents: amountCents },
      locale,
    });
  },

  purchases(leadId: string, locale: Locale): Promise<AdminPurchase[]> {
    return request<AdminPurchase[]>(`/admin/leads/${leadId}/purchases`, { locale });
  },

  professionals(
    query: string,
    locale: Locale,
    verificationStatus?: VerificationStatus,
  ): Promise<AdminProfessionalList> {
    const params = new URLSearchParams();
    if (query.trim()) params.set("query", query.trim());
    if (verificationStatus) params.set("verification_status", verificationStatus);
    return request<AdminProfessionalList>(`/admin/professionals?${params.toString()}`, { locale });
  },

  /** Expediente de validacion. Las URLs de los documentos caducan en minutos. */
  verificationDossier(professionalId: string, locale: Locale): Promise<VerificationDossier> {
    return request<VerificationDossier>(`/admin/professionals/${professionalId}/verification`, {
      locale,
    });
  },

  approveProfessional(professionalId: string, locale: Locale): Promise<Professional> {
    return request<Professional>(`/admin/professionals/${professionalId}/approve`, {
      method: "POST",
      locale,
    });
  },

  /** Reembolsa el primer cobro y cancela la recarga. 503 si la pasarela falla. */
  rejectProfessional(professionalId: string, reason: string, locale: Locale): Promise<Rejection> {
    return request<Rejection>(`/admin/professionals/${professionalId}/reject`, {
      method: "POST",
      body: { reason },
      locale,
    });
  },

  reviewPurchase(purchaseId: string, note: string, locale: Locale): Promise<void> {
    return request<void>(`/admin/purchases/${purchaseId}/reviews`, {
      method: "POST",
      body: { note },
      locale,
    });
  },

  /** Directorio de usuarios: rol y, si lo tienen, resumen del perfil profesional. */
  users(filters: AdminUserFilters, locale: Locale): Promise<AdminUserList> {
    const params = query({
      query: filters.query?.trim(),
      role: filters.role,
      verification_status: filters.verificationStatus,
      limit: filters.limit,
      offset: filters.offset,
    });
    return request<AdminUserList>(`/admin/users?${params}`, { locale });
  },

  /** Surte efecto en la siguiente peticion del usuario: el rol vive en la BD. */
  setUserRole(userId: string, role: UserRole, note: string | null, locale: Locale): Promise<AdminUser> {
    return request<AdminUser>(`/admin/users/${userId}/role`, {
      method: "PUT",
      body: { role, note },
      locale,
    });
  },

  userRoleEvents(userId: string, locale: Locale): Promise<UserRoleEvent[]> {
    return request<UserRoleEvent[]>(`/admin/users/${userId}/role-events`, { locale });
  },

  /** Todas las compras, lo mas reciente primero. Sin PII del cliente. */
  allPurchases(filters: AdminPurchaseFilters, locale: Locale): Promise<AdminPurchaseList> {
    const params = query({
      status: filters.status,
      from: filters.from,
      to: filters.to,
      limit: filters.limit,
      offset: filters.offset,
    });
    return request<AdminPurchaseList>(`/admin/purchases?${params}`, { locale });
  },

  /** Un punto por dia, ambos extremos incluidos (`YYYY-MM-DD`). */
  metricsTimeseries(from: string, to: string, locale: Locale): Promise<MetricsTimeseries> {
    return request<MetricsTimeseries>(`/admin/metrics/timeseries?${query({ from, to })}`, {
      locale,
    });
  },
};
