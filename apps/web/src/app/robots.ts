import type { MetadataRoute } from "next";

import { absoluteUrl } from "@/helpers/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      // Zonas privadas: no aportan nada al indice y algunas muestran datos de
      // contacto ya comprados.
      disallow: ["/api/", "/es/perfil", "/en/perfil", "/es/admin", "/en/admin",
                 "/es/mis-contactos", "/en/mis-contactos"],
    },
    sitemap: absoluteUrl("/sitemap.xml"),
  };
}
