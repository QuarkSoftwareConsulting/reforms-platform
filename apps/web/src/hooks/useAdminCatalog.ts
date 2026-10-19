"use client";

/** Estado del catalogo en el panel de admin: carga, crea, edita y borra. */

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { useApiError } from "@/hooks/useApiError";
import {
  adminService,
  type CatalogNames,
  type CategoryPayload,
  type NewCategoryPayload,
  type ServicePayload,
} from "@/services/admin.service";
import type { AdminCatalogCategory, Locale } from "@/types/api";

export interface AdminCatalogState {
  categories: AdminCatalogCategory[];
  loading: boolean;
  /** Que accion esta en curso (`create`, `category:<id>`, `service:<id>`...), para su boton. */
  pending: string | null;
  error: string | null;
  notice: string | null;
  createCategory: (payload: NewCategoryPayload) => Promise<boolean>;
  updateCategory: (categoryId: string, payload: CategoryPayload) => Promise<boolean>;
  deleteCategory: (categoryId: string) => Promise<boolean>;
  createService: (categoryId: string, payload: CatalogNames) => Promise<boolean>;
  updateService: (categoryId: string, serviceId: string, payload: ServicePayload) => Promise<boolean>;
  deleteService: (categoryId: string, serviceId: string) => Promise<boolean>;
}

function byCatalogOrder(a: AdminCatalogCategory, b: AdminCatalogCategory): number {
  return a.sort_order - b.sort_order || a.name_es.localeCompare(b.name_es);
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

  useEffect(() => {
    let cancelled = false;
    adminService
      .catalog(locale)
      .then((items) => {
        if (!cancelled) setCategories(items);
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

  const run = useCallback(
    async (key: string, action: () => Promise<void>, message: string): Promise<boolean> => {
      setPending(key);
      setError(null);
      setNotice(null);
      try {
        await action();
        setNotice(message);
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
    deleteService: (categoryId, serviceId) =>
      run(
        `service:${serviceId}`,
        async () => {
          await adminService.deleteService(categoryId, serviceId, locale);
          setCategories((current) =>
            current.map((item) =>
              item.id === categoryId
                ? { ...item, services: item.services.filter((s) => s.id !== serviceId) }
                : item,
            ),
          );
        },
        t("deleted"),
      ),
  };
}
