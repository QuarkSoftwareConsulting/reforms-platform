"use client";

/** Estado del catalogo en el panel de admin: carga, crea, edita y borra. */

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { CATALOG_TAG } from "@/helpers/cacheTags";
import { useApiError } from "@/hooks/useApiError";
import {
  adminService,
  type CatalogNames,
  type CategoryPayload,
  type NewCategoryPayload,
  type ServicePayload,
} from "@/services/admin.service";
import { revalidationService } from "@/services/revalidation.service";
import type { AdminCatalogCategory, Locale } from "@/types/api";

export interface AdminCatalogState {
  categories: AdminCatalogCategory[];
  loading: boolean;
  /** Que accion esta en curso (`create`, `category:<id>`, `service:<id>`...), para su boton. */
  pending: string | null;
  error: string | null;
  notice: string | null;
  /** Categorias cuyos servicios se estan pidiendo ahora mismo. */
  loadingServices: ReadonlySet<string>;
  /** Pide los servicios de una categoria si aun no los tiene; el error va a `error`. */
  loadServices: (categoryId: string) => Promise<void>;
  createCategory: (payload: NewCategoryPayload) => Promise<boolean>;
  updateCategory: (categoryId: string, payload: CategoryPayload) => Promise<boolean>;
  deleteCategory: (categoryId: string) => Promise<boolean>;
  createService: (categoryId: string, payload: CatalogNames) => Promise<boolean>;
  updateService: (categoryId: string, serviceId: string, payload: ServicePayload) => Promise<boolean>;
  deleteService: (categoryId: string, serviceId: string) => Promise<boolean>;
  /** Sube la foto al bucket y devuelve su clave; se guarda al guardar el servicio. */
  uploadServiceImage: (categoryId: string, serviceId: string, file: File) => Promise<string | null>;
}

/** Primero las activas, despues por nombre: lo desactivado queda al final del panel. */
function byCatalogOrder(a: AdminCatalogCategory, b: AdminCatalogCategory): number {
  return Number(b.active) - Number(a.active) || a.name_es.localeCompare(b.name_es, "es");
}

export function useAdminCatalog(): AdminCatalogState {
  const locale = useLocale() as Locale;
  const t = useTranslations("admin.catalog");
  const translateError = useApiError();
  const [categories, setCategories] = useState<AdminCatalogCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loadingServices, setLoadingServices] = useState<ReadonlySet<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    adminService
      .catalog(locale)
      .then((items) => {
        if (!cancelled) setCategories([...items].sort(byCatalogOrder));
      })
      .catch((caught: unknown) => {
        if (!cancelled) setError(translateError(caught));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [locale, translateError]);

  /** Sustituye (o anade) la categoria que devuelve el API, sin recargar todo. */
  const upsert = useCallback((category: AdminCatalogCategory) => {
    setCategories((current) =>
      [...current.filter((item) => item.id !== category.id), category].sort(byCatalogOrder),
    );
  }, []);

  const loadServices = useCallback(
    async (categoryId: string) => {
      setLoadingServices((current) => new Set(current).add(categoryId));
      setError(null);
      try {
        const services = await adminService.categoryServices(categoryId, locale);
        setCategories((current) =>
          current.map((item) =>
            item.id === categoryId ? { ...item, services, services_count: services.length } : item,
          ),
        );
      } catch (caught) {
        setError(translateError(caught));
      } finally {
        setLoadingServices((current) => {
          const next = new Set(current);
          next.delete(categoryId);
          return next;
        });
      }
    },
    [locale, translateError],
  );

  const run = useCallback(
    async (key: string, action: () => Promise<void>, message: string): Promise<boolean> => {
      setPending(key);
      setError(null);
      setNotice(null);
      try {
        await action();
        setNotice(message);
        // La landing y el formulario publico son estaticos: se regeneran con el cambio.
        void revalidationService.revalidate([CATALOG_TAG]);
        return true;
      } catch (caught) {
        // "En uso" llega como CATALOG_ITEM_IN_USE: el texto ya dice que se desactive.
        setError(translateError(caught));
        return false;
      } finally {
        setPending(null);
      }
    },
    [translateError],
  );

  return {
    categories,
    loading,
    pending,
    error,
    notice,
    loadingServices,
    loadServices,
    createCategory: (payload) =>
      run("create", async () => upsert(await adminService.createCategory(payload, locale)), t("created")),
    updateCategory: (categoryId, payload) =>
      run(
        `category:${categoryId}`,
        async () => upsert(await adminService.updateCategory(categoryId, payload, locale)),
        t("saved"),
      ),
    deleteCategory: (categoryId) =>
      run(
        `category:${categoryId}`,
        async () => {
          await adminService.deleteCategory(categoryId, locale);
          setCategories((current) => current.filter((item) => item.id !== categoryId));
        },
        t("deleted"),
      ),
    createService: (categoryId, payload) =>
      run(
        `new-service:${categoryId}`,
        async () => upsert(await adminService.createService(categoryId, payload, locale)),
        t("serviceAdded"),
      ),
    updateService: (categoryId, serviceId, payload) =>
      run(
        `service:${serviceId}`,
        async () =>
          upsert(await adminService.updateService(categoryId, serviceId, payload, locale)),
        t("saved"),
      ),
    uploadServiceImage: async (categoryId, serviceId, file) => {
      setPending(`image:${serviceId}`);
      setError(null);
      try {
        const presigned = await adminService.requestServiceImageUpload(
          categoryId,
          serviceId,
          file,
          locale,
        );
        const response = await fetch(presigned.upload_url, {
          method: presigned.method,
          headers: presigned.headers,
          body: file,
        });
        if (!response.ok) throw new Error(`Fallo la subida de ${file.name}`);
        return presigned.storage_key;
      } catch (caught) {
        setError(translateError(caught));
        return null;
      } finally {
        setPending(null);
      }
    },
    deleteService: (categoryId, serviceId) =>
      run(
        `service:${serviceId}`,
        async () => {
          await adminService.deleteService(categoryId, serviceId, locale);
          setCategories((current) =>
            current.map((item) =>
              item.id === categoryId
                ? {
                    ...item,
                    services: item.services?.filter((s) => s.id !== serviceId) ?? null,
                    services_count: Math.max(0, item.services_count - 1),
                  }
                : item,
            ),
          );
        },
        t("deleted"),
      ),
  };
}
