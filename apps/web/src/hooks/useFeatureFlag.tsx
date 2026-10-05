"use client";

/**
 * Feature flags en el cliente.
 *
 * El layout las lee en el servidor al renderizar (cacheadas 60 s) y las entrega aqui:
 * la seccion marcada sale ya con la pagina, sin parpadeo ni otra peticion al API.
 */

import { createContext, useContext, type ReactNode } from "react";

import type { FeatureFlags } from "@/services/featureFlags.service";

const FeatureFlagsContext = createContext<FeatureFlags>({});

export function FeatureFlagsProvider({
  flags,
  children,
}: {
  flags: FeatureFlags;
  children: ReactNode;
}) {
  return <FeatureFlagsContext.Provider value={flags}>{children}</FeatureFlagsContext.Provider>;
}

/**
 * Si la flag esta encendida en este entorno. Una que no existe en la tabla cuenta como
 * apagada: lo nuevo nace oculto hasta que alguien lo enciende.
 */
export function useFeatureFlag(name: string): boolean {
  return useContext(FeatureFlagsContext)[name] === true;
}
