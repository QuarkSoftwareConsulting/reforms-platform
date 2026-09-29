"use client";

import { useLocale, useTranslations } from "next-intl";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/helpers/date";
import type { AppLocale } from "@/i18n/routing";
import type { Verification } from "@/types/api";

/**
 * Estado del alta (F02). Mientras falten datos o documentos lista que falta; con
 * todo completo ofrece enviarla a revision. En revision se pueden ver solicitudes,
 * pero comprar solo cuando el admin la apruebe.
 */
export function VerificationCard({ verification, onSubmit, submitting }: {
  verification: Verification;
  onSubmit: () => void;
  submitting: boolean;
}) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("profile.verification");

  if (verification.status === "approved") {
    return <Alert tone="success" title={t("approvedTitle")}>{t("approvedBody")}</Alert>;
  }
  if (verification.status === "pending") {
    return (
      <Alert tone="info" title={t("pendingTitle")}>
        {t("pendingBody", {
          date: verification.submitted_at ? formatDate(verification.submitted_at, locale) : "",
        })}
      </Alert>
    );
  }
  if (verification.status === "rejected") {
    return (
      <Alert tone="error" title={t("rejectedTitle")}>
        <p>{t("rejectedBody")}</p>
        {verification.rejection_reason && (
          <p className="mt-2">
            <strong>{t("reason")}:</strong> {verification.rejection_reason}
          </p>
        )}
      </Alert>
    );
  }

  const ready = verification.missing.length === 0;
  return (
    <Alert tone="warning" title={t("incompleteTitle")}>
      <div className="space-y-3">
        <p>{ready ? t("readyBody") : t("incompleteBody")}</p>
        {!ready && (
          <ul className="list-inside list-disc">
            {verification.missing.map((item) => (
              <li key={item}>{t(`missing.${item}`)}</li>
            ))}
          </ul>
        )}
        <Button
          type="button"
          variant="accent"
          disabled={!ready}
          loading={submitting}
          onClick={onSubmit}
        >
          {t("submit")}
        </Button>
      </div>
    </Alert>
  );
}
