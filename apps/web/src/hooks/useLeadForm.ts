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
import type { ProjectSchedule, PropertyType } from "@/helpers/leadOptions";
import { leadsService } from "@/services/leads.service";
import type { CreatedLead, Locale } from "@/types/api";

export const STEPS = ["category", "details", "contact"] as const;
export type Step = (typeof STEPS)[number];

export interface LeadFormValues {
  categoryId: string;
  serviceIds: string[];
  title: string;
  description: string;
  /** Vacio hasta que el cliente elige; la validacion del paso lo exige. */
  propertyType: PropertyType | "";
  schedule: ProjectSchedule | "";
  postalCode: string;
  clientName: string;
  clientPhone: string;
  clientEmail: string;
  consentAccepted: boolean;
  /** Codigo del SMS de verificacion; solo se pide si el API lo exige. */
  phoneCode: string;
}

const EMPTY: LeadFormValues = {
  categoryId: "",
  serviceIds: [],
  title: "",
  description: "",
  propertyType: "",
  schedule: "",
  postalCode: "",
  clientName: "",
  clientPhone: "",
  clientEmail: "",
  consentAccepted: false,
  phoneCode: "",
};

const PHONE_CODE = /^\d{6}$/;

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
  /** Movil al que se envio el SMS; mientras sea `null` no se pide codigo. */
  smsSentTo: string | null;
  resendingCode: boolean;
  resendCode: () => Promise<void>;
  setField: <K extends keyof LeadFormValues>(field: K, value: LeadFormValues[K]) => void;
  /** Cambiar de categoria limpia los servicios: eran de la anterior. */
  setCategory: (categoryId: string) => void;
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
    // Se muestra el primer error de cada campo: el que falla antes es el mas
    // concreto (un CP inexistente tambien esta "fuera de Madrid").
    if (typeof field === "string" && !(field in errors)) {
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
  // `null` = aun no se sabe si este entorno verifica por SMS; lo dice el API.
  const [smsRequired, setSmsRequired] = useState<boolean | null>(null);
  const [smsSentTo, setSmsSentTo] = useState<string | null>(null);
  const [resendingCode, setResendingCode] = useState(false);

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

  const setCategory = useCallback((categoryId: string) => {
    setValues((current) =>
      current.categoryId === categoryId ? current : { ...current, categoryId, serviceIds: [] },
    );
    setErrors((current) => {
      if (!("categoryId" in current)) return current;
      const next = { ...current };
      delete next.categoryId;
      return next;
    });
  }, []);

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

  const resendCode = useCallback(async () => {
    const phone = values.clientPhone.trim();
    setResendingCode(true);
    setSubmitError(null);
    try {
      await leadsService.startPhoneVerification(phone);
      setSmsSentTo(phone);
    } catch (caught) {
      setSubmitError(translateError(caught));
    } finally {
      setResendingCode(false);
    }
  }, [values.clientPhone, translateError]);

  const submit = useCallback(
    async (photoKeys: string[]) => {
      const stepErrors = validateStep("contact", values);
      setErrors(stepErrors);
      if (Object.keys(stepErrors).length > 0) return;
      // Los pasos anteriores ya se validaron al avanzar; esto solo estrecha el tipo.
      if (!values.propertyType || !values.schedule) return;

      setSubmitting(true);
      setSubmitError(null);
      const phone = values.clientPhone.trim();
      try {
        // Antes de publicar se verifica el movil (F01). Si el cliente cambia el
        // telefono tras recibir el SMS, el codigo ya no vale: se manda otro.
        let verified = smsRequired === false;
        if (!verified && smsSentTo !== phone) {
          const { required } = await leadsService.startPhoneVerification(phone);
          setSmsRequired(required);
          if (required) {
            setSmsSentTo(phone);
            setValues((current) => ({ ...current, phoneCode: "" }));
            return;
          }
          verified = true;
        }
        if (!verified && !PHONE_CODE.test(values.phoneCode.trim())) {
          setErrors({ phoneCode: "phoneCodeFormat" });
          return;
        }

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
            service_ids: values.serviceIds,
            property_type: values.propertyType,
            schedule: values.schedule,
            phone_verification_code: verified ? null : values.phoneCode.trim(),
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
    [values, locale, translateError, smsRequired, smsSentTo],
  );

  const reset = useCallback(() => {
    setValues(EMPTY);
    setStepIndex(0);
    setErrors({});
    setSubmitError(null);
    setCreated(null);
    setSmsSentTo(null);
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
      smsSentTo,
      resendingCode,
      resendCode,
      setField,
      setCategory,
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
      smsSentTo,
      resendingCode,
      resendCode,
      setField,
      setCategory,
      goNext,
      goBack,
      submit,
      reset,
    ],
  );
}
