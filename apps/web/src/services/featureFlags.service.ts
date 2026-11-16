/** Feature flags del entorno del API (se cambian a mano en la tabla `feature_flags`). */

import { request } from "@/services/api";

export type FeatureFlags = Readonly<Record<string, boolean>>;

export const featureFlagsService = {
  /**
   * Nunca lanza: si el API no responde todas cuentan como apagadas. Lo que va detras de
   * una flag es lo nuevo, y es preferible ocultarlo a romper la pagina.
   */
  async list(): Promise<FeatureFlags> {
    try {
      const { flags } = await request<{ flags: Record<string, boolean> }>("/feature-flags", {
        anonymous: true,
      });
      return flags;
    } catch {
      return {};
    }
  },
};
