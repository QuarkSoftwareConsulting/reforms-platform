"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { TextAreaField } from "@/components/ui/Field";
import { formatMoney } from "@/helpers/currency";
import { formatDate, formatDateTime } from "@/helpers/date";
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
  const tProfile = useTranslations("profile");
  const queue = useVerificationQueue();
  const [reason, setReason] = useState("");
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
        <div className="space-y-4">
          <dl className="grid gap-3 text-[14.5px] sm:grid-cols-2">
            {(
              [
                [tProfile("legalNameLabel"), dossier.professional.legal_name],
                [tProfile("taxIdLabel"), dossier.professional.tax_id],
                [
                  tProfile("typeLabel"),
                  dossier.professional.professional_type
                    ? tProfile(`types.${dossier.professional.professional_type}.title`)
                    : null,
                ],
                [tProfile("addressLabel"), dossier.professional.address],
                [tProfile("businessNameLabel"), dossier.professional.business_name],
                [tProfile("phoneLabel"), dossier.professional.phone],
                [t("email"), dossier.email],
                [tProfile("postalCodeLabel"), dossier.professional.postal_code],
              ] as const
            ).map(([label, value]) => (
              <div key={label}>
                <dt className="text-[11px] uppercase tracking-[0.7px] text-muted">{label}</dt>
                <dd className="font-semibold text-ink">{value ?? "—"}</dd>
              </div>
            ))}
          </dl>

          <div className="space-y-2">
            <p className="text-[15px] font-semibold text-ink">{tProfile("documentsLabel")}</p>
            {dossier.documents.length === 0 ? (
              <p className="text-secondary">{t("noDocuments")}</p>
            ) : (
              <ul className="space-y-1">
                {dossier.documents.map((document) => (
                  <li key={document.id}>
                    <a
                      href={document.download_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-semibold text-brand hover:underline"
                    >
                      {document.filename}
                    </a>{" "}
                    <span className="text-help text-muted">
                      · {tProfile(`documentKinds.${document.kind}`)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-help text-muted">{t("linksExpire")}</p>
          </div>

          <div className="space-y-1">
            <p className="text-[15px] font-semibold text-ink">{t("history")}</p>
            <ul className="text-help text-secondary">
              {dossier.events.map((event) => (
                <li key={`${event.created_at}-${event.to_status}`}>
                  {formatDateTime(event.created_at, locale)} ·{" "}
                  {t(`status.${event.to_status}`)}
                  {event.note && ` · ${event.note}`}
                </li>
              ))}
            </ul>
          </div>

          <TextAreaField
            label={t("reasonLabel")}
            hint={t("reasonHint")}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            maxLength={1000}
          />

          <div className="flex flex-wrap gap-3">
            <Button
              type="button"
              loading={queue.deciding}
              onClick={() => void queue.approve()}
            >
              {t("approve")}
            </Button>
            <Button
              type="button"
              variant="secondary"
              loading={queue.deciding}
              disabled={reason.trim().length < 3}
              onClick={() => void queue.reject(reason.trim()).then(() => setReason(""))}
            >
              {t("reject")}
            </Button>
            <Button type="button" variant="text" onClick={queue.close}>
              {t("back")}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
