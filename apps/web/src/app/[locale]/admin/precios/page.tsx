import { setRequestLocale } from "next-intl/server";

import { AdminPricing } from "@/components/features/AdminPricing";
import { isAppLocale, type AppLocale } from "@/i18n/routing";

import { adminSectionMetadata } from "../metadata";

export function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
  return adminSectionMetadata(params, "pricing");
}

export default async function AdminPricingPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  setRequestLocale((isAppLocale(raw) ? raw : "es") as AppLocale);
  return <AdminPricing />;
}
