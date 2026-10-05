"use client";

/**
 * Subidas del alta del profesional con URL prefirmada.
 *
 * Las fotos (rostro, logo, trabajos) van al bucket publico y se guardan en el perfil
 * al pulsar "Guardar". Los documentos van al bucket PRIVADO y se adjuntan al alta en
 * el momento: el profesional no tiene URL para verlos, solo el admin con firma.
 */

import { useCallback, useState } from "react";

import type { DocumentKind } from "@/helpers/professionalOptions";
import { DOCUMENT_CONTENT_TYPES } from "@/helpers/professionalOptions";
import { MAX_PHOTO_BYTES, validatePhotos } from "@/helpers/validators";
import { useApiError } from "@/hooks/useApiError";
import { useAuth } from "@/hooks/useAuth";
import { professionalService, type UploadPurpose } from "@/services/professional.service";
import type { Media } from "@/types/api";

export interface ProfessionalFilesState {
  uploading: boolean;
  error: string | null;
  /** Clave de validacion ("photoType", "documentType"...) del ultimo archivo rechazado. */
  rejected: string | null;
  uploadMedia: (file: File) => Promise<Media | null>;
  uploadDocument: (kind: DocumentKind, file: File) => Promise<void>;
  removeDocument: (documentId: string) => Promise<void>;
}

async function putToBucket(purpose: UploadPurpose, file: File): Promise<string> {
  const presigned = await professionalService.requestUpload(purpose, file);
  const response = await fetch(presigned.upload_url, {
    method: presigned.method,
    headers: presigned.headers,
    body: file,
  });
  if (!response.ok) throw new Error(`Fallo la subida de ${file.name}`);
  return presigned.storage_key;
}

export function useProfessionalFiles(): ProfessionalFilesState {
  const auth = useAuth();
  const translateError = useApiError();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rejected, setRejected] = useState<string | null>(null);

  const run = useCallback(
    async <T>(action: () => Promise<T>): Promise<T | null> => {
      setUploading(true);
      setError(null);
      try {
        return await action();
      } catch (caught) {
        setError(translateError(caught));
        return null;
      } finally {
        setUploading(false);
      }
    },
    [translateError],
  );

  const uploadMedia = useCallback(
    async (file: File): Promise<Media | null> => {
      const { rejected: refused } = validatePhotos([file], 0);
      if (refused.length > 0) {
        setRejected(refused[0]?.reason === "size" ? "mediaTooLarge" : "mediaType");
        return null;
      }
      setRejected(null);
      return run(async () => ({
        key: await putToBucket("media", file),
        url: URL.createObjectURL(file),
      }));
    },
    [run],
  );

  const uploadDocument = useCallback(
    async (kind: DocumentKind, file: File): Promise<void> => {
      const allowed = (DOCUMENT_CONTENT_TYPES as readonly string[]).includes(file.type);
      if (!allowed || file.size > MAX_PHOTO_BYTES) {
        setRejected(allowed ? "documentTooLarge" : "documentType");
        return;
      }
      setRejected(null);
      await run(async () => {
        const key = await putToBucket("document", file);
        await professionalService.addDocument(kind, key, file.name);
        await auth.refreshMe({ silent: true });
      });
    },
    [run, auth],
  );

  const removeDocument = useCallback(
    async (documentId: string): Promise<void> => {
      await run(async () => {
        await professionalService.removeDocument(documentId);
        await auth.refreshMe({ silent: true });
      });
    },
    [run, auth],
  );

  return { uploading, error, rejected, uploadMedia, uploadDocument, removeDocument };
}
