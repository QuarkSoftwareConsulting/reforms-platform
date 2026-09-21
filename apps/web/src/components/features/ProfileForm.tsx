"use client";

import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { CategoryPicker } from "@/components/features/CategoryPicker";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { SelectField, TextField } from "@/components/ui/Field";
import { professionalProfileSchema } from "@/helpers/validators";
import { useApiError } from "@/hooks/useApiError";
import { useAuth } from "@/hooks/useAuth";
import { path, type AppLocale } from "@/i18n/routing";
import { professionalService } from "@/services/professional.service";
import type { Category } from "@/types/api";

const RADIUS_OPTIONS = [5, 10, 25, 50, 100, 200, 300] as const;

type FieldErrors = Partial<Record<"businessName" | "phone" | "postalCode" | "serviceRadiusKm" | "categoryIds", string>>;

/**
 * Perfil profesional. Sirve de onboarding (primera vez) y de edicion.
 *
 * Tras crearlo por primera vez lleva al explorador, que es lo que el profesional
 * venia buscando.
 */
export function ProfileForm({ categories }: { categories: Category[] }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("profile");
  const tCommon = useTranslations("common");
  const tValidation = useTranslations("validation");
  const auth = useAuth();
  const router = useRouter();
  const translateError = useApiError();

  const existing = auth.me?.professional ?? null;
  const isOnboarding = existing === null;

  const [businessName, setBusinessName] = useState(existing?.business_name ?? "");
  const [phone, setPhone] = useState(existing?.phone ?? "");
  const [postalCode, setPostalCode] = useState(existing?.postal_code ?? "");
  const [serviceRadiusKm, setServiceRadiusKm] = useState(existing?.service_radius_km ?? 25);
  const [categoryIds, setCategoryIds] = useState<string[]>(
    existing?.categories.map((category) => category.id) ?? [],
  );

  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitError(null);
    setSaved(false);

    const parsed = professionalProfileSchema.safeParse({
      businessName,
      phone,
      postalCode,
      serviceRadiusKm,
      categoryIds,
    });

    if (!parsed.success) {
      const nextErrors: FieldErrors = {};
      for (const issue of parsed.error.issues) {
        const field = issue.path[0];
        if (typeof field === "string") {
          nextErrors[field as keyof FieldErrors] = issue.message;
        }
      }
      setErrors(nextErrors);
      return;
    }

    setErrors({});
    setSubmitting(true);
    try {
      await professionalService.upsertProfile(
        {
          business_name: parsed.data.businessName,
          phone: parsed.data.phone,
          postal_code: parsed.data.postalCode,
          service_radius_km: parsed.data.serviceRadiusKm,
          category_ids: parsed.data.categoryIds,
        },
        locale,
      );
      await auth.refreshMe();
      setSaved(true);
      if (isOnboarding) {
        router.push(path(locale, "projects"));
      }
    } catch (caught) {
      setSubmitError(translateError(caught));
    } finally {
      setSubmitting(false);
    }
  };

  const error = (field: keyof FieldErrors): string | undefined => {
    const key = errors[field];
    return key ? tValidation(key) : undefined;
  };

  return (
    <form onSubmit={handleSubmit} className="mx-auto max-w-2xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-h1 font-bold text-ink">
          {isOnboarding ? t("onboardingTitle") : t("title")}
        </h1>
        <p className="text-secondary">
          {isOnboarding ? t("onboardingSubtitle") : t("subtitle")}
        </p>
      </header>

      <Card className="space-y-5">
        <TextField
          label={t("businessNameLabel")}
          value={businessName}
          onChange={(event) => setBusinessName(event.target.value)}
          error={error("businessName")}
          required
          autoComplete="organization"
        />
        <TextField
          label={t("phoneLabel")}
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
          error={error("phone")}
          required
          type="tel"
          inputMode="tel"
          autoComplete="tel"
        />
        <TextField
          label={t("postalCodeLabel")}
          value={postalCode}
          onChange={(event) => setPostalCode(event.target.value)}
          error={error("postalCode")}
          required
          inputMode="numeric"
          maxLength={5}
          autoComplete="postal-code"
        />
        <SelectField
          label={t("radiusLabel")}
          hint={t("radiusHint")}
          value={String(serviceRadiusKm)}
          onChange={(event) => setServiceRadiusKm(Number(event.target.value))}
          error={error("serviceRadiusKm")}
        >
          {RADIUS_OPTIONS.map((km) => (
            <option key={km} value={km}>
              {km} km
            </option>
          ))}
        </SelectField>
        <CategoryPicker
          categories={categories}
          selected={categoryIds}
          onChange={setCategoryIds}
          multiple
          label={t("categoriesLabel")}
          hint={t("categoriesHint")}
          error={error("categoryIds")}
        />
      </Card>

      {submitError && <Alert tone="error">{submitError}</Alert>}
      {saved && !isOnboarding && <Alert tone="success">{t("saved")}</Alert>}

      <Button type="submit" size="lg" fullWidth loading={submitting}>
        {isOnboarding ? tCommon("next") : tCommon("save")}
      </Button>
    </form>
  );
}
