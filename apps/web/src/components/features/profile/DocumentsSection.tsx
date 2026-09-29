"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { formatDate } from "@/helpers/date";
import {
  DOCUMENT_CONTENT_TYPES,
  REQUIRED_DOCUMENT,
  type DocumentKind,
  type ProfessionalType,
} from "@/helpers/professionalOptions";
import type { ProfessionalFilesState } from "@/hooks/useProfessionalFiles";
import type { AppLocale } from "@/i18n/routing";
import type { ProfessionalDocument } from "@/types/api";

/**
 * Documentos de alta (F02): modelos de la Agencia Tributaria para autonomos y
 * empresas; DNI, TIE o pasaporte para el trabajador independiente.
 *
 * Se suben al bucket privado y se adjuntan en el acto. El profesional no tiene
 * enlace para abrirlos: solo el admin, con URLs firmadas que caducan.
 */
export function DocumentsSection({ files, documents, professionalType, locked }: {
  files: ProfessionalFilesState;
  documents: ProfessionalDocument[];
  professionalType: ProfessionalType | null;
  locked: boolean;
}) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("profile");
  const inputRef = useRef<HTMLInputElement>(null);
  const required = professionalType ? REQUIRED_DOCUMENT[professionalType] : null;
  const [kind, setKind] = useState<DocumentKind>(required ?? "tax_registration");
  const effectiveKind = required ?? kind;

  return (
    <div className="space-y-3">
      <div>
        <p className="text-[15px] font-semibold text-ink">{t("documentsLabel")}</p>
        <p className="text-help text-muted">
          {required ? t(`documentsHint.${required}`) : t("documentsHintNoType")}
        </p>
      </div>

      {documents.length > 0 && (
        <ul className="divide-y divide-divider rounded-option border border-line">
          {documents.map((document) => (
            <li key={document.id} className="flex items-center justify-between gap-3 px-4 py-3">
              <span className="min-w-0">
                <span className="block truncate text-[14.5px] font-medium text-ink">
                  {document.filename}
                </span>
                <span className="block text-help text-muted">
                  {t(`documentKinds.${document.kind}`)} ·{" "}
                  {formatDate(document.uploaded_at, locale)}
                </span>
              </span>
              {!locked && (
                <Button
                  type="button"
                  variant="text"
                  size="sm"
                  onClick={() => void files.removeDocument(document.id)}
                  aria-label={`${t("documentRemove")}: ${document.filename}`}
                >
                  {t("documentRemove")}
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {!locked && (
        <div className="flex flex-wrap items-center gap-3">
          {!required && (
            <select
              aria-label={t("documentKindLabel")}
              value={kind}
              onChange={(event) => setKind(event.target.value as DocumentKind)}
              className="min-h-10 rounded-control border border-line bg-surface px-3 text-[14.5px]"
            >
              <option value="tax_registration">{t("documentKinds.tax_registration")}</option>
              <option value="identity">{t("documentKinds.identity")}</option>
            </select>
          )}
          <input
            ref={inputRef}
            type="file"
            accept={DOCUMENT_CONTENT_TYPES.join(",")}
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void files.uploadDocument(effectiveKind, file);
              event.target.value = "";
            }}
          />
          <Button
            type="button"
            variant="secondary"
            size="sm"
            loading={files.uploading}
            onClick={() => inputRef.current?.click()}
          >
            {t("documentAdd")}
          </Button>
        </div>
      )}
      {locked && <p className="text-help text-muted">{t("documentsLocked")}</p>}
    </div>
  );
}
