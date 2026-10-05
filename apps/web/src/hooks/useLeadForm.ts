"use client";

/** Estado del formulario de publicacion por pasos. */

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useMemo, useState } from "react";
import type { z } from "zod";

import { useApiError, useApiFormErrors, type FieldErrorMap } from "@/hooks/useApiError";
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

/** Campos que pueden tener error: los valores del formulario mas las fotos (otro hook). */
export type LeadField = keyof LeadFormValues | "photos";

/** Mensaje ya traducido de cada campo con error. */
export type FieldErrors = Partial<Record<LeadField, string>>;

/** Paso en el que se muestra cada campo: un error del backend lleva hasta el. */
export const FIELD_STEP: Record<LeadField, Step> = {
  categoryId: "category",
  serviceIds: "category",
  title: "details",
  description: "details",
  propertyType: "details",
  schedule: "details",
  postalCode: "details",
  photos: "details",
  clientName: "contact",
  clientPhone: "contact",
  clientEmail: "contact",
  phoneCode: "contact",
  consentAccepted: "contact",
};

/** Errores del backend que pertenecen a un campo concreto del formulario. */
const LEAD_ERROR_MAP: FieldErrorMap = {
  codes: {
    CATEGORY_NOT_FOUND: "categoryId",
    INVALID_SERVICE: "serviceIds",
    TITLE_LENGTH_INVALID: "title",
    DESCRIPTION_LENGTH_INVALID: "description",
    INVALID_POSTAL_CODE: "postalCode",
    UNKNOWN_POSTAL_CODE: "postalCode",
    POSTAL_CODE_NOT_COVERED: "postalCode",
    CLIENT_NAME_REQUIRED: "clientName",
    INVALID_PHONE: "clientPhone",
    PHONE_NOT_MOBILE: "clientPhone",
    INVALID_EMAIL: "clientEmail",
    PHONE_NOT_VERIFIED: "phoneCode",
    CONSENT_REQUIRED: "consentAccepted",
  },
  fields: {
    category_id: "categoryId",
    service_ids: "serviceIds",
    title: "title",
    description: "description",
    property_type: "propertyType",
    schedule: "schedule",
    postal_code: "postalCode",
    photo_keys: "photos",
    client_name: "clientName",
    client_phone: "clientPhone",
    client_email: "clientEmail",
    phone_verification_code: "phoneCode",
    consent_accepted: "consentAccepted",
  },
};

/** Los errores de `errors` que no son de `step`: siguen ahi al cambiar de paso. */
function errorsOutside(errors: FieldErrors, step: Step): FieldErrors {
  const kept: FieldErrors = {};
  for (const [field, message] of Object.entries(errors) as [LeadField, string][]) {
    if (FIELD_STEP[field] !== step) kept[field] = message;
  }
  return kept;
}

export interface LeadFormState {
  values: LeadFormValues;
  step: Step;
  stepIndex: number;
  errors: FieldErrors;
  /**
   * Sube en cada intento fallido (avanzar o publicar). El resumen de errores lo usa
   * para tomar el foco: sin el, el boton parece no hacer nada.
   */
  failedAttempts: number;
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
  /** Valida un campo al salir de el (ver `checkField` en la implementacion). */
  checkField: (field: keyof LeadFormValues) => void;
  /** Vuelve al paso donde esta el campo, para corregirlo desde el resumen. */
  goToField: (field: LeadField) => void;
  submit: (photoKeys: string[]) => Promise<void>;
  reset: () => void;
}

/** Valida solo el paso indicado y devuelve las claves de validacion por campo. */
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
  const formErrors = useApiFormErrors(LEAD_ERROR_MAP);
  const tValidation = useTranslations("validation");

  const [values, setValues] = useState<LeadFormValues>(EMPTY);
  const [stepIndex, setStepIndex] = useState(0);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [failedAttempts, setFailedAttempts] = useState(0);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<CreatedLead | null>(null);
  // `null` = aun no se sabe si este entorno verifica por SMS; lo dice el API.
  const [smsRequired, setSmsRequired] = useState<boolean | null>(null);
  const [smsSentTo, setSmsSentTo] = useState<string | null>(null);
  const [resendingCode, setResendingCode] = useState(false);

  const step = STEPS[stepIndex] ?? "category";

  /**
   * Sustituye los errores de `step` por los de su validacion, sin tocar los de otros
   * pasos (un telefono que rechazo el backend sigue marcado al volver al paso 2).
   * Devuelve si el paso es valido.
   */
  const applyStepValidation = useCallback(
    (target: Step): boolean => {
      const keys = validateStep(target, values);
      const translated: FieldErrors = {};
      for (const [field, key] of Object.entries(keys) as [LeadField, string][]) {
        translated[field] = tValidation(key);
      }
      setErrors((current) => ({ ...errorsOutside(current, target), ...translated }));
      const valid = Object.keys(translated).length === 0;
      if (!valid) setFailedAttempts((count) => count + 1);
      return valid;
    },
    [values, tValidation],
  );

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

  /**
   * Al salir de un campo ya escrito se avisa si no vale, sin esperar a "Continuar".
   * Un campo vacio no se marca (el usuario puede estar solo recorriendolos) y nunca se
   * quita un error: el de un campo editado ya se fue al escribir, y si queda uno es
   * del servidor, que la validacion local no ve.
   */
  const checkField = useCallback(
    (field: keyof LeadFormValues) => {
      const value = values[field];
      if (typeof value !== "string" || value.trim() === "") return;
      const key = validateStep(FIELD_STEP[field], values)[field];
      if (key) setErrors((current) => ({ ...current, [field]: tValidation(key) }));
    },
    [values, tValidation],
  );

  const goNext = useCallback((): boolean => {
    if (!applyStepValidation(step)) return false;
    setStepIndex((index) => Math.min(index + 1, STEPS.length - 1));
    return true;
  }, [step, applyStepValidation]);

  const goBack = useCallback(() => {
    // Lo que el usuario aun no ha intentado enviar no se marca como error al volver.
    setErrors((current) => errorsOutside(current, step));
    setStepIndex((index) => Math.max(index - 1, 0));
  }, [step]);

  const goToField = useCallback((field: LeadField) => {
    setStepIndex(STEPS.indexOf(FIELD_STEP[field]));
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
      if (!applyStepValidation("contact")) return;
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
          setErrors((current) => ({ ...current, phoneCode: tValidation("phoneCodeFormat") }));
          setFailedAttempts((count) => count + 1);
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
        // Un error con campo se pinta en su campo y el formulario vuelve al paso donde
        // esta: un CP rechazado no puede quedarse como aviso suelto en el paso 3.
        const { issues, message } = formErrors(caught);
        if (issues.length > 0) {
          const next: FieldErrors = {};
          for (const issue of issues) next[issue.field as LeadField] = issue.message;
          setErrors(next);
          const firstStep = Math.min(
            ...issues.map((issue) => STEPS.indexOf(FIELD_STEP[issue.field as LeadField])),
          );
          setStepIndex(firstStep);
          setFailedAttempts((count) => count + 1);
        }
        setSubmitError(message);
      } finally {
        setSubmitting(false);
      }
    },
    [values, locale, smsRequired, smsSentTo, applyStepValidation, formErrors, tValidation],
  );

  const reset = useCallback(() => {
    setValues(EMPTY);
    setStepIndex(0);
    setErrors({});
    setFailedAttempts(0);
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
      failedAttempts,
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
      checkField,
      goToField,
      submit,
      reset,
    }),
    [
      values,
      step,
      stepIndex,
      errors,
      failedAttempts,
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
      checkField,
      goToField,
      submit,
      reset,
    ],
  );
}
