import { setRequestLocale } from "next-intl/server";

import { AdminUsers } from "@/components/features/AdminUsers";
import { AdminVerificationQueue } from "@/components/features/AdminVerificationQueue";
import { isAppLocale, type AppLocale } from "@/i18n/routing";

import { adminSectionMetadata } from "../metadata";

export function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
  return adminSectionMetadata(params, "professionals");
}

export default async function AdminProfessionalsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  setRequestLocale((isAppLocale(raw) ? raw : "es") as AppLocale);
  return (
    <div className="space-y-8">
      <AdminVerificationQueue />
      <AdminUsers />
    </div>
  );
}
