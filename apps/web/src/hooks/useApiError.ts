"use client";

/** Traduce errores del API y de Firebase al idioma del usuario. */

import { useTranslations } from "next-intl";
import { useCallback } from "react";

import { schemaIssues, type FormIssue, type SchemaIssue } from "@/helpers/formErrors";
import { ApiError } from "@/services/api";

export interface ErrorTranslator {
  (error: unknown): string;
}

type Translate = ReturnType<typeof useTranslations<"errors">>;
type Values = Record<string, string | number>;

function firebaseErrorCode(error: unknown): string | null {
  if (typeof error === "object" && error !== null && "code" in error) {
    const code = (error as { code: unknown }).code;
    if (typeof code === "string" && code.startsWith("auth/")) return code;
  }
  return null;
}

/**
 * El usuario cerro la ventana de Google (o abrio otra encima). No es un error: lo decidio
 * el, y un aviso rojo por ello confunde. El formulario vuelve a su estado sin mensaje.
 */
export function isAuthDismissal(error: unknown): boolean {
  const code = firebaseErrorCode(error);
  return code === "auth/popup-closed-by-user" || code === "auth/cancelled-popup-request";
}

/** Los `details` del backend que son texto o número: lo que cabe en un `{min}` del mensaje. */
function interpolationValues(details: Record<string, unknown> | null): Values {
  const values: Values = {};
  for (const [name, value] of Object.entries(details ?? {})) {
    if (typeof value === "string" || typeof value === "number") values[name] = value;
  }
  return values;
}

/** La regla incumplida, sin decir el campo: "mínimo 20 caracteres". */
function issuePhrase(issue: SchemaIssue, t: Translate): string {
  const { min_length: min, max_length: max } = issue.limits;
  if (issue.type === "missing") return t("issue.missing");
  if (issue.type === "string_too_short" && min !== undefined) return t("issue.tooShort", { min });
  if (issue.type === "string_too_long" && max !== undefined) return t("issue.tooLong", { max });
  return t("issue.invalid");
}

/**
 * Convierte `VALIDATION_ERROR` en "Revisa el formulario: Descripción: mínimo 20
 * caracteres; Teléfono: obligatorio." Devuelve `null` si no hay ningún campo que
 * sepamos nombrar: entonces vale el mensaje genérico del código.
 */
function describeValidation(error: ApiError, t: Translate): string | null {
  const named = schemaIssues(error.details).filter((issue) => t.has(`fields.${issue.key}`));
  if (named.length === 0) return null;
  const unique = [
    ...new Set(
      named.map((issue) =>
        t("fieldError.item", { field: t(`fields.${issue.key}`), issue: issuePhrase(issue, t) }),
      ),
    ),
  ];
  return t("fieldError.intro", { details: unique.join("; ") });
}

/**
 * Devuelve una funcion que convierte cualquier error en un mensaje mostrable.
 *
 * Los codigos del backend (`LEAD_CAP_REACHED`) y los de Firebase
 * (`auth/invalid-credential`) son claves de traduccion; lo que no reconocemos cae
 * en un mensaje genérico en vez de filtrar detalles tecnicos al usuario. El
 * `message` del backend es para desarrolladores y nunca se muestra.
 */
export function useApiError(): ErrorTranslator {
  const t = useTranslations("errors");

  return useCallback(
    (error: unknown): string => {
      const authCode = firebaseErrorCode(error);
      if (authCode) {
        return t.has(authCode) ? t(authCode) : t("generic");
      }
      if (error instanceof ApiError) {
        if (error.code === "VALIDATION_ERROR") {
          const described = describeValidation(error, t);
          if (described) return described;
        }
        return t.has(error.code) ? t(error.code, interpolationValues(error.details)) : t("generic");
      }
      if (error instanceof TypeError) {
        // fetch lanza TypeError cuando no hay red o el CORS falla.
        return t("network");
      }
      return t("generic");
    },
    [t],
  );
}

/** Que campo de UN formulario corresponde a cada error del backend. */
export interface FieldErrorMap {
  /** Codigo de negocio (`INVALID_PHONE`) -> campo del formulario al que pertenece. */
  codes?: Record<string, string>;
  /** Campo del esquema del backend (`consent_accepted_at`) -> campo del formulario. */
  fields: Record<string, string>;
}

export interface ApiFormErrors {
  /** Errores que se pintan en su campo y entran en el resumen junto al boton. */
  issues: FormIssue[];
  /** Lo que no es de un campo (red caida, sin permiso...): va como aviso general. */
  message: string | null;
}

/**
 * Reparte un error del API entre los campos del formulario.
 *
 * Un error con campo (teléfono inválido, descripción corta) se queda en ese campo y en
 * el resumen; el que no tiene campo conocido sale como aviso general. Así el texto del
 * servidor ya no se pierde en un "revisa el formulario" lejos de lo que hay que tocar.
 */
export function useApiFormErrors(map: FieldErrorMap): (error: unknown) => ApiFormErrors {
  const t = useTranslations("errors");
  const translate = useApiError();

  return useCallback(
    (error: unknown): ApiFormErrors => {
      if (error instanceof ApiError) {
        const field = map.codes?.[error.code];
        if (field) return { issues: [{ field, message: translate(error) }], message: null };

        if (error.code === "VALIDATION_ERROR") {
          const issues: FormIssue[] = [];
          let unmapped = false;
          for (const issue of schemaIssues(error.details)) {
            const target = map.fields[issue.key];
            if (target === undefined) unmapped = true;
            else if (!issues.some((existing) => existing.field === target)) {
              issues.push({ field: target, message: issuePhrase(issue, t) });
            }
          }
          if (issues.length > 0) {
            return { issues, message: unmapped ? translate(error) : null };
          }
        }
      }
      return { issues: [], message: translate(error) };
    },
    [map, t, translate],
  );
}
