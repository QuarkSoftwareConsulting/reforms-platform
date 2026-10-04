"use client";

/**
 * Alta manual de un lead captado fuera de la web (llamada, feria...).
 *
 * El formulario es largo y su boton queda abajo: los errores se atribuyen a su campo y
 * se resumen junto al boton, igual que en el perfil y en el formulario publico. Las
 * claves de los campos son las del API (`client_phone`), que tambien son los `name`
 * del `<form>`.
 */

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useMemo, useState } from "react";

import { adminLeadSchema } from "@/helpers/validators";
import { useApiFormErrors, type FieldErrorMap } from "@/hooks/useApiError";
import { adminService } from "@/services/admin.service";
import type { Locale } from "@/types/api";

/** Campos con error, en el orden en que se ven: el resumen los lista igual. */
export const MANUAL_LEAD_FIELDS = [
  "category_id",
  "title",
  "description",
  "postal_code",
  "client_name",
  "client_phone",
  "client_email",
  "channel",
  "policy_version",
  "accepted_at",
  "campaign_reference",
  "photos",
] as const;

export type ManualLeadField = (typeof MANUAL_LEAD_FIELDS)[number];
export type ManualLeadErrors = Partial<Record<ManualLeadField, string>>;

const MANUAL_LEAD_ERROR_MAP: FieldErrorMap = {
  codes: {
    CATEGORY_NOT_FOUND: "category_id",
    TITLE_LENGTH_INVALID: "title",
    DESCRIPTION_LENGTH_INVALID: "description",
    INVALID_POSTAL_CODE: "postal_code",
    UNKNOWN_POSTAL_CODE: "postal_code",
    POSTAL_CODE_NOT_COVERED: "postal_code",
    CLIENT_NAME_REQUIRED: "client_name",
    INVALID_PHONE: "client_phone",
    INVALID_EMAIL: "client_email",
    CONSENT_DATE_IN_FUTURE: "accepted_at",
  },
  fields: {
    category_id: "category_id",
    title: "title",
    description: "description",
    postal_code: "postal_code",
    client_name: "client_name",
    client_phone: "client_phone",
    client_email: "client_email",
    photo_keys: "photos",
    consent_channel: "channel",
    consent_policy_version: "policy_version",
    consent_accepted_at: "accepted_at",
    consent_campaign_reference: "campaign_reference",
  },
};

export interface AdminManualLeadState {
  errors: ManualLeadErrors;
  /** Sube en cada envio que falla por un campo: el resumen toma el foco. */
  failedAttempts: number;
  saving: boolean;
  /** Error sin campo (sin red, sin permiso...). */
  error: string | null;
  /** Titulo del ultimo lead creado, para confirmarlo junto al boton. */
  createdTitle: string | null;
  /** Al escribir en un campo desaparece su error, no al reenviar. */
  clearError: (field: string) => void;
  /** Devuelve `true` si se creo el lead (el formulario se puede vaciar). */
  submit: (form: FormData, photoKeys: string[]) => Promise<boolean>;
}

export function useAdminManualLead(): AdminManualLeadState {
  const locale = useLocale() as Locale;
  const tValidation = useTranslations("validation");
  const formErrors = useApiFormErrors(MANUAL_LEAD_ERROR_MAP);

  const [errors, setErrors] = useState<ManualLeadErrors>({});
  const [failedAttempts, setFailedAttempts] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdTitle, setCreatedTitle] = useState<string | null>(null);

  const clearError = useCallback((field: string) => {
    setErrors((current) => {
      if (!(field in current)) return current;
      const next = { ...current };
      delete next[field as ManualLeadField];
      return next;
    });
  }, []);

  const submit = useCallback(
    async (form: FormData, photoKeys: string[]): Promise<boolean> => {
      setError(null);
      setCreatedTitle(null);
      const raw = Object.fromEntries(
        MANUAL_LEAD_FIELDS.filter((field) => field !== "photos").map((field) => [
          field,
          String(form.get(field) ?? ""),
        ]),
      );
      const parsed = adminLeadSchema.safeParse(raw);
      if (!parsed.success) {
        const next: ManualLeadErrors = {};
        for (const issue of parsed.error.issues) {
          const field = issue.path[0] as ManualLeadField;
          if (!(field in next)) next[field] = tValidation(issue.message);
        }
        setErrors(next);
        setFailedAttempts((count) => count + 1);
        return false;
      }

      setErrors({});
      setSaving(true);
      try {
        const data = parsed.data;
        await adminService.createLead(
          {
            category_id: data.category_id,
            title: data.title,
            description: data.description,
            postal_code: data.postal_code,
            client_name: data.client_name,
            client_phone: data.client_phone,
            client_email: data.client_email,
            photo_keys: photoKeys,
            consent: {
              policy_version: data.policy_version,
              // `datetime-local` es hora local sin zona: `Date` la interpreta como tal.
              accepted_at: new Date(data.accepted_at).toISOString(),
              channel: data.channel,
              campaign_reference: data.campaign_reference,
            },
          },
          locale,
        );
        setCreatedTitle(data.title);
        return true;
      } catch (caught) {
        const { issues, message } = formErrors(caught);
        if (issues.length > 0) {
          const next: ManualLeadErrors = {};
          for (const issue of issues) next[issue.field as ManualLeadField] = issue.message;
          setErrors(next);
          setFailedAttempts((count) => count + 1);
        }
        setError(message);
        return false;
      } finally {
        setSaving(false);
      }
    },
    [locale, tValidation, formErrors],
  );

  return useMemo(
    () => ({ errors, failedAttempts, saving, error, createdTitle, clearError, submit }),
    [errors, failedAttempts, saving, error, createdTitle, clearError, submit],
  );
}
