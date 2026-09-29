/** Endpoints de la recarga mensual del profesional. */

import { request } from "@/services/api";
import type { Account, Locale } from "@/types/api";

export const subscriptionService = {
  account(locale: Locale): Promise<Account> {
    return request<Account>("/me/account", { locale });
  },

  /**
   * URL del checkout de la recarga.
   *
   * Volver del checkout NO activa la cuenta: la activa el webhook firmado por
   * Stripe cuando el cobro se confirma.
   */
  startCheckout(locale: Locale): Promise<{ checkout_url: string }> {
    return request<{ checkout_url: string }>("/me/subscription/checkout", {
      method: "POST",
      locale,
    });
  },

  openPortal(locale: Locale): Promise<{ url: string }> {
    return request<{ url: string }>("/me/subscription/portal", { method: "POST", locale });
  },
};
