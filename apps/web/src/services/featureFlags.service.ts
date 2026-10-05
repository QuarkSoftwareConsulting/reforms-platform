/** Feature flags del entorno del API (se cambian a mano en la tabla `feature_flags`). */

import { request } from "@/services/api";

export type FeatureFlags = Readonly<Record<string, boolean>>;

/**
 * Lo que tarda como maximo en verse un cambio de flag en la web. Igual que el
 * `Cache-Control` del endpoint.
 */
export const FEATURE_FLAGS_REVALIDATE_SECONDS = 60;

export const featureFlagsService = {
  /**
   * Nunca lanza: si el API no responde (un build sin red, una caida) todas cuentan como
   * apagadas. Lo que va detras de una flag es lo nuevo, y es preferible ocultarlo a
   * tumbar la pagina o el build.
   */
  async list(): Promise<FeatureFlags> {
    try {
      const { flags } = await request<{ flags: Record<string, boolean> }>("/feature-flags", {
        anonymous: true,
        revalidate: FEATURE_FLAGS_REVALIDATE_SECONDS,
      });
      return flags;
    } catch {
      return {};
    }
  },
};
