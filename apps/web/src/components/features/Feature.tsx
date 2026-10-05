"use client";

import type { ReactNode } from "react";

import { useFeatureFlag } from "@/hooks/useFeatureFlag";

/**
 * Muestra su contenido solo con la flag encendida; si no, `fallback` (nada, por defecto).
 *
 * ```tsx
 * <Feature name="admin.reports">
 *   <NavLink href="/admin/informes">Informes</NavLink>
 * </Feature>
 * ```
 *
 * Es una comodidad de interfaz, no un control de acceso: lo que este detras debe seguir
 * protegido en el backend.
 */
export function Feature({
  name,
  children,
  fallback = null,
}: {
  name: string;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  return useFeatureFlag(name) ? children : fallback;
}
