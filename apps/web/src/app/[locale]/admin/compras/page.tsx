import { setRequestLocale } from "next-intl/server";

import { AdminPurchases } from "@/components/features/AdminPurchases";
import { isAppLocale, type AppLocale } from "@/i18n/routing";

import { adminSectionMetadata } from "../metadata";

export function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
  return adminSectionMetadata(params, "purchases");
}

export default async function AdminPurchasesPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  setRequestLocale((isAppLocale(raw) ? raw : "es") as AppLocale);
  return <AdminPurchases />;
}
