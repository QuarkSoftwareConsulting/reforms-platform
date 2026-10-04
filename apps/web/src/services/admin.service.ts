/** Cliente HTTP del backoffice. */

import type { VerificationStatus } from "@/helpers/professionalOptions";
import { request } from "@/services/api";
import type {
  AdminAccount,
  AdminLeadList,
  AdminMetrics,
  AdminProfessionalList,
  AdminPurchase,
  Category,
  CreatedLead,
  Locale,
  Professional,
  Rejection,
  SubscriptionPrice,
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

  /** Abona (centimos positivos) o carga (negativos) saldo. Un abono salda antes la deuda. */
  adjustCredit(
    professionalId: string,
    amountCents: number,
    note: string,
    locale: Locale,
  ): Promise<AdminAccount> {
    return request<AdminAccount>(`/admin/professionals/${professionalId}/credit-adjustments`, {
      method: "POST",
      body: { amount_cents: amountCents, note },
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
};
