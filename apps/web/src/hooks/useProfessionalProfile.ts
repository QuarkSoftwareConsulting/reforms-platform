"use client";

/**
 * Estado del perfil profesional y de su alta (F02).
 *
 * El formulario guarda el perfil completo en cada envio (`PUT /me/professional`).
 * Los documentos no pasan por aqui: se adjuntan uno a uno en el momento de subirlos
 * (`useProfessionalFiles`), porque viven en el bucket privado y no en el perfil.
 */

import { useLocale } from "next-intl";
import { useCallback, useMemo, useState } from "react";

import type { ProfessionalType } from "@/helpers/professionalOptions";
import { professionalProfileSchema } from "@/helpers/validators";
import { useApiError } from "@/hooks/useApiError";
import { useAuth } from "@/hooks/useAuth";
import { professionalService } from "@/services/professional.service";
import type { Locale, Media, Professional } from "@/types/api";

export interface ProfileValues {
  businessName: string;
  phone: string;
  postalCode: string;
  serviceRadiusKm: number;
  categoryIds: string[];
  serviceIds: string[];
  professionalType: ProfessionalType | null;
  legalName: string;
  taxId: string;
  address: string;
  profilePhoto: Media | null;
  logo: Media | null;
  workPhotos: Media[];
}

export type ProfileErrors = Partial<Record<keyof ProfileValues, string>>;

function initialValues(professional: Professional | null): ProfileValues {
  return {
    businessName: professional?.business_name ?? "",
    phone: professional?.phone ?? "",
    postalCode: professional?.postal_code ?? "",
    serviceRadiusKm: professional?.service_radius_km ?? 25,
    categoryIds: professional?.categories.map((category) => category.id) ?? [],
    serviceIds: professional?.services.map((service) => service.id) ?? [],
    professionalType: professional?.professional_type ?? null,
    legalName: professional?.legal_name ?? "",
    taxId: professional?.tax_id ?? "",
    address: professional?.address ?? "",
    profilePhoto: professional?.profile_photo ?? null,
    logo: professional?.logo ?? null,
    workPhotos: professional?.work_photos ?? [],
  };
}

export interface ProfessionalProfileState {
  professional: Professional | null;
  values: ProfileValues;
  errors: ProfileErrors;
  /** Tipo, razon social y NIF quedan fijos al enviar el alta a revision. */
  identityLocked: boolean;
  saving: boolean;
  submitting: boolean;
  /** Tras guardar un alta completa se pide confirmar antes de enviarla a revision. */
  reviewPrompt: boolean;
  error: string | null;
  saved: boolean;
  setField: <K extends keyof ProfileValues>(field: K, value: ProfileValues[K]) => void;
  /** Quitar un oficio quita tambien los servicios elegidos dentro de el. */
  setCategories: (categoryIds: string[], servicesOf: (categoryId: string) => string[]) => void;
  save: () => Promise<Professional | null>;
  confirmReview: () => Promise<void>;
  dismissReview: () => void;
}

export function useProfessionalProfile(): ProfessionalProfileState {
  const locale = useLocale() as Locale;
  const auth = useAuth();
  const translateError = useApiError();
  const professional = auth.me?.professional ?? null;

  const [values, setValues] = useState<ProfileValues>(() => initialValues(professional));
  const [errors, setErrors] = useState<ProfileErrors>({});
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [reviewPrompt, setReviewPrompt] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const identityLocked =
    professional !== null && professional.verification.status !== "incomplete";

  const setField = useCallback(
    <K extends keyof ProfileValues>(field: K, value: ProfileValues[K]) => {
      setValues((current) => ({ ...current, [field]: value }));
      setSaved(false);
      setErrors((current) => {
        if (!(field in current)) return current;
        const next = { ...current };
        delete next[field];
        return next;
      });
    },
    [],
  );

  const setCategories = useCallback(
    (categoryIds: string[], servicesOf: (categoryId: string) => string[]) => {
      setValues((current) => {
        const allowed = new Set(categoryIds.flatMap(servicesOf));
        return {
          ...current,
          categoryIds,
          serviceIds: current.serviceIds.filter((id) => allowed.has(id)),
        };
      });
      setSaved(false);
    },
    [],
  );

  const save = useCallback(async (): Promise<Professional | null> => {
    setError(null);
    setSaved(false);
    const parsed = professionalProfileSchema.safeParse({
      ...values,
      workPhotoKeys: values.workPhotos.map((photo) => photo.key),
    });
    if (!parsed.success) {
      const next: ProfileErrors = {};
      for (const issue of parsed.error.issues) {
        const field = issue.path[0];
        if (typeof field === "string" && !(field in next)) {
          next[field as keyof ProfileValues] = issue.message;
        }
      }
      setErrors(next);
      return null;
    }
    setErrors({});
    setSaving(true);
    try {
      const data = parsed.data;
      const updated = await professionalService.upsertProfile(
        {
          business_name: data.businessName,
          phone: data.phone,
          postal_code: data.postalCode,
          service_radius_km: data.serviceRadiusKm,
          category_ids: data.categoryIds,
          service_ids: data.serviceIds,
          professional_type: data.professionalType,
          legal_name: data.legalName,
          tax_id: data.taxId,
          address: data.address,
          profile_photo_key: values.profilePhoto?.key ?? null,
          logo_key: values.logo?.key ?? null,
          work_photo_keys: data.workPhotoKeys,
        },
        locale,
      );
      await auth.refreshMe({ silent: true });
      setSaved(true);
      // Un alta completa que aun no se ha enviado pasa por la confirmacion: no hay
      // boton de envio aparte, guardar es el unico paso del profesional.
      if (updated.verification.status === "incomplete" && updated.verification.missing.length === 0) {
        setReviewPrompt(true);
      }
      return updated;
    } catch (caught) {
      setError(translateError(caught));
      return null;
    } finally {
      setSaving(false);
    }
  }, [values, locale, auth, translateError]);

  const confirmReview = useCallback(async () => {
    // No se vuelve a guardar: el dialogo es modal y lo que se envia es lo recien guardado.
    setSubmitting(true);
    setError(null);
    try {
      await professionalService.submitForReview(locale);
      await auth.refreshMe({ silent: true });
    } catch (caught) {
      setError(translateError(caught));
    } finally {
      setSubmitting(false);
      setReviewPrompt(false);
    }
  }, [locale, auth, translateError]);

  const dismissReview = useCallback(() => setReviewPrompt(false), []);

  return useMemo(
    () => ({
      professional,
      values,
      errors,
      identityLocked,
      saving,
      submitting,
      reviewPrompt,
      error,
      saved,
      setField,
      setCategories,
      save,
      confirmReview,
      dismissReview,
    }),
    [
      professional,
      values,
      errors,
      identityLocked,
      saving,
      submitting,
      reviewPrompt,
      error,
      saved,
      setField,
      setCategories,
      save,
      confirmReview,
      dismissReview,
    ],
  );
}
