import { setRequestLocale } from "next-intl/server";

import { AdminCatalog } from "@/components/features/AdminCatalog";
import { isAppLocale, type AppLocale } from "@/i18n/routing";

import { adminSectionMetadata } from "../metadata";

export function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
  return adminSectionMetadata(params, "catalog");
}

export default async function AdminCatalogPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  setRequestLocale((isAppLocale(raw) ? raw : "es") as AppLocale);
  return <AdminCatalog />;
}
