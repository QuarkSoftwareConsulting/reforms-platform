import { useTranslations } from "next-intl";

import { Seal } from "@/components/ui/Card";
import type { ClientContact } from "@/types/api";

/**
 * Datos del cliente ya desbloqueados. Solo se renderiza con `contact` no nulo.
 *
 * Es el unico sitio del explorador donde aparecen el nombre y el telefono
 * reales, y solo llega relleno tras una compra pagada.
 */
export function ContactPanel({ contact }: { contact: ClientContact }) {
  const t = useTranslations("lead");

  return (
    <div className="space-y-4 rounded-card border-[1.5px] border-brand bg-brand-soft p-6">
      <Seal>{t("contactUnlocked")}</Seal>

      <dl className="space-y-3">
        <div>
          <dt className="text-[12.5px] font-semibold uppercase tracking-[0.7px] text-brand">
            {t("clientName")}
          </dt>
          <dd className="text-card-title font-semibold text-ink">{contact.name}</dd>
        </div>
        <div>
          <dt className="text-[12.5px] font-semibold uppercase tracking-[0.7px] text-brand">
            {t("clientPhone")}
          </dt>
          <dd className="text-card-title">
            <a href={`tel:${contact.phone}`} className="font-bold text-brand hover:underline">
              {contact.phone}
            </a>
          </dd>
        </div>
        {contact.email && (
          <div>
            <dt className="text-[12.5px] font-semibold uppercase tracking-[0.7px] text-brand">
              {t("clientEmail")}
            </dt>
            <dd className="break-all text-[15px]">
              <a href={`mailto:${contact.email}`} className="text-brand hover:underline">
                {contact.email}
              </a>
            </dd>
          </div>
        )}
      </dl>

      <a
        href={`tel:${contact.phone}`}
        className="inline-flex min-h-12 w-full items-center justify-center rounded-control bg-brand px-[26px] text-base font-semibold text-surface transition-colors hover:bg-brand-hover"
      >
        {t("callClient")}
      </a>
    </div>
  );
}
