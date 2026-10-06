"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState } from "react";

import { CategoryPicker } from "@/components/features/CategoryPicker";
import { PhotoUploader } from "@/components/features/PhotoUploader";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Panel } from "@/components/ui/Card";
import { ChipGroup } from "@/components/ui/ChipGroup";
import {
  CheckboxField,
  FieldError,
  TextAreaField,
  TextField,
} from "@/components/ui/Field";
import {
  FormErrorSummary,
  type SummaryIssue,
} from "@/components/ui/FormErrorSummary";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { focusField } from "@/helpers/formErrors";
import { PROJECT_SCHEDULES, PROPERTY_TYPES } from "@/helpers/leadOptions";
import { MIN_DESCRIPTION_LENGTH } from "@/helpers/validators";
import {
  FIELD_STEP,
  STEPS,
  useLeadForm,
  type LeadField,
} from "@/hooks/useLeadForm";
import { usePhotoUpload } from "@/hooks/usePhotoUpload";
import { path, type AppLocale } from "@/i18n/routing";
import type { CatalogCategory } from "@/types/api";

const MAX_PROFESSIONALS = 5;

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
export function LeadWizard({ categories }: { categories: CatalogCategory[] }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("publish");
  const tCommon = useTranslations("common");
  const tErrors = useTranslations("errors");
  const tProject = useTranslations("project");
  const form = useLeadForm();
  const upload = usePhotoUpload();
  const searchParams = useSearchParams();
  const [policyOpen, setPolicyOpen] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);
  const photosErrorId = useId();
  // Campo de otro paso elegido en el resumen: se enfoca cuando ese paso ya se pinto.
  const [pendingFocus, setPendingFocus] = useState<LeadField | null>(null);

  useEffect(() => {
    if (!pendingFocus || FIELD_STEP[pendingFocus] !== form.step) return;
    focusField(formRef.current, pendingFocus);
    setPendingFocus(null);
  }, [pendingFocus, form.step]);

  // Permite entrar desde la landing con el oficio ya elegido (?category=slug), y
  // opcionalmente uno de sus servicios (&service=slug).
  const presetSlug = searchParams.get("category");
  const presetServiceSlug = searchParams.get("service");
  const presetCategory = categories.find((category) => category.slug === presetSlug);
  // El servicio se marca una sola vez: si el usuario lo desmarca, no vuelve.
  const servicePresetApplied = useRef(false);
  useEffect(() => {
    if (!presetCategory || form.values.categoryId) return;
    form.setCategory(presetCategory.id);
  }, [presetCategory, form]);
  useEffect(() => {
    if (servicePresetApplied.current || !presetCategory) return;
    if (form.values.categoryId !== presetCategory.id) return;
    servicePresetApplied.current = true;
    const service = presetCategory.services.find((s) => s.slug === presetServiceSlug);
    if (service) form.setField("serviceIds", [service.id]);
  }, [presetCategory, presetServiceSlug, form]);

  const error = (field: LeadField): string | undefined => form.errors[field];

  if (form.created) {
    return (
      <Panel className="mx-auto max-w-xl p-10 text-center">
        <span
          aria-hidden
          className="mx-auto flex size-[62px] items-center justify-center rounded-full bg-accent"
        >
          <svg
            viewBox="0 0 24 24"
            className="size-8 stroke-ink"
            fill="none"
            strokeWidth={2.5}
          >
            <path
              d="M5 13l4.5 4.5L19 7"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
        <h2 className="mt-6 text-h2 font-bold text-ink">{t("successTitle")}</h2>
        <p className="mt-3 text-[15.5px] leading-[1.6] text-secondary">
          {t("successBody", { city: form.created.city })}
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-3 items-center">
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
  const selectedCategory = categories.find(
    (category) => category.id === form.values.categoryId,
  );
  // El cliente eligio la opcion 1 del mockup con un cambio: los servicios de la
  // categoria se ven junto al boton "Continuar", no debajo de la rejilla.
  const services =
    form.step === "category" &&
    selectedCategory &&
    selectedCategory.services.length > 0
      ? selectedCategory.services
      : null;
  // Orden de pantalla: el resumen lista primero lo que esta antes en el formulario.
  const fieldLabels: Record<LeadField, string> = {
    categoryId: tErrors("fields.category_id"),
    serviceIds: tErrors("fields.service_ids"),
    title: tErrors("fields.title"),
    description: tErrors("fields.description"),
    propertyType: tErrors("fields.property_type"),
    schedule: tErrors("fields.schedule"),
    postalCode: t("postalCodeLabel"),
    photos: tErrors("fields.photo_keys"),
    clientName: t("nameLabel"),
    clientPhone: t("phoneLabel"),
    clientEmail: t("emailLabel"),
    phoneCode: t("phoneCodeLabel"),
    consentAccepted: t("consentShortLabel"),
  };
  const summaryIssues: SummaryIssue[] = (
    Object.keys(fieldLabels) as LeadField[]
  ).flatMap((field) => {
    const message = form.errors[field];
    return message ? [{ field, label: fieldLabels[field], message }] : [];
  });
  const selectIssue = (field: string) => {
    const target = field as LeadField;
    if (FIELD_STEP[target] === form.step) {
      focusField(formRef.current, target);
      return;
    }
    form.goToField(target);
    setPendingFocus(target);
  };

  const toggleService = (id: string) =>
    form.setField(
      "serviceIds",
      form.values.serviceIds.includes(id)
        ? form.values.serviceIds.filter((x) => x !== id)
        : [...form.values.serviceIds, id],
    );

  return (
    <form
      ref={formRef}
      noValidate
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
        <svg
          viewBox="0 0 24 24"
          aria-hidden
          className="mt-0.5 size-[18px] shrink-0 fill-brand"
        >
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
          label={t("stepOf", {
            current: form.stepIndex + 1,
            total: STEPS.length,
          })}
        />
      </div>

      <Panel className="space-y-6 sm:p-8">
        {form.step === "category" && (
          <CategoryPicker
            categories={categories}
            selected={form.values.categoryId ? [form.values.categoryId] : []}
            onChange={(ids) => form.setCategory(ids[0] ?? "")}
            label={t("categoryLabel")}
            error={error("categoryId")}
            fieldKey="categoryId"
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
              fieldKey="title"
              onBlur={() => form.checkField("title")}
              required
              maxLength={140}
            />
            <TextAreaField
              label={t("descriptionLabel")}
              placeholder={t("descriptionPlaceholder")}
              hint={t("descriptionHint", { min: MIN_DESCRIPTION_LENGTH })}
              value={form.values.description}
              onChange={(event) =>
                form.setField("description", event.target.value)
              }
              error={error("description")}
              fieldKey="description"
              onBlur={() => form.checkField("description")}
              required
              maxLength={4000}
            />
            <ChipGroup
              name="propertyType"
              label={t("propertyTypeLabel")}
              options={PROPERTY_TYPES.map((value) => ({
                value,
                label: tProject(`propertyTypes.${value}`),
              }))}
              selected={
                form.values.propertyType ? [form.values.propertyType] : []
              }
              onToggle={(value) => form.setField("propertyType", value)}
              error={error("propertyType")}
              required
              fieldKey="propertyType"
            />
            <ChipGroup
              name="schedule"
              label={t("scheduleLabel")}
              options={PROJECT_SCHEDULES.map((value) => ({
                value,
                label: tProject(`schedules.${value}`),
              }))}
              selected={form.values.schedule ? [form.values.schedule] : []}
              onToggle={(value) => form.setField("schedule", value)}
              error={error("schedule")}
              required
              fieldKey="schedule"
            />
            <TextField
              label={t("postalCodeLabel")}
              placeholder={t("postalCodePlaceholder")}
              hint={t("postalCodeHint")}
              value={form.values.postalCode}
              onChange={(event) =>
                form.setField("postalCode", event.target.value)
              }
              error={error("postalCode")}
              fieldKey="postalCode"
              onBlur={() => form.checkField("postalCode")}
              required
              inputMode="numeric"
              maxLength={5}
              autoComplete="postal-code"
            />
            <div
              className="space-y-1.5 focus:outline-none"
              role="group"
              aria-label={fieldLabels.photos}
              aria-describedby={error("photos") ? photosErrorId : undefined}
              data-field="photos"
              tabIndex={-1}
            >
              <PhotoUploader upload={upload} />
              {error("photos") && (
                <FieldError id={photosErrorId}>{error("photos")}</FieldError>
              )}
            </div>
          </>
        )}

        {form.step === "contact" && (
          <>
            <TextField
              label={t("nameLabel")}
              value={form.values.clientName}
              onChange={(event) =>
                form.setField("clientName", event.target.value)
              }
              error={error("clientName")}
              fieldKey="clientName"
              onBlur={() => form.checkField("clientName")}
              required
              autoComplete="name"
            />
            <TextField
              label={t("phoneLabel")}
              hint={t("phoneHint")}
              value={form.values.clientPhone}
              onChange={(event) =>
                form.setField("clientPhone", event.target.value)
              }
              error={error("clientPhone")}
              fieldKey="clientPhone"
              onBlur={() => form.checkField("clientPhone")}
              required
              type="tel"
              inputMode="tel"
              autoComplete="tel"
            />
            <TextField
              label={`${t("emailLabel")} (${tCommon("optional")})`}
              hint={t("emailHint")}
              value={form.values.clientEmail}
              onChange={(event) =>
                form.setField("clientEmail", event.target.value)
              }
              error={error("clientEmail")}
              fieldKey="clientEmail"
              onBlur={() => form.checkField("clientEmail")}
              type="email"
              autoComplete="email"
            />

            {form.smsSentTo && (
              <div className="space-y-2 rounded-option border border-brand bg-brand-soft p-5">
                <TextField
                  label={t("phoneCodeLabel")}
                  hint={t("phoneCodeHint", { phone: form.smsSentTo })}
                  value={form.values.phoneCode}
                  onChange={(event) =>
                    form.setField("phoneCode", event.target.value)
                  }
                  error={error("phoneCode")}
                  fieldKey="phoneCode"
                  // Sin `required` nativo: si el cliente corrige el telefono, el
                  // formulario tiene que poder enviarse para pedir otro codigo.
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                />
                <Button
                  type="button"
                  variant="text"
                  loading={form.resendingCode}
                  onClick={() => void form.resendCode()}
                  className="text-[13px]"
                >
                  {t("phoneCodeResend")}
                </Button>
              </div>
            )}

            <div className="space-y-3 rounded-option border border-line bg-page p-5">
              <CheckboxField
                label={t("consentLabel", {
                  maxProfessionals: MAX_PROFESSIONALS,
                })}
                checked={form.values.consentAccepted}
                onChange={(event) =>
                  form.setField("consentAccepted", event.target.checked)
                }
                error={error("consentAccepted")}
                fieldKey="consentAccepted"
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
                        {t(`policy.${row}.body`, {
                          maxProfessionals: MAX_PROFESSIONALS,
                        })}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            </div>
          </>
        )}
      </Panel>

      {/* Junto a los botones: el error suele quedar arriba, fuera de pantalla, y en el
          paso 3 puede ser de un paso anterior (un CP que rechazo el servidor). */}
      <FormErrorSummary
        title={tErrors("summary", { count: summaryIssues.length })}
        issues={summaryIssues}
        attempt={form.failedAttempts}
        onSelect={selectIssue}
      />
      {form.submitError && <Alert tone="error">{form.submitError}</Alert>}

      <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
        {services && (
          <ChipGroup
            name="services"
            label={t("servicesLabel", {
              category: selectedCategory?.name ?? "",
            })}
            hint={t("servicesHint")}
            options={services.map((service) => ({
              value: service.id,
              label: service.name,
            }))}
            selected={form.values.serviceIds}
            onToggle={toggleService}
            multiple
            error={error("serviceIds")}
            fieldKey="serviceIds"
            className="flex-1 rounded-option border border-line bg-surface p-5"
          />
        )}
        <div className="flex items-center justify-between gap-3 lg:ml-auto lg:justify-end">
          <Button
            type="button"
            variant="secondary"
            onClick={form.goBack}
            disabled={form.stepIndex === 0}
          >
            {tCommon("back")}
          </Button>
          <Button
            type="submit"
            size="lg"
            loading={form.submitting || upload.uploading}
          >
            {isLastStep
              ? form.submitting
                ? t("submitting")
                : t("submit")
              : tCommon("next")}
          </Button>
        </div>
      </div>
    </form>
  );
}
