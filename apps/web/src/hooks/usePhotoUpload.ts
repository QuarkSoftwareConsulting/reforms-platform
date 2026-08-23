"use client";

/**
 * Subida de fotos con URL prefirmada.
 *
 * Los bytes van del navegador al bucket directamente; el API solo firma la URL.
 * Asi no pagamos ancho de banda de subida ni bloqueamos un worker del backend.
 */

import { useCallback, useState } from "react";

import { useApiError } from "@/hooks/useApiError";
import { validatePhotos, type PhotoRejection } from "@/helpers/validators";
import { leadsService } from "@/services/leads.service";

export interface UploadedPhoto {
  storageKey: string;
  previewUrl: string;
  filename: string;
}

export interface PhotoUploadState {
  photos: UploadedPhoto[];
  uploading: boolean;
  error: string | null;
  rejections: PhotoRejection[];
  addFiles: (files: File[]) => Promise<void>;
  remove: (storageKey: string) => void;
  storageKeys: string[];
}

export function usePhotoUpload(): PhotoUploadState {
  const translateError = useApiError();
  const [photos, setPhotos] = useState<UploadedPhoto[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rejections, setRejections] = useState<PhotoRejection[]>([]);

  const addFiles = useCallback(
    async (files: File[]) => {
      const { accepted, rejected } = validatePhotos(files, photos.length);
      setRejections(rejected);
      if (accepted.length === 0) return;

      setUploading(true);
      setError(null);
      try {
        const uploaded = await Promise.all(
          accepted.map(async (file) => {
            const presigned = await leadsService.presignPhoto(file.name, file.type, file.size);
            const response = await fetch(presigned.upload_url, {
              method: presigned.method,
              headers: presigned.headers,
              body: file,
            });
            if (!response.ok) {
              throw new Error(`Fallo la subida de ${file.name}`);
            }
            return {
              storageKey: presigned.storage_key,
              previewUrl: URL.createObjectURL(file),
              filename: file.name,
            };
          }),
        );
        setPhotos((current) => [...current, ...uploaded]);
      } catch (caught) {
        setError(translateError(caught));
      } finally {
        setUploading(false);
      }
    },
    [photos.length, translateError],
  );

  const remove = useCallback((storageKey: string) => {
    setPhotos((current) => {
      const target = current.find((photo) => photo.storageKey === storageKey);
      if (target) URL.revokeObjectURL(target.previewUrl);
      return current.filter((photo) => photo.storageKey !== storageKey);
    });
  }, []);

  return {
    photos,
    uploading,
    error,
    rejections,
    addFiles,
    remove,
    storageKeys: photos.map((photo) => photo.storageKey),
  };
}
