"use client";

import { useTranslations } from "next-intl";
import { useId, useRef, useState } from "react";

import { PhotoUploader } from "@/components/features/PhotoUploader";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldError, SelectField, TextAreaField, TextField } from "@/components/ui/Field";
import { FormErrorSummary, type SummaryIssue } from "@/components/ui/FormErrorSummary";
import { toDatetimeLocal } from "@/helpers/date";
import { focusField } from "@/helpers/formErrors";
import {
  MANUAL_LEAD_FIELDS,
  useAdminManualLead,
  type ManualLeadField,
} from "@/hooks/useAdminManualLead";
import { usePhotoUpload } from "@/hooks/usePhotoUpload";
import type { Category } from "@/types/api";

/**
 * Alta manual de un lead (admin). Los errores y la confirmacion salen junto al boton:
 * antes iban arriba del todo del panel, fuera de pantalla, y el boton parecia no hacer
 * nada.
 */
export function AdminManualLeadForm({
  categories,
  onCreated,
}: {
  categories: Category[];
  onCreated: () => void;
}) {
  const t = useTranslations("admin");
  const tErrors = useTranslations("errors");
  const form = useAdminManualLead();
  const photoUpload = usePhotoUpload();
  const formRef = useRef<HTMLFormElement>(null);
  const photosErrorId = useId();
  // Casi siempre se ingresa el lead el mismo dia: se propone "ahora" y se corrige si no.
  const [defaultAcceptedAt] = useState(() => toDatetimeLocal(new Date()));

  const labels: Record<ManualLeadField, string> = {
    category_id: t("manual.category"),
    title: t("manual.titleLabel"),
    description: t("manual.description"),
    postal_code: t("manual.postalCode"),
    client_name: t("manual.name"),
    client_phone: t("manual.phone"),
    client_email: t("manual.email"),
    channel: t("manual.channel"),
    policy_version: t("manual.policy"),
    accepted_at: t("manual.acceptedAt"),
    campaign_reference: t("manual.campaign"),
    photos: tErrors("fields.photo_keys"),
  };
  const issues: SummaryIssue[] = MANUAL_LEAD_FIELDS.flatMap((field) => {
    const message = form.errors[field];
    return message ? [{ field, label: labels[field], message }] : [];
  });
  /** Props comunes de cada campo: etiqueta, `name`, clave para el resumen y error. */
  const field = (name: Exclude<ManualLeadField, "photos">) => ({
    label: labels[name],
    name,
    fieldKey: name,
    error: form.errors[name],
  });

  return (
    <Card>
      <h2 className="mb-4 text-card-title font-bold text-ink">{t("manual.title")}</h2>
      <form
        ref={formRef}
        noValidate
        className="grid gap-4 sm:grid-cols-2"
        // Formulario no controlado: el error de un campo se borra al escribir en el.
        onChange={(event) => {
          const name = (event.target as Element).getAttribute("name");
          if (name) form.clearError(name);
        }}
        onSubmit={(event) => {
          event.preventDefault();
          // `currentTarget` es null tras el primer `await`: se guarda antes.
          const element = event.currentTarget;
          void form.submit(new FormData(element), photoUpload.storageKeys).then((created) => {
            if (!created) return;
            element.reset();
            onCreated();
          });
        }}
      >
        <SelectField {...field("category_id")} required>
          <option value="">{t("manual.categoryPlaceholder")}</option>
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </SelectField>
        <TextField {...field("title")} required />
        <TextAreaField {...field("description")} className="sm:col-span-2" required />
        <TextField {...field("postal_code")} inputMode="numeric" maxLength={5} required />
        <TextField {...field("client_name")} required />
        <TextField {...field("client_phone")} type="tel" required />
        <TextField {...field("client_email")} type="email" />
        <TextField {...field("channel")} required />
        <TextField {...field("policy_version")} required />
        <TextField
          {...field("accepted_at")}
          type="datetime-local"
          defaultValue={defaultAcceptedAt}
          required
        />
        <TextField {...field("campaign_reference")} />
        <div
          className="space-y-1.5 focus:outline-none sm:col-span-2"
          role="group"
          aria-label={labels.photos}
          aria-describedby={form.errors.photos ? photosErrorId : undefined}
          data-field="photos"
          tabIndex={-1}
        >
          <PhotoUploader upload={photoUpload} />
          {form.errors.photos && <FieldError id={photosErrorId}>{form.errors.photos}</FieldError>}
        </div>

        <div className="space-y-3 sm:col-span-2">
          <FormErrorSummary
            title={tErrors("summary", { count: issues.length })}
            issues={issues}
            attempt={form.failedAttempts}
            onSelect={(key) => focusField(formRef.current, key)}
          />
          {form.error && <Alert tone="error">{form.error}</Alert>}
          {form.createdTitle && (
            <Alert tone="success">{t("manual.created", { title: form.createdTitle })}</Alert>
          )}
          <Button loading={form.saving} type="submit">
            {t("manual.submit")}
          </Button>
        </div>
      </form>
    </Card>
  );
}
