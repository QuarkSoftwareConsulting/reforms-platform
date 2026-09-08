"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";

import { Button } from "@/components/ui/Button";
import { useAuth } from "@/hooks/useAuth";
import { path, type AppLocale } from "@/i18n/routing";

export function SiteHeader() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("nav");
  const tCommon = useTranslations("common");
  const auth = useAuth();

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
        <Link href={path(locale, "home") || "/"} className="text-lg font-bold text-brand-700">
          {tCommon("appName")}
        </Link>

        <nav className="flex items-center gap-1 sm:gap-3">
          {auth.isAuthenticated ? (
            <>
              <Link
                href={path(locale, "projects")}
                className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                {t("projects")}
              </Link>
              {auth.me?.role === "admin" && (
                <Link
                  href={path(locale, "admin")}
                  className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
                >
                  {t("admin")}
                </Link>
              )}
              <Link
                href={path(locale, "myContacts")}
                className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                {t("myContacts")}
              </Link>
              <Link
                href={path(locale, "profile")}
                className="hidden rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 sm:block"
              >
                {t("profile")}
              </Link>
              <Button variant="ghost" size="sm" onClick={() => void auth.logout()}>
                {t("logout")}
              </Button>
            </>
          ) : (
            <>
              <Link
                href={path(locale, "login")}
                className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                {t("login")}
              </Link>
              <Link href={path(locale, "publish")}>
                <Button size="sm">{t("publish")}</Button>
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
