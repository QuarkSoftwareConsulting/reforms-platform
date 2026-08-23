import { useTranslations } from "next-intl";

import { Alert } from "@/components/ui/Alert";
import type { ClientContact } from "@/types/api";

/** Datos del cliente ya desbloqueados. Solo se renderiza con `contact` no nulo. */
export function ContactPanel({ contact }: { contact: ClientContact }) {
  const t = useTranslations("lead");

  return (
    <div className="space-y-4 rounded-xl border border-emerald-200 bg-emerald-50 p-5">
      <Alert tone="success" className="border-0 bg-transparent px-0 py-0">
        <p className="font-semibold">{t("contactUnlocked")}</p>
      </Alert>

      <dl className="space-y-3 text-sm">
        <div>
          <dt className="font-medium text-slate-600">{t("clientName")}</dt>
          <dd className="text-base text-slate-900">{contact.name}</dd>
        </div>
        <div>
          <dt className="font-medium text-slate-600">{t("clientPhone")}</dt>
          <dd className="text-base">
            <a
              href={`tel:${contact.phone}`}
              className="font-semibold text-brand-700 hover:underline"
            >
              {contact.phone}
            </a>
          </dd>
        </div>
        {contact.email && (
          <div>
            <dt className="font-medium text-slate-600">{t("clientEmail")}</dt>
            <dd className="text-base">
              <a href={`mailto:${contact.email}`} className="text-brand-700 hover:underline">
                {contact.email}
              </a>
            </dd>
          </div>
        )}
      </dl>

      <a
        href={`tel:${contact.phone}`}
        className="inline-flex h-11 w-full items-center justify-center rounded-lg bg-emerald-600 px-5 text-sm font-semibold text-white hover:bg-emerald-700"
      >
        {t("callClient")}
      </a>
    </div>
  );
}
