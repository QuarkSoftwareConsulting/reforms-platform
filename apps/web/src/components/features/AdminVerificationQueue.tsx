"use client";

import { useLocale, useTranslations } from "next-intl";

import { VerificationDossierView } from "@/components/features/VerificationDossierView";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { formatMoney } from "@/helpers/currency";
import { formatDate } from "@/helpers/date";
import { useVerificationQueue } from "@/hooks/useVerificationQueue";
import type { AppLocale } from "@/i18n/routing";

/**
 * Cola de validacion de altas (F02). El admin revisa datos y documentos y aprueba
 * o rechaza. Rechazar reembolsa el primer cobro y cancela la recarga del
 * profesional, por eso pide un motivo y lo deja en la auditoria.
 */
export function AdminVerificationQueue() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("admin.verification");
  const queue = useVerificationQueue();
  const dossier = queue.dossier;

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="text-h2 font-bold text-ink">{t("title")}</h2>
        <p className="text-help text-muted">{t("subtitle")}</p>
      </div>

      {queue.error && <Alert tone="error">{queue.error}</Alert>}
      {queue.lastRejection && (
        <Alert tone="success">
          {queue.lastRejection.refunded
            ? t("rejectedRefunded", { amount: formatMoney(queue.lastRejection.refunded, locale) })
            : t("rejectedNothingToRefund")}
        </Alert>
      )}

      {!dossier && (
        <>
          {queue.loading ? null : queue.queue.length === 0 ? (
            <p className="text-secondary">{t("empty")}</p>
          ) : (
            <ul className="divide-y divide-divider rounded-option border border-line">
              {queue.queue.map((professional) => (
                <li
                  key={professional.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                >
                  <span>
                    <span className="block font-semibold text-ink">
                      {professional.legal_name ?? professional.business_name}
                    </span>
                    <span className="block text-help text-muted">
                      {professional.business_name} · {professional.city ?? professional.postal_code}
                      {professional.submitted_at &&
                        ` · ${t("submittedOn", { date: formatDate(professional.submitted_at, locale) })}`}
                    </span>
                  </span>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => void queue.open(professional.id)}
                  >
                    {t("review")}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {dossier && (
        <VerificationDossierView
          dossier={dossier}
          deciding={queue.deciding}
          onApprove={queue.approve}
          onReject={queue.reject}
          onBack={queue.close}
        />
      )}
    </Card>
  );
}
