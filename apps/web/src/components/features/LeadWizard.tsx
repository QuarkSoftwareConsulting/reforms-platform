"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { CategoryPicker } from "@/components/features/CategoryPicker";
import { PhotoUploader } from "@/components/features/PhotoUploader";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Panel } from "@/components/ui/Card";
import { CheckboxField, TextAreaField, TextField } from "@/components/ui/Field";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { MIN_DESCRIPTION_LENGTH } from "@/helpers/validators";
import { STEPS, useLeadForm } from "@/hooks/useLeadForm";
import { usePhotoUpload } from "@/hooks/usePhotoUpload";
import { path, type AppLocale } from "@/i18n/routing";
import type { Category } from "@/types/api";

const MAX_PROFESSIONALS = 3;

/** Apartados del resumen de la politica que se despliega bajo el consentimiento. */
const POLICY_ROWS = [
  "controller",
  "purpose",
  "legitimation",
  "recipients",
  "retention",
  "rights",
] as const;

/** Formulario de publicacion en tres pasos. Toda la logica vive en los hooks. */
export function LeadWizard({ categories }: { categories: Category[] }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("publish");
  const tCommon = useTranslations("common");
  const tValidation = useTranslations("validation");
  const form = useLeadForm();
  const upload = usePhotoUpload();
  const searchParams = useSearchParams();
  const [policyOpen, setPolicyOpen] = useState(false);

  // Permite entrar desde la landing con el oficio ya elegido (?category=slug).
  const presetSlug = searchParams.get("category");
  useEffect(() => {
    if (!presetSlug || form.values.categoryId) return;
    const match = categories.find((category) => category.slug === presetSlug);
    if (match) form.setField("categoryId", match.id);
  }, [presetSlug, categories, form]);

  const error = (field: keyof typeof form.values): string | undefined => {
    const key = form.errors[field];
    return key ? tValidation(key) : undefined;
  };

  if (form.created) {
    return (
      <Panel className="mx-auto max-w-xl p-10 text-center">
        <span
          aria-hidden
          className="mx-auto flex size-[62px] items-center justify-center rounded-full bg-accent"
        >
          <svg viewBox="0 0 24 24" className="size-8 stroke-ink" fill="none" strokeWidth={2.5}>
            <path d="M5 13l4.5 4.5L19 7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <h2 className="mt-6 text-h2 font-bold text-ink">{t("successTitle")}</h2>
        <p className="mt-3 text-[15.5px] leading-[1.6] text-secondary">
          {t("successBody", { city: form.created.city })}
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-3">
          <Button variant="secondary" onClick={form.reset}>
            {t("publishAnother")}
          </Button>
          <Link href={path(locale, "home") || "/"}>
            <Button variant="text">{tCommon("close")}</Button>
          </Link>
        </div>
      </Panel>
    );
  }

  const isLastStep = form.stepIndex === STEPS.length - 1;

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (isLastStep) {
          void form.submit(upload.storageKeys);
        } else {
          form.goNext();
        }
      }}
      className="space-y-6"
    >
      {/* El aviso de privacidad acompana los tres pasos: es la razon por la que
          el cliente se atreve a dejar el telefono. */}
      <p className="flex items-start gap-2.5 text-[14.5px] leading-[1.5] text-secondary">
        <svg viewBox="0 0 24 24" aria-hidden className="mt-0.5 size-[18px] shrink-0 fill-brand">
          <path d="M12 2a5 5 0 00-5 5v3H6a2 2 0 00-2 2v8a2 2 0 002 2h12a2 2 0 002-2v-8a2 2 0 00-2-2h-1V7a5 5 0 00-5-5zm-3 5a3 3 0 016 0v3H9V7z" />
        </svg>
        {t("lockNotice")}
      </p>

      <div className="space-y-2">
        <p className="text-[14.5px] font-semibold text-brand">
          {t("stepOf", { current: form.stepIndex + 1, total: STEPS.length })} ·{" "}
          {t(`steps.${form.step}`)}
        </p>
        <ProgressBar
          value={form.stepIndex + 1}
          max={STEPS.length}
          label={t("stepOf", { current: form.stepIndex + 1, total: STEPS.length })}
        />
      </div>

      <Panel className="space-y-6 sm:p-8">
        {form.step === "category" && (
          <CategoryPicker
            categories={categories}
            selected={form.values.categoryId ? [form.values.categoryId] : []}
            onChange={(ids) => form.setField("categoryId", ids[0] ?? "")}
            label={t("categoryLabel")}
            error={error("categoryId")}
          />
        )}

        {form.step === "details" && (
          <>
            <TextField
              label={t("titleLabel")}
              placeholder={t("titlePlaceholder")}
              value={form.values.title}
              onChange={(event) => form.setField("title", event.target.value)}
              error={error("title")}
              required
              maxLength={140}
            />
            <TextAreaField
              label={t("descriptionLabel")}
              placeholder={t("descriptionPlaceholder")}
              hint={t("descriptionHint", { min: MIN_DESCRIPTION_LENGTH })}
              value={form.values.description}
              onChange={(event) => form.setField("description", event.target.value)}
              error={error("description")}
              required
              maxLength={4000}
            />
            <TextField
              label={t("postalCodeLabel")}
              placeholder={t("postalCodePlaceholder")}
              hint={t("postalCodeHint")}
              value={form.values.postalCode}
              onChange={(event) => form.setField("postalCode", event.target.value)}
              error={error("postalCode")}
              required
              inputMode="numeric"
              maxLength={5}
              autoComplete="postal-code"
            />
            <PhotoUploader upload={upload} />
          </>
        )}

        {form.step === "contact" && (
          <>
            <TextField
              label={t("nameLabel")}
              value={form.values.clientName}
              onChange={(event) => form.setField("clientName", event.target.value)}
              error={error("clientName")}
              required
              autoComplete="name"
            />
            <TextField
              label={t("phoneLabel")}
              hint={t("phoneHint")}
              value={form.values.clientPhone}
              onChange={(event) => form.setField("clientPhone", event.target.value)}
              error={error("clientPhone")}
              required
              type="tel"
              inputMode="tel"
              autoComplete="tel"
            />
            <TextField
              label={`${t("emailLabel")} (${tCommon("optional")})`}
              hint={t("emailHint")}
              value={form.values.clientEmail}
              onChange={(event) => form.setField("clientEmail", event.target.value)}
              error={error("clientEmail")}
              type="email"
              autoComplete="email"
            />

            <div className="space-y-3 rounded-option border border-line bg-page p-5">
              <CheckboxField
                label={t("consentLabel", { maxProfessionals: MAX_PROFESSIONALS })}
                checked={form.values.consentAccepted}
                onChange={(event) => form.setField("consentAccepted", event.target.checked)}
                error={error("consentAccepted")}
              />
              {/* Un boton, no un segundo checkbox: el unico control marcable de
                  este paso es el consentimiento. */}
              <Button
                type="button"
                variant="text"
                aria-expanded={policyOpen}
                aria-controls="policy-summary"
                onClick={() => setPolicyOpen((open) => !open)}
                className="text-[13px]"
              >
                {policyOpen ? t("policyHide") : t("policyShow")}
              </Button>
              <div
                id="policy-summary"
                hidden={!policyOpen}
                className="max-h-[190px] overflow-y-auto rounded-tag border border-line bg-surface p-4"
              >
                <dl className="space-y-2.5">
                  {POLICY_ROWS.map((row) => (
                    <div key={row}>
                      <dt className="text-[12.5px] font-semibold uppercase tracking-[0.7px] text-brand">
                        {t(`policy.${row}.term`)}
                      </dt>
                      <dd className="text-help leading-[1.5] text-secondary">
                        {t(`policy.${row}.body`, { maxProfessionals: MAX_PROFESSIONALS })}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            </div>
          </>
        )}
      </Panel>

      {form.submitError && <Alert tone="error">{form.submitError}</Alert>}

      <div className="flex items-center justify-between gap-3">
        <Button
          type="button"
          variant="secondary"
          onClick={form.goBack}
          disabled={form.stepIndex === 0}
        >
          {tCommon("back")}
        </Button>
        <Button type="submit" size="lg" loading={form.submitting || upload.uploading}>
          {isLastStep ? (form.submitting ? t("submitting") : t("submit")) : tCommon("next")}
        </Button>
      </div>
    </form>
  );
}
