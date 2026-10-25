/** Tarjetas de oficios de la landing, a partir del catalogo. Funciones puras. */

import { PHASE_PRODUCTION_BUILD } from "next/constants";

import type { CatalogCategory, Money } from "@/types/api";

export interface LandingTrade {
  serviceId: string;
  name: string;
  categorySlug: string;
  serviceSlug: string;
  /** Precio sugerido de su categoria: lo que se cobra si el contacto no tiene precio propio. */
  price: Money;
}

/**
 * Si la landing se pinta sin catalogo cuando el API no responde.
 *
 * Solo al compilar (el CI construye sin API) y en desarrollo. En produccion el error se
 * propaga a proposito: al regenerar en segundo plano, Next conserva la ultima version
 * buena en vez de publicar una sin oficios que Google podria indexar.
 */
export function toleratesApiOutage(
  phase: string | undefined = process.env.NEXT_PHASE,
  nodeEnv: string | undefined = process.env.NODE_ENV,
): boolean {
  return phase === PHASE_PRODUCTION_BUILD || nodeEnv === "development";
}

/**
 * Los servicios que el admin destaco, en el orden del catalogo (categoria y luego
 * servicio). El API solo devuelve categorias y servicios activos, y un destacado
 * siempre tiene foto: no hay tarjetas rotas que filtrar aqui.
 */
export function featuredTrades(categories: CatalogCategory[]): LandingTrade[] {
  return categories.flatMap((category) =>
    category.services
      .filter((service) => service.featured)
      .map((service) => ({
        serviceId: service.id,
        name: service.landing_name,
        categorySlug: category.slug,
        serviceSlug: service.slug,
        price: category.suggested_lead_price,
      })),
  );
}
