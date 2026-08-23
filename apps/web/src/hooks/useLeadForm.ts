"use client";

/** Estado del formulario de publicacion por pasos. */

import { useLocale } from "next-intl";
import { useCallback, useMemo, useState } from "react";
import type { z } from "zod";

import { useApiError } from "@/hooks/useApiError";
import {
  leadStepCategorySchema,
  leadStepContactSchema,
  leadStepDetailsSchema,
} from "@/helpers/validators";
import { leadsService } from "@/services/leads.service";
import type { CreatedLead, Locale } from "@/types/api";

export const STEPS = ["category", "details", "contact"] as const;
export type Step = (typeof STEPS)[number];

export interface LeadFormValues {
  categoryId: string;
  title: string;
  description: string;
  postalCode: string;
  clientName: string;
  clientPhone: string;
  clientEmail: string;
  consentAccepted: boolean;
}

const EMPTY: LeadFormValues = {
  categoryId: "",
  title: "",
  description: "",
  postalCode: "",
  clientName: "",
  clientPhone: "",
  clientEmail: "",
  consentAccepted: false,
};

const STEP_SCHEMAS: Record<Step, z.ZodTypeAny> = {
  category: leadStepCategorySchema,
  details: leadStepDetailsSchema,
  contact: leadStepContactSchema,
};

export type FieldErrors = Partial<Record<keyof LeadFormValues, string>>;

export interface LeadFormState {
  values: LeadFormValues;
  step: Step;
  stepIndex: number;
  errors: FieldErrors;
  submitError: string | null;
  submitting: boolean;
  created: CreatedLead | null;
  setField: <K extends keyof LeadFormValues>(field: K, value: LeadFormValues[K]) => void;
  goNext: () => boolean;
  goBack: () => void;
  submit: (photoKeys: string[]) => Promise<void>;
  reset: () => void;
}

/** Valida solo el paso indicado y devuelve los errores por campo. */
function validateStep(step: Step, values: LeadFormValues): FieldErrors {
  const result = STEP_SCHEMAS[step].safeParse(values);
  if (result.success) return {};

  const errors: FieldErrors = {};
  for (const issue of result.error.issues) {
    const field = issue.path[0];
    if (typeof field === "string") {
      errors[field as keyof LeadFormValues] = issue.message;
    }
  }
  return errors;
}

export function useLeadForm(): LeadFormState {
  const locale = useLocale() as Locale;
  const translateError = useApiError();

  const [values, setValues] = useState<LeadFormValues>(EMPTY);
  const [stepIndex, setStepIndex] = useState(0);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<CreatedLead | null>(null);

  const step = STEPS[stepIndex] ?? "category";

  const setField = useCallback(
    <K extends keyof LeadFormValues>(field: K, value: LeadFormValues[K]) => {
      setValues((current) => ({ ...current, [field]: value }));
      // El error de un campo se limpia al escribir en el, no al enviar de nuevo.
      setErrors((current) => {
        if (!(field in current)) return current;
        const next = { ...current };
        delete next[field];
        return next;
      });
    },
    [],
  );

  const goNext = useCallback((): boolean => {
    const stepErrors = validateStep(step, values);
    setErrors(stepErrors);
    if (Object.keys(stepErrors).length > 0) return false;
    setStepIndex((index) => Math.min(index + 1, STEPS.length - 1));
    return true;
  }, [step, values]);

  const goBack = useCallback(() => {
    setErrors({});
    setStepIndex((index) => Math.max(index - 1, 0));
  }, []);

  const submit = useCallback(
    async (photoKeys: string[]) => {
      const stepErrors = validateStep("contact", values);
      setErrors(stepErrors);
      if (Object.keys(stepErrors).length > 0) return;

      setSubmitting(true);
      setSubmitError(null);
      try {
        const lead = await leadsService.create(
          {
            category_id: values.categoryId,
            title: values.title.trim(),
            description: values.description.trim(),
            postal_code: values.postalCode.trim(),
            client_name: values.clientName.trim(),
            client_phone: values.clientPhone.trim(),
            client_email: values.clientEmail.trim() || null,
            photo_keys: photoKeys,
            consent: { accepted: values.consentAccepted },
          },
          locale,
        );
        setCreated(lead);
      } catch (caught) {
        setSubmitError(translateError(caught));
      } finally {
        setSubmitting(false);
      }
    },
    [values, locale, translateError],
  );

  const reset = useCallback(() => {
    setValues(EMPTY);
    setStepIndex(0);
    setErrors({});
    setSubmitError(null);
    setCreated(null);
  }, []);

  return useMemo(
    () => ({
      values,
      step,
      stepIndex,
      errors,
      submitError,
      submitting,
      created,
      setField,
      goNext,
      goBack,
      submit,
      reset,
    }),
    [
      values,
      step,
      stepIndex,
      errors,
      submitError,
      submitting,
      created,
      setField,
      goNext,
      goBack,
      submit,
      reset,
    ],
  );
}
