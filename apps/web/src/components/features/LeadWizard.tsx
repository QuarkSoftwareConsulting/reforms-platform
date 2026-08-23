"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useEffect } from "react";

import { CategoryPicker } from "@/components/features/CategoryPicker";
import { PhotoUploader } from "@/components/features/PhotoUploader";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { CheckboxField, TextAreaField, TextField } from "@/components/ui/Field";
import { MIN_DESCRIPTION_LENGTH } from "@/helpers/validators";
import { STEPS, useLeadForm } from "@/hooks/useLeadForm";
import { usePhotoUpload } from "@/hooks/usePhotoUpload";
import { path, type AppLocale } from "@/i18n/routing";
import type { Category } from "@/types/api";

const MAX_PROFESSIONALS = 3;

/** Formulario de publicacion en tres pasos. Toda la logica vive en los hooks. */
export function LeadWizard({ categories }: { categories: Category[] }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("publish");
  const tCommon = useTranslations("common");
  const tValidation = useTranslations("validation");
  const form = useLeadForm();
  const upload = usePhotoUpload();
  const searchParams = useSearchParams();

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
      <Card className="space-y-4 text-center">
        <h2 className="text-xl font-bold text-emerald-700">{t("successTitle")}</h2>
        <p className="text-slate-600">{t("successBody", { city: form.created.city })}</p>
        <div className="flex flex-wrap justify-center gap-3">
          <Button variant="secondary" onClick={form.reset}>
            {t("publishAnother")}
          </Button>
          <Link href={path(locale, "home") || "/"}>
            <Button variant="ghost">{tCommon("close")}</Button>
          </Link>
        </div>
      </Card>
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
      <div className="space-y-2">
        <p className="text-sm font-medium text-brand-700">
          {t("stepOf", { current: form.stepIndex + 1, total: STEPS.length })} ·{" "}
          {t(`steps.${form.step}`)}
        </p>
        <div className="flex gap-1.5" role="progressbar" aria-valuenow={form.stepIndex + 1} aria-valuemin={1} aria-valuemax={STEPS.length}>
          {STEPS.map((step, index) => (
            <span
              key={step}
              className={`h-1.5 flex-1 rounded-full ${
                index <= form.stepIndex ? "bg-brand-600" : "bg-slate-200"
              }`}
            />
          ))}
        </div>
      </div>

      <Card className="space-y-5">
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
              value={form.values.clientEmail}
              onChange={(event) => form.setField("clientEmail", event.target.value)}
              error={error("clientEmail")}
              type="email"
              autoComplete="email"
            />
            <CheckboxField
              label={
                <>
                  {t("consentLabel", { maxProfessionals: MAX_PROFESSIONALS })}{" "}
                  <span className="text-brand-700 underline">{t("consentLink")}</span>
                </>
              }
              checked={form.values.consentAccepted}
              onChange={(event) => form.setField("consentAccepted", event.target.checked)}
              error={error("consentAccepted")}
            />
          </>
        )}
      </Card>

      {form.submitError && <Alert tone="error">{form.submitError}</Alert>}

      <div className="flex items-center justify-between gap-3">
        <Button
          type="button"
          variant="ghost"
          onClick={form.goBack}
          disabled={form.stepIndex === 0}
        >
          {tCommon("back")}
        </Button>
        <Button type="submit" size="lg" loading={form.submitting || upload.uploading}>
          {isLastStep
            ? form.submitting
              ? t("submitting")
              : t("submit")
            : tCommon("next")}
        </Button>
      </div>
    </form>
  );
}
