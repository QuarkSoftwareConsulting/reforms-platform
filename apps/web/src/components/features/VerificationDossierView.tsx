"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { TextAreaField } from "@/components/ui/Field";
import { formatDateTime } from "@/helpers/date";
import type { AppLocale } from "@/i18n/routing";
import type { VerificationDossier } from "@/types/api";

interface VerificationDossierViewProps {
  dossier: VerificationDossier;
  deciding: boolean;
  onApprove: () => Promise<void>;
  onReject: (reason: string) => Promise<void>;
  onBack: () => void;
}

/**
 * Expediente de un alta: datos, documentos (URLs firmadas) e historial. Aprobar y
 * rechazar solo aparecen con el alta en revision; el backend lo exige igualmente.
 */
export function VerificationDossierView({
  dossier,
  deciding,
  onApprove,
  onReject,
  onBack,
}: VerificationDossierViewProps) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("admin.verification");
  const tProfile = useTranslations("profile");
  const [reason, setReason] = useState("");
  const pending = dossier.professional.verification.status === "pending";

  return (
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
              {formatDateTime(event.created_at, locale)} · {t(`status.${event.to_status}`)}
              {event.note && ` · ${event.note}`}
            </li>
          ))}
        </ul>
      </div>

      {pending && (
        <TextAreaField
          label={t("reasonLabel")}
          hint={t("reasonHint")}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          maxLength={1000}
        />
      )}

      <div className="flex flex-wrap gap-3">
        {pending && (
          <>
            <Button type="button" loading={deciding} onClick={() => void onApprove()}>
              {t("approve")}
            </Button>
            <Button
              type="button"
              variant="secondary"
              loading={deciding}
              disabled={reason.trim().length < 3}
              onClick={() => void onReject(reason.trim()).then(() => setReason(""))}
            >
              {t("reject")}
            </Button>
          </>
        )}
        <Button type="button" variant="text" onClick={onBack}>
          {t("back")}
        </Button>
      </div>
    </div>
  );
}
