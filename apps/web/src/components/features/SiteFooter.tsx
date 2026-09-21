import Image from "next/image";
import Link from "next/link";
import { getLocale, getTranslations } from "next-intl/server";

import { Container } from "@/components/ui/Container";
import { splitBrand } from "@/helpers/brand";
import { ISOTYPE_PATH } from "@/helpers/site";
import { path, type AppLocale } from "@/i18n/routing";

/**
 * Pie del sitio.
 *
 * Solo enlaza rutas que existen. Aviso legal, privacidad, precios y ayuda son
 * paginas del diseno que todavia no estan construidas: ponerlas aqui como
 * enlaces muertos seria peor que no ponerlas.
 */
export async function SiteFooter() {
  const locale = (await getLocale()) as AppLocale;
  const t = await getTranslations("footer");
  const tCommon = await getTranslations("common");
  const tNav = await getTranslations("nav");

  const { lead, tail } = splitBrand(tCommon("appName"));

  const links = [
    { href: path(locale, "publish"), label: tNav("publish") },
    { href: path(locale, "register"), label: tNav("register") },
    { href: `${path(locale, "home") || "/"}#como-validamos`, label: tNav("howWeValidate") },
    { href: `${path(locale, "home") || "/"}#precios`, label: tNav("pricing") },
  ];

  return (
    <footer className="bg-ink py-10 text-line-strong">
      <Container className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="flex items-center gap-2.5 text-xl font-bold tracking-[-0.4px] text-surface">
            <Image src={ISOTYPE_PATH} alt="" width={30} height={30} className="shrink-0" />
            <span>
              {lead} <span className="text-accent">{tail}</span>
            </span>
          </p>
          <p className="mt-1 text-[14.5px]">{t("tagline")}</p>
        </div>

        <nav className="flex flex-wrap gap-x-6 gap-y-2">
          {links.map((link) => (
            <Link key={link.href} href={link.href} className="text-[14.5px] hover:text-accent">
              {link.label}
            </Link>
          ))}
        </nav>
      </Container>
    </footer>
  );
}
