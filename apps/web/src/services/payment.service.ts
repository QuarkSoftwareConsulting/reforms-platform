/** Endpoints de compra de contactos. */

import { request } from "@/services/api";
import type { Locale, PurchasedLead, StartPurchase } from "@/types/api";

export const paymentService = {
  /**
   * Reserva la plaza y devuelve la URL del checkout.
   *
   * El contacto NO se desbloquea al volver de la pasarela: eso lo confirma el
   * webhook firmado por Stripe contra el backend.
   */
  startPurchase(leadId: string, locale: Locale): Promise<StartPurchase> {
    return request<StartPurchase>(`/leads/${leadId}/purchase`, { method: "POST", locale });
  },

  myPurchases(locale: Locale, limit = 50, offset = 0): Promise<PurchasedLead[]> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    return request<PurchasedLead[]>(`/me/purchases?${params.toString()}`, { locale });
  },
};
