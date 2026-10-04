import { setRequestLocale } from "next-intl/server";

import { AdminDashboard } from "@/components/features/AdminDashboard";
import { isAppLocale, type AppLocale } from "@/i18n/routing";

import { adminSectionMetadata } from "./metadata";

export function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
  return adminSectionMetadata(params, "overview");
}

export default async function AdminOverviewPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  setRequestLocale((isAppLocale(raw) ? raw : "es") as AppLocale);
  return <AdminDashboard />;
}
