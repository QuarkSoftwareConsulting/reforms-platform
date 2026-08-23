import Link from "next/link";
import { getTranslations } from "next-intl/server";

export default async function NotFound() {
  const t = await getTranslations("common");
  return (
    <div className="mx-auto max-w-md space-y-4 py-16 text-center">
      <p className="text-6xl font-bold text-brand-200">404</p>
      <h1 className="text-2xl font-bold text-slate-900">{t("appName")}</h1>
      <Link href="/" className="inline-block font-semibold text-brand-700 hover:underline">
        ← {t("close")}
      </Link>
    </div>
  );
}
