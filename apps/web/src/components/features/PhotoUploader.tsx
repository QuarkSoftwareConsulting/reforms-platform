"use client";

import Image from "next/image";
import { useTranslations } from "next-intl";
import { useRef } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ALLOWED_PHOTO_TYPES, MAX_PHOTOS } from "@/helpers/validators";
import type { PhotoUploadState } from "@/hooks/usePhotoUpload";

/** Selector de fotos con vista previa. La subida la gestiona `usePhotoUpload`. */
export function PhotoUploader({ upload }: { upload: PhotoUploadState }) {
  const t = useTranslations("publish");
  const tValidation = useTranslations("validation");
  const inputRef = useRef<HTMLInputElement>(null);

  const rejectionKey = { type: "photoType", size: "photoSize", count: "photoCount" } as const;

  return (
    <div className="space-y-3">
      <div>
        <p className="text-[15px] font-semibold text-ink">{t("photosLabel")}</p>
        <p className="text-help text-muted">{t("photosHint", { max: MAX_PHOTOS })}</p>
      </div>

      {upload.photos.length > 0 && (
        <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {upload.photos.map((photo) => (
            <li key={photo.storageKey} className="relative">
              <div className="relative h-24 overflow-hidden rounded-lg bg-page">
                <Image
                  src={photo.previewUrl}
                  alt={photo.filename}
                  fill
                  unoptimized
                  className="object-cover"
                />
              </div>
              <button
                type="button"
                onClick={() => upload.remove(photo.storageKey)}
                aria-label={`${t("photoRemove")}: ${photo.filename}`}
                className="absolute -right-1.5 -top-1.5 flex size-6 items-center justify-center rounded-full bg-ink text-xs text-surface hover:bg-danger"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ALLOWED_PHOTO_TYPES.join(",")}
        className="hidden"
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          void upload.addFiles(files);
          // Se limpia el input para que volver a elegir el mismo archivo dispare
          // el evento change otra vez.
          event.target.value = "";
        }}
      />

      <Button
        type="button"
        variant="secondary"
        size="sm"
        loading={upload.uploading}
        disabled={upload.photos.length >= MAX_PHOTOS}
        onClick={() => inputRef.current?.click()}
      >
        {upload.uploading ? t("uploading") : t("photosAdd")}
      </Button>

      {upload.rejections.length > 0 && (
        <Alert tone="warning">
          <ul className="list-inside list-disc">
            {upload.rejections.map((rejection) => (
              <li key={`${rejection.filename}-${rejection.reason}`}>
                {tValidation(rejectionKey[rejection.reason], { filename: rejection.filename })}
              </li>
            ))}
          </ul>
        </Alert>
      )}
      {upload.error && <Alert tone="error">{upload.error}</Alert>}
    </div>
  );
}
