/**
 * DTOs del API. Reflejan los schemas Pydantic de `apps/api`.
 *
 * Nota importante sobre `LeadPublic`: no tiene campos para el nombre, telefono ni
 * email del cliente. Esa ausencia es intencionada — el explorador no puede
 * mostrar lo que su tipo no contiene.
 */

export type Locale = "es" | "en";

export interface Money {
  amount_cents: number;
  currency: string;
  formatted: string;
}

export interface Category {
  id: string;
  slug: string;
  name: string;
  /** Precio de referencia del oficio. El de un lead concreto viene en `LeadPublic.price`. */
  suggested_lead_price: Money;
}

export interface LeadPublic {
  id: string;
  title: string;
  description: string;
  city: string;
  province: string;
  postal_code_prefix: string;
  category: Category;
  photo_urls: string[];
  created_at: string;
  remaining_slots: number;
  distance_km: number | null;
  masked_phone: string;
  masked_email: string | null;
  already_purchased: boolean;
  price: Money;
}

export interface LeadList {
  items: LeadPublic[];
  total: number;
  limit: number;
  offset: number;
}

/** Datos de contacto del cliente. Solo llega relleno tras una compra pagada. */
export interface ClientContact {
  name: string;
  phone: string;
  email: string | null;
}

export type PurchaseStatus = "reserved" | "paid" | "expired" | "failed" | "refunded";

export interface Purchase {
  id: string;
  status: PurchaseStatus;
  amount: Money;
  created_at: string;
  paid_at: string | null;
  reserved_until: string | null;
}

export interface LeadDetail {
  lead: LeadPublic;
  is_unlocked: boolean;
  contact: ClientContact | null;
  purchase: Purchase | null;
}

export interface CreatedLead {
  id: string;
  status: string;
  city: string;
  province: string;
  created_at: string;
}

export interface StartPurchase {
  purchase_id: string;
  checkout_url: string;
  amount: Money;
  expires_at: string | null;
}

export interface PurchasedLead {
  lead_id: string;
  title: string;
  city: string;
  province: string;
  category: Category;
  purchase: Purchase;
  is_unlocked: boolean;
  contact: ClientContact | null;
}

export interface Professional {
  id: string;
  business_name: string;
  phone: string;
  postal_code: string;
  city: string | null;
  province: string | null;
  service_radius_km: number;
  categories: Category[];
}

export interface Me {
  user_id: string;
  email: string;
  role: "professional" | "admin";
  display_name: string | null;
  professional: Professional | null;
}

export interface PostalCodeInfo {
  code: string;
  city: string;
  province: string;
  latitude: number;
  longitude: number;
}

export interface PresignedUpload {
  storage_key: string;
  upload_url: string;
  method: string;
  headers: Record<string, string>;
  expires_in_seconds: number;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
}

export interface AdminLead {
  id: string;
  title: string;
  description: string;
  city: string;
  province: string;
  postal_code_prefix: string;
  category: Category;
  photo_urls: string[];
  created_at: string;
  status: "published" | "exhausted" | "disabled";
  source: "organic" | "admin";
  purchases_count: number;
  max_purchases: number;
  remaining_slots: number;
  price: Money;
}

export interface AdminLeadList {
  items: AdminLead[];
  total: number;
  limit: number;
  offset: number;
}

export interface AdminMetrics {
  leads_total: number;
  leads_published: number;
  leads_exhausted: number;
  leads_disabled: number;
  leads_organic: number;
  leads_admin: number;
  professionals_total: number;
  paid_purchases: number;
  paid_leads: number;
  coverage_rate: number;
  liquidity: number;
  revenue_by_currency: Record<string, Money>;
}

export interface AdminProfessional {
  id: string;
  business_name: string;
  postal_code: string;
  city: string | null;
  province: string | null;
  service_radius_km: number;
  categories: Category[];
}

export interface AdminProfessionalList {
  items: AdminProfessional[];
  total: number;
  limit: number;
  offset: number;
}

export interface AdminPurchase {
  purchase: Purchase;
  professional: AdminProfessional | null;
  review_count: number;
}
