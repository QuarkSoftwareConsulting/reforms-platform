"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";

import { Alert } from "@/components/ui/Alert";
import { path, type AppLocale } from "@/i18n/routing";
import type { Verification } from "@/types/api";

/**
 * Estado del alta en "Solicitudes en tu zona" (F02). Aprobado no muestra nada: el
 * aviso solo aparece mientras el profesional todavia no puede comprar por ello.
 */
export function VerificationBanner({ verification }: { verification: Verification | null }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("profile.verification");
  if (verification === null || verification.status === "approved") return null;

  if (verification.status === "rejected") {
    return <Alert tone="error" title={t("rejectedTitle")}>{t("rejectedBody")}</Alert>;
  }
  const pending = verification.status === "pending";
  return (
    <Alert
      tone={pending ? "info" : "warning"}
      title={t(pending ? "pendingTitle" : "incompleteTitle")}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span>{t(pending ? "bannerPending" : "bannerIncomplete")}</span>
        {!pending && (
          <Link href={path(locale, "profile")} className="font-semibold text-brand hover:underline">
            {t("bannerCta")}
          </Link>
        )}
      </div>
    </Alert>
  );
}
