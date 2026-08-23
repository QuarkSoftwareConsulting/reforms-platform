/** Endpoints del perfil profesional. */

import { request } from "@/services/api";
import type { Locale, Me, Professional } from "@/types/api";

export interface ProfilePayload {
  business_name: string;
  phone: string;
  postal_code: string;
  service_radius_km: number;
  category_ids: string[];
}

export const professionalService = {
  me(locale: Locale): Promise<Me> {
    return request<Me>("/me", { locale });
  },

  upsertProfile(payload: ProfilePayload, locale: Locale): Promise<Professional> {
    return request<Professional>("/me/professional", { method: "PUT", body: payload, locale });
  },
};
