"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { cn } from "@/helpers/cn";
import { locales, type AppLocale } from "@/i18n/routing";

/**
 * Cambio de idioma discreto para la cabecera ("ES · EN").
 *
 * Las rutas son las mismas en los dos idiomas (solo cambia el prefijo), asi que basta
 * con sustituir el primer segmento. La query y el ancla se leen tras montar: con
 * `useSearchParams()` el layout entero exigiria un `<Suspense>` para prerenderizar.
 */
export function LocaleSwitch({ className, onNavigate }: { className?: string; onNavigate?: () => void }) {
  const current = useLocale() as AppLocale;
  const t = useTranslations("nav");
  const pathname = usePathname();
  const [suffix, setSuffix] = useState("");

  useEffect(() => {
    setSuffix(`${window.location.search}${window.location.hash}`);
  }, [pathname]);

  const hrefFor = (locale: AppLocale) => {
    const rest = pathname.split("/").slice(2).join("/");
    return `/${locale}${rest ? `/${rest}` : ""}${suffix}`;
  };

  return (
    <nav aria-label={t("language")} className={cn("flex items-center gap-1.5 text-[13px]", className)}>
      {locales.map((locale, index) => (
        <span key={locale} className="flex items-center gap-1.5">
          {index > 0 && (
            <span aria-hidden className="text-line-strong/50">
              ·
            </span>
          )}
          <Link
            href={hrefFor(locale)}
            lang={locale}
            hrefLang={locale}
            aria-label={t(locale === "es" ? "languageEs" : "languageEn")}
            aria-current={locale === current ? "true" : undefined}
            onClick={onNavigate}
            className={cn(
              "uppercase tracking-wide transition-colors hover:text-accent",
              locale === current ? "font-semibold text-surface" : "text-line-strong",
            )}
          >
            {locale}
          </Link>
        </span>
      ))}
    </nav>
  );
}
