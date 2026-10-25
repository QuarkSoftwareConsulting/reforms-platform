/**
 * Regenera las paginas publicas tras un cambio del admin (catalogo, mensualidad).
 *
 * Llama a una ruta de Next (`/api/revalidate`), no al API: la cache de las paginas vive
 * en el servidor de Next. La ruta comprueba con el API que quien llama es admin.
 */

import type { CacheTag } from "@/helpers/cacheTags";
import { currentToken } from "@/services/api";

export const revalidationService = {
  /** Mejor esfuerzo: si falla, la pagina se regenera igual en el respaldo diario. */
  async revalidate(tags: CacheTag[]): Promise<void> {
    const token = await currentToken();
    if (!token) return;
    try {
      await fetch("/api/revalidate", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ tags }),
      });
    } catch {
      // Sin red o con la ruta caida: la regeneracion diaria lo corrige.
    }
  },
};
