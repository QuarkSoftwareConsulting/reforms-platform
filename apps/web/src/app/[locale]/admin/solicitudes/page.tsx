import { setRequestLocale } from "next-intl/server";

import { AdminLeads } from "@/components/features/AdminLeads";
import { isAppLocale, type AppLocale } from "@/i18n/routing";

import { adminSectionMetadata } from "../metadata";

export function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
  return adminSectionMetadata(params, "leads");
}

export default async function AdminLeadsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  setRequestLocale((isAppLocale(raw) ? raw : "es") as AppLocale);
  return <AdminLeads />;
}
