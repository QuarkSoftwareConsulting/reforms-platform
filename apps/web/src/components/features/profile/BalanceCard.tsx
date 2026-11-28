"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";

import { Card } from "@/components/ui/Card";
import { formatMoney } from "@/helpers/currency";
import { path, type AppLocale } from "@/i18n/routing";
import type { Account } from "@/types/api";

/**
 * Saldo en el perfil. El profesional lo buscaba aqui y solo estaba en la mensualidad;
 * se muestra tambien a 0 y con la cuenta inactiva, porque el saldo se conserva.
 */
export function BalanceCard({ account }: { account: Account }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("subscription");

  return (
    <Card className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <p className="text-[13px] text-secondary">{t("balanceLabel")}</p>
        <p className="text-[24px] font-bold text-brand">{formatMoney(account.balance, locale)}</p>
      </div>
      <Link
        href={path(locale, "subscription")}
        className="font-semibold text-brand hover:underline"
      >
        {t("bannerManage")}
      </Link>
    </Card>
  );
}
