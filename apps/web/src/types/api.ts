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

/** Desglose de un precio con IVA incluido. */
export interface VatBreakdown {
  net: Money;
  vat: Money;
  rate_percent: number;
}

export interface LeadPublic {
  id: string;
  title: string;
  description: string;
  city: string;
  province: string;
  postal_code_prefix: string;
  /** CP completo; `null` si el consentimiento del cliente no cubre mostrarlo. */
  postal_code: string | null;
  /** Nombre de pila; `null` si el consentimiento del cliente no cubre mostrarlo. */
  client_first_name: string | null;
  category: Category;
  photo_urls: string[];
  created_at: string;
  remaining_slots: number;
  /** Profesionales que ya compraron el contacto. */
  purchases_count: number;
  max_purchases: number;
  /** Agotado: se muestra como "Cerrado" y no admite compras. */
  is_closed: boolean;
  distance_km: number | null;
  masked_phone: string;
  masked_email: string | null;
  already_purchased: boolean;
  /** Con IVA incluido. */
  price: Money;
  price_breakdown: VatBreakdown;
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
  /** Parte pagada con el saldo de la recarga; el resto se cobro en la pasarela. */
  credit_applied?: Money | null;
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

/**
 * Resultado de iniciar una compra. Si `paid_with_credit`, el saldo cubrio todo:
 * no hay checkout y el contacto ya esta desbloqueado.
 */
export interface StartPurchase {
  purchase_id: string;
  checkout_url: string | null;
  amount: Money;
  credit_applied: Money;
  amount_due: Money;
  paid_with_credit: boolean;
  expires_at: string | null;
}

export type SubscriptionStatus = "none" | "pending" | "active" | "past_due" | "canceled";

export type CreditEntryKind =
  | "topup"
  | "spend"
  | "spend_reversal"
  | "adjustment_credit"
  | "adjustment_debit";

export interface CreditEntry {
  kind: CreditEntryKind;
  amount: Money;
  signed_amount_cents: number;
  created_at: string;
}

/** Recarga mensual y saldo. `is_active` es lo que decide si se puede comprar. */
export interface Account {
  status: SubscriptionStatus;
  is_active: boolean;
  balance: Money;
  topup_amount: Money;
  current_period_end: string | null;
  can_manage_billing: boolean;
  entries: CreditEntry[];
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
  /** Solo presente cuando ya existe perfil profesional. */
  account: Account | null;
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
  active_accounts: number;
  topup_revenue_by_currency: Record<string, Money>;
}

export interface AdminProfessional {
  id: string;
  business_name: string;
  postal_code: string;
  city: string | null;
  province: string | null;
  service_radius_km: number;
  categories: Category[];
  account: AdminAccount | null;
}

export interface SubscriptionPrice {
  amount: Money;
  updated_at: string | null;
  /** Aun no la fijo el admin: rige el valor inicial de configuracion. */
  is_default: boolean;
  /** Sin precio en Stripe nadie puede suscribirse. */
  configured: boolean;
}

export interface AdminAccount {
  status: SubscriptionStatus;
  is_active: boolean;
  balance: Money;
  current_period_end: string | null;
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
