"use client";

import Image from "next/image";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { Container } from "@/components/ui/Container";
import { cn } from "@/helpers/cn";
import { useAuth } from "@/hooks/useAuth";
import { splitBrand } from "@/helpers/brand";
import { ISOTYPE_PATH } from "@/helpers/site";
import { path, type AppLocale } from "@/i18n/routing";

/**
 * Marca de la cabecera: isotipo + logotipo de texto.
 *
 * El lockup completo no sirve aqui — lleva fondo blanco opaco y el "Voy a" en
 * azul oscuro, que sobre el gris tinta de la cabecera no contrasta. Se usa el
 * isotipo recortado y el nombre se compone con los colores de marca.
 */
function Wordmark({ locale }: { locale: AppLocale }) {
  const t = useTranslations("common");
  const { lead, tail } = splitBrand(t("appName"));

  return (
    <Link
      href={path(locale, "home") || "/"}
      className="flex items-center gap-2.5 text-xl font-bold tracking-[-0.4px] text-surface"
    >
      <Image src={ISOTYPE_PATH} alt="" width={34} height={34} priority className="shrink-0" />
      <span>
        {lead} <span className="text-accent">{tail}</span>
      </span>
    </Link>
  );
}

const NAV_LINK = "text-[14.5px] text-line-strong transition-colors hover:text-accent";

export function SiteHeader() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("nav");
  const [menuOpen, setMenuOpen] = useState(false);
  const auth = useAuth();

  const close = () => setMenuOpen(false);

  // Para quien no ha entrado, la navegacion apunta a las secciones del home:
  // son paginas que existen, a diferencia de /precios o /ayuda.
  const publicLinks = [
    { href: `${path(locale, "home") || "/"}#como-validamos`, label: t("howWeValidate") },
    { href: `${path(locale, "home") || "/"}#precios`, label: t("pricing") },
    { href: path(locale, "publish"), label: t("publish") },
  ];

  const privateLinks = [
    { href: path(locale, "projects"), label: t("projects") },
    { href: path(locale, "myContacts"), label: t("myContacts") },
    { href: path(locale, "profile"), label: t("profile") },
    ...(auth.me?.role === "admin" ? [{ href: path(locale, "admin"), label: t("admin") }] : []),
  ];

  const links = auth.isAuthenticated ? privateLinks : publicLinks;

  return (
    <header className="sticky top-0 z-20 bg-ink">
      <Container className="flex h-16 items-center justify-between gap-6">
        <div className="flex items-center gap-8">
          <Wordmark locale={locale} />
          <nav className="hidden items-center gap-6 lg:flex">
            {links.map((link) => (
              <Link key={link.href} href={link.href} className={NAV_LINK}>
                {link.label}
              </Link>
            ))}
          </nav>
        </div>

        <div className="hidden items-center gap-3.5 lg:flex">
          {auth.isAuthenticated ? (
            <button
              type="button"
              onClick={() => void auth.logout()}
              className="text-[14.5px] font-medium text-surface hover:text-accent"
            >
              {t("logout")}
            </button>
          ) : (
            <>
              <Link
                href={path(locale, "login")}
                className="text-[14.5px] font-medium text-surface hover:text-accent"
              >
                {t("login")}
              </Link>
              <Link
                href={path(locale, "register")}
                className="rounded-lg bg-accent px-[18px] py-2.5 text-[14.5px] font-semibold text-ink transition-colors hover:bg-accent-hover"
              >
                {t("register")}
              </Link>
            </>
          )}
        </div>

        <button
          type="button"
          onClick={() => setMenuOpen((open) => !open)}
          aria-expanded={menuOpen}
          aria-controls="site-menu"
          className="-mr-2 flex size-12 items-center justify-center text-surface lg:hidden"
        >
          <span className="sr-only">{t("menu")}</span>
          <svg viewBox="0 0 24 24" aria-hidden className="size-6 stroke-current" fill="none" strokeWidth={2}>
            {menuOpen ? (
              <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
            ) : (
              <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
            )}
          </svg>
        </button>
      </Container>

      <div
        id="site-menu"
        hidden={!menuOpen}
        className={cn("border-t border-white/10 bg-ink lg:hidden")}
      >
        <Container className="flex flex-col gap-1 py-3">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={close}
              className="flex min-h-12 items-center text-[15px] text-line-strong"
            >
              {link.label}
            </Link>
          ))}
          {auth.isAuthenticated ? (
            <button
              type="button"
              onClick={() => {
                close();
                void auth.logout();
              }}
              className="flex min-h-12 items-center text-left text-[15px] font-medium text-surface"
            >
              {t("logout")}
            </button>
          ) : (
            <>
              <Link
                href={path(locale, "login")}
                onClick={close}
                className="flex min-h-12 items-center text-[15px] font-medium text-surface"
              >
                {t("login")}
              </Link>
              <Link
                href={path(locale, "register")}
                onClick={close}
                className="mt-2 flex min-h-12 items-center justify-center rounded-lg bg-accent px-[18px] text-[15px] font-semibold text-ink"
              >
                {t("register")}
              </Link>
            </>
          )}
        </Container>
      </div>
    </header>
  );
}
