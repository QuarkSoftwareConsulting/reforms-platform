"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useRef, type ReactNode } from "react";

import { CategoryPicker } from "@/components/features/CategoryPicker";
import { DocumentsSection } from "@/components/features/profile/DocumentsSection";
import { MediaFields } from "@/components/features/profile/MediaFields";
import { ReviewConfirmDialog } from "@/components/features/profile/ReviewConfirmDialog";
import { VerificationCard } from "@/components/features/profile/VerificationCard";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { SelectField, TextField } from "@/components/ui/Field";
import { FormErrorSummary, type SummaryIssue } from "@/components/ui/FormErrorSummary";
import { OptionCard } from "@/components/ui/OptionCard";
import { focusField } from "@/helpers/formErrors";
import { PROFESSIONAL_TYPES } from "@/helpers/professionalOptions";
import { useProfessionalFiles } from "@/hooks/useProfessionalFiles";
import { useProfessionalProfile, type ProfileValues } from "@/hooks/useProfessionalProfile";
import { path, type AppLocale } from "@/i18n/routing";
import type { CatalogCategory, Media } from "@/types/api";

const RADIUS_OPTIONS = [5, 10, 25, 50, 100, 200, 300] as const;

/** Orden de los campos en pantalla: el resumen de errores los lista igual. */
const FIELD_ORDER: (keyof ProfileValues)[] = [
  "businessName",
  "phone",
  "postalCode",
  "serviceRadiusKm",
  "categoryIds",
  "serviceIds",
  "professionalType",
  "legalName",
  "taxId",
  "address",
  "workPhotos",
];

/** Error de un grupo que no es un `Field` (oficios, servicios, tipo de alta, fotos). */
function GroupError({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="text-help font-medium text-danger">
      {children}
    </p>
  );
}

/**
 * Perfil profesional y alta (F02). Sirve de onboarding y de edicion.
 *
 * Tras registrarse, el profesional configura perfil, oficios y zona; despues aporta
 * sus datos fiscales y documentos y envia el alta a revision. Mientras no este
 * aprobada puede ver solicitudes, pero no comprarlas. La logica vive en los hooks.
 */
export function ProfileForm({ categories }: { categories: CatalogCategory[] }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("profile");
  const tCommon = useTranslations("common");
  const tValidation = useTranslations("validation");
  const tErrors = useTranslations("errors");
  const form = useProfessionalProfile();
  const files = useProfessionalFiles();
  const formRef = useRef<HTMLFormElement>(null);
  const { values, professional } = form;

  const error = (field: keyof ProfileValues): string | undefined => form.errors[field];

  const fieldLabels: Record<keyof ProfileValues, string> = {
    businessName: t("businessNameLabel"),
    phone: t("phoneLabel"),
    postalCode: t("postalCodeLabel"),
    serviceRadiusKm: t("radiusLabel"),
    categoryIds: t("categoriesLabel"),
    serviceIds: t("servicesShortLabel"),
    professionalType: t("typeShortLabel"),
    legalName: t("legalNameLabel"),
    taxId: t("taxIdLabel"),
    address: t("addressLabel"),
    profilePhoto: t("sections.media"),
    logo: t("sections.media"),
    workPhotos: t("sections.media"),
  };
  const summaryIssues: SummaryIssue[] = FIELD_ORDER.flatMap((field) => {
    const message = form.errors[field];
    return message ? [{ field, label: fieldLabels[field], message }] : [];
  });
  const servicesOf = (categoryId: string): string[] =>
    categories.find((category) => category.id === categoryId)?.services.map((s) => s.id) ?? [];
  const selectedCategories = categories.filter((c) => values.categoryIds.includes(c.id));

  return (
    <form
      ref={formRef}
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        void form.save();
      }}
      className="mx-auto max-w-2xl space-y-6"
    >
      <header className="space-y-1">
        <h1 className="text-h1 font-bold text-ink">
          {professional ? t("title") : t("onboardingTitle")}
        </h1>
        <p className="text-secondary">{professional ? t("subtitle") : t("onboardingSubtitle")}</p>
      </header>

      {professional && <VerificationCard verification={professional.verification} />}

      <Card className="space-y-5">
        <h2 className="text-card-title font-semibold text-ink">{t("sections.business")}</h2>
        <TextField
          label={t("businessNameLabel")}
          value={values.businessName}
          onChange={(event) => form.setField("businessName", event.target.value)}
          error={error("businessName")}
          fieldKey="businessName"
          required
          autoComplete="organization"
        />
        <TextField
          label={t("phoneLabel")}
          hint={t("phoneHint")}
          value={values.phone}
          onChange={(event) => form.setField("phone", event.target.value)}
          error={error("phone")}
          fieldKey="phone"
          required
          type="tel"
          inputMode="tel"
          autoComplete="tel"
        />
        <TextField
          label={t("postalCodeLabel")}
          hint={t("postalCodeHint")}
          value={values.postalCode}
          onChange={(event) => form.setField("postalCode", event.target.value)}
          error={error("postalCode")}
          fieldKey="postalCode"
          required
          inputMode="numeric"
          maxLength={5}
          autoComplete="postal-code"
        />
        <SelectField
          label={t("radiusLabel")}
          hint={t("radiusHint")}
          value={String(values.serviceRadiusKm)}
          onChange={(event) => form.setField("serviceRadiusKm", Number(event.target.value))}
          error={error("serviceRadiusKm")}
          fieldKey="serviceRadiusKm"
        >
          {RADIUS_OPTIONS.map((km) => (
            <option key={km} value={km}>
              {km} km
            </option>
          ))}
        </SelectField>
      </Card>

      <Card className="space-y-5">
        <h2 className="text-card-title font-semibold text-ink">{t("sections.trades")}</h2>
        <CategoryPicker
          categories={categories}
          selected={values.categoryIds}
          onChange={(ids) => form.setCategories(ids, servicesOf)}
          multiple
          label={t("categoriesLabel")}
          hint={t("categoriesHint")}
          error={error("categoryIds")}
          fieldKey="categoryIds"
        />
        {/* Un solo hueco de error para todos los servicios: el backend los valida juntos. */}
        <div className="space-y-5 focus:outline-none" data-field="serviceIds" tabIndex={-1}>
          {selectedCategories
            .filter((category) => category.services.length > 0)
            .map((category) => (
              <ChipGroup
                key={category.id}
                name={`services-${category.id}`}
                label={t("servicesLabel", { category: category.name })}
                hint={t("servicesHint")}
                options={category.services.map((service) => ({
                  value: service.id,
                  label: service.name,
                }))}
                selected={values.serviceIds}
                multiple
                onToggle={(id) =>
                  form.setField(
                    "serviceIds",
                    values.serviceIds.includes(id)
                      ? values.serviceIds.filter((x) => x !== id)
                      : [...values.serviceIds, id],
                  )
                }
              />
            ))}
          {error("serviceIds") && <GroupError>{error("serviceIds")}</GroupError>}
        </div>
      </Card>

      <Card className="space-y-5">
        <div>
          <h2 className="text-card-title font-semibold text-ink">{t("sections.registration")}</h2>
          <p className="text-help text-muted">
            {form.identityLocked ? t("identityLocked") : t("registrationHint")}
          </p>
        </div>
        <fieldset
          className="space-y-3 focus:outline-none"
          disabled={form.identityLocked}
          data-field="professionalType"
          tabIndex={-1}
        >
          <legend className="text-[15px] font-semibold text-ink">{t("typeLabel")}</legend>
          <div className="grid gap-3 sm:grid-cols-3">
            {PROFESSIONAL_TYPES.map((type) => (
              <OptionCard
                key={type}
                name="professionalType"
                value={type}
                title={t(`types.${type}.title`)}
                subtitle={t(`types.${type}.subtitle`)}
                checked={values.professionalType === type}
                onChange={() => form.setField("professionalType", type)}
              />
            ))}
          </div>
          {error("professionalType") && <GroupError>{error("professionalType")}</GroupError>}
        </fieldset>
        <TextField
          label={t("legalNameLabel")}
          hint={t("legalNameHint")}
          value={values.legalName}
          onChange={(event) => form.setField("legalName", event.target.value)}
          error={error("legalName")}
          fieldKey="legalName"
          disabled={form.identityLocked}
          autoComplete="name"
        />
        <TextField
          label={t("taxIdLabel")}
          value={values.taxId}
          onChange={(event) => form.setField("taxId", event.target.value)}
          error={error("taxId")}
          fieldKey="taxId"
          disabled={form.identityLocked}
          maxLength={20}
        />
        <TextField
          label={t("addressLabel")}
          value={values.address}
          onChange={(event) => form.setField("address", event.target.value)}
          error={error("address")}
          fieldKey="address"
          autoComplete="street-address"
        />
      </Card>

      {professional ? (
        <>
          <Card className="space-y-5">
            <h2 className="text-card-title font-semibold text-ink">{t("sections.media")}</h2>
            <div className="space-y-5 focus:outline-none" data-field="workPhotos" tabIndex={-1}>
              <MediaFields
                files={files}
                profilePhoto={values.profilePhoto}
                logo={values.logo}
                workPhotos={values.workPhotos}
                onChange={(field, value) => {
                  if (field === "workPhotos") form.setField("workPhotos", value as Media[]);
                  else form.setField(field, value as Media | null);
                }}
              />
              {error("workPhotos") && <GroupError>{error("workPhotos")}</GroupError>}
            </div>
          </Card>
          <Card className="space-y-5">
            <h2 className="text-card-title font-semibold text-ink">{t("sections.documents")}</h2>
            <DocumentsSection
              files={files}
              documents={professional.documents}
              professionalType={values.professionalType}
              locked={form.identityLocked}
            />
          </Card>
        </>
      ) : (
        <p className="text-help text-muted">{t("uploadsAfterSaving")}</p>
      )}

      {files.rejected && <Alert tone="warning">{tValidation(files.rejected)}</Alert>}
      {files.error && <Alert tone="error">{files.error}</Alert>}
      {form.error && <Alert tone="error">{form.error}</Alert>}
      {form.saved && <Alert tone="success">{t("saved")}</Alert>}

      {/* Junto al boton: en un formulario largo el error queda arriba, fuera de pantalla,
          y sin esto pulsar "Guardar" parece no hacer nada. */}
      <FormErrorSummary
        title={tErrors("summary", { count: summaryIssues.length })}
        issues={summaryIssues}
        attempt={form.failedAttempts}
        onSelect={(field) => focusField(formRef.current, field)}
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button type="submit" size="lg" loading={form.saving}>
          {professional ? tCommon("save") : t("create")}
        </Button>
        {professional && (
          <Link
            href={path(locale, "projects")}
            className="font-semibold text-brand hover:underline"
          >
            {t("goToProjects")}
          </Link>
        )}
      </div>

      <ReviewConfirmDialog
        open={form.reviewPrompt}
        submitting={form.submitting}
        onConfirm={() => void form.confirmReview()}
        onCancel={form.dismissReview}
      />
    </form>
  );
}
