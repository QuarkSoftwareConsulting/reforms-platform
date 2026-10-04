"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";

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
import { OptionCard } from "@/components/ui/OptionCard";
import { PROFESSIONAL_TYPES } from "@/helpers/professionalOptions";
import { useProfessionalFiles } from "@/hooks/useProfessionalFiles";
import { useProfessionalProfile, type ProfileValues } from "@/hooks/useProfessionalProfile";
import { path, type AppLocale } from "@/i18n/routing";
import type { CatalogCategory, Media } from "@/types/api";

const RADIUS_OPTIONS = [5, 10, 25, 50, 100, 200, 300] as const;

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
  const form = useProfessionalProfile();
  const files = useProfessionalFiles();
  const { values, professional } = form;

  const error = (field: keyof ProfileValues): string | undefined => {
    const key = form.errors[field];
    return key ? tValidation(key) : undefined;
  };
  const servicesOf = (categoryId: string): string[] =>
    categories.find((category) => category.id === categoryId)?.services.map((s) => s.id) ?? [];
  const selectedCategories = categories.filter((c) => values.categoryIds.includes(c.id));

  return (
    <form
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
        <p className="text-secondary">
          {professional ? t("subtitle") : t("onboardingSubtitle")}
        </p>
      </header>

      {professional && (
        <VerificationCard verification={professional.verification} />
      )}

      <Card className="space-y-5">
        <h2 className="text-card-title font-semibold text-ink">{t("sections.business")}</h2>
        <TextField
          label={t("businessNameLabel")}
          value={values.businessName}
          onChange={(event) => form.setField("businessName", event.target.value)}
          error={error("businessName")}
          required
          autoComplete="organization"
        />
        <TextField
          label={t("phoneLabel")}
          hint={t("phoneHint")}
          value={values.phone}
          onChange={(event) => form.setField("phone", event.target.value)}
          error={error("phone")}
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
        />
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
      </Card>

      <Card className="space-y-5">
        <div>
          <h2 className="text-card-title font-semibold text-ink">{t("sections.registration")}</h2>
          <p className="text-help text-muted">
            {form.identityLocked ? t("identityLocked") : t("registrationHint")}
          </p>
        </div>
        <fieldset className="space-y-3" disabled={form.identityLocked}>
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
        </fieldset>
        <TextField
          label={t("legalNameLabel")}
          hint={t("legalNameHint")}
          value={values.legalName}
          onChange={(event) => form.setField("legalName", event.target.value)}
          error={error("legalName")}
          disabled={form.identityLocked}
          autoComplete="name"
        />
        <TextField
          label={t("taxIdLabel")}
          value={values.taxId}
          onChange={(event) => form.setField("taxId", event.target.value)}
          error={error("taxId")}
          disabled={form.identityLocked}
          maxLength={20}
        />
        <TextField
          label={t("addressLabel")}
          value={values.address}
          onChange={(event) => form.setField("address", event.target.value)}
          error={error("address")}
          autoComplete="street-address"
        />
      </Card>

      {professional ? (
        <>
          <Card className="space-y-5">
            <h2 className="text-card-title font-semibold text-ink">{t("sections.media")}</h2>
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
