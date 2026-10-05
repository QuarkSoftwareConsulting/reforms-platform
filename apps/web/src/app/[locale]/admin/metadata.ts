import { getTranslations } from "next-intl/server";

import type { AdminSection } from "@/helpers/adminSections";

/** Titulo de la pestana del navegador: "Solicitudes · Administracion". */
export async function adminSectionMetadata(
  params: Promise<{ locale: string }>,
  section: AdminSection,
) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "admin" });
  return { title: `${t(`nav.${section}`)} · ${t("title")}` };
}
