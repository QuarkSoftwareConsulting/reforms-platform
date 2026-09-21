import Link from "next/link";
import { getTranslations } from "next-intl/server";

export default async function NotFound() {
  const t = await getTranslations("common");
  return (
    <div className="mx-auto max-w-md space-y-4 py-16 text-center">
      <p className="text-[64px] font-extrabold leading-none text-line">404</p>
      <h1 className="text-h2 font-bold text-ink">{t("appName")}</h1>
      <Link href="/" className="inline-block font-semibold text-brand underline underline-offset-4 hover:text-brand-hover">
        ← {t("close")}
      </Link>
    </div>
  );
}
