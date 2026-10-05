"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";

import { ADMIN_SECTIONS } from "@/helpers/adminSections";
import { cn } from "@/helpers/cn";
import { useAdminPending } from "@/hooks/useAdminPending";
import { path, type AppLocale } from "@/i18n/routing";

/** Pestanas del panel de administracion; la activa sale de la URL. */
export function AdminNav() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("admin.nav");
  const pathname = usePathname();
  const { count } = useAdminPending();

  return (
    // En movil las pestanas no caben: se desplazan en horizontal en vez de partirse.
    <nav aria-label={t("label")} className="-mx-1 overflow-x-auto border-b border-line">
      <ul className="flex min-w-max gap-1 px-1">
        {ADMIN_SECTIONS.map((section) => {
          const href = path(locale, "admin", section.suffix);
          // "Resumen" es la raiz: con `startsWith` estaria activa en todas.
          const active = section.suffix === "" ? pathname === href : pathname.startsWith(href);
          const badge = section.key === "professionals" && count ? count : null;
          return (
            <li key={section.key}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "-mb-px flex items-center gap-2 border-b-2 px-4 py-3 text-[14.5px] transition-colors",
                  active
                    ? "border-brand font-semibold text-ink"
                    : "border-transparent text-secondary hover:text-ink",
                )}
              >
                {t(section.key)}
                {badge !== null && (
                  <span className="rounded-full bg-accent px-2 py-0.5 text-xs font-bold leading-none text-ink">
                    {badge}
                    <span className="sr-only"> {t("pending", { count: badge })}</span>
                  </span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
