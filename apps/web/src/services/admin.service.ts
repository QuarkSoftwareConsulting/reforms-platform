/** Cliente HTTP del backoffice. */

import { request } from "@/services/api";
import type {
  AdminLeadList,
  AdminMetrics,
  AdminProfessionalList,
  AdminPurchase,
  Category,
  CreatedLead,
  Locale,
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

  professionals(query: string, locale: Locale): Promise<AdminProfessionalList> {
    const params = new URLSearchParams();
    if (query.trim()) params.set("query", query.trim());
    return request<AdminProfessionalList>(`/admin/professionals?${params.toString()}`, { locale });
  },

  reviewPurchase(purchaseId: string, note: string, locale: Locale): Promise<void> {
    return request<void>(`/admin/purchases/${purchaseId}/reviews`, {
      method: "POST",
      body: { note },
      locale,
    });
  },
};
