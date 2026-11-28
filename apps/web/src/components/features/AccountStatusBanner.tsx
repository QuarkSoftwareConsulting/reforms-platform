"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";

import { Alert } from "@/components/ui/Alert";
import { formatMoney } from "@/helpers/currency";
import { path, type AppLocale } from "@/i18n/routing";
import type { Account } from "@/types/api";

/**
 * Estado de la cuenta en "Solicitudes en tu zona".
 *
 * Lo pide el negocio: una cuenta inactiva puede ver las solicitudes pero no
 * comprarlas, y el profesional tiene que saberlo antes de intentar comprar. El saldo
 * se ve en todos los estados, tambien a 0: se conserva aunque la recarga caduque.
 */
export function AccountStatusBanner({ account }: { account: Account | null }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("subscription");
  const href = path(locale, "subscription");

  if (account?.is_active && account.debt && account.debt.amount_cents > 0) {
    return (
      <Alert tone="warning">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span>
            <span className="block">
              {t("bannerDebt", { debt: formatMoney(account.debt, locale) })}
            </span>
            <span className="block font-semibold">
              {t("bannerBalance", { balance: formatMoney(account.balance, locale) })}
            </span>
          </span>
          <Link href={href} className="font-semibold text-brand hover:underline">
            {t("bannerManage")}
          </Link>
        </div>
      </Alert>
    );
  }

  if (account?.is_active) {
    return (
      <Alert tone="info">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span>{t("bannerActive", { balance: formatMoney(account.balance, locale) })}</span>
          <Link href={href} className="font-semibold text-brand hover:underline">
            {t("bannerManage")}
          </Link>
        </div>
      </Alert>
    );
  }

  return (
    <Alert tone="warning" title={t(`status.${account?.status ?? "none"}`)}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span>
          <span className="block">{t("bannerInactive")}</span>
          {account && (
            <span className="block font-semibold">
              {t("bannerBalance", { balance: formatMoney(account.balance, locale) })}
            </span>
          )}
        </span>
        <Link href={href} className="font-semibold text-brand hover:underline">
          {t("bannerCta")}
        </Link>
      </div>
    </Alert>
  );
}
