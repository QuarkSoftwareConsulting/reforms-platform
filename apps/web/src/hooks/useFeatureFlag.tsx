"use client";

/**
 * Feature flags en el cliente.
 *
 * Las pide el navegador una vez por carga de pagina, no el layout en el servidor: el
 * layout esta en todas las paginas y la cache de las flags fijaria cada cuanto se
 * regeneran todas. A cambio, lo que va detras de una flag aparece tras esa peticion
 * (mientras tanto cuenta como apagada), asi que no se usa para contenido que deba
 * indexar Google.
 */

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { featureFlagsService, type FeatureFlags } from "@/services/featureFlags.service";

const FeatureFlagsContext = createContext<FeatureFlags>({});

export function FeatureFlagsProvider({ children }: { children: ReactNode }) {
  const [flags, setFlags] = useState<FeatureFlags>({});

  useEffect(() => {
    let active = true;
    void featureFlagsService.list().then((loaded) => {
      if (active) setFlags(loaded);
    });
    return () => {
      active = false;
    };
  }, []);

  return <FeatureFlagsContext.Provider value={flags}>{children}</FeatureFlagsContext.Provider>;
}

/**
 * Si la flag esta encendida en este entorno. Una que no existe en la tabla cuenta como
 * apagada: lo nuevo nace oculto hasta que alguien lo enciende.
 */
export function useFeatureFlag(name: string): boolean {
  return useContext(FeatureFlagsContext)[name] === true;
}
