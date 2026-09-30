"use client";

import Image from "next/image";
import { useTranslations } from "next-intl";
import { useRef } from "react";

import { Button } from "@/components/ui/Button";
import { MAX_WORK_PHOTOS } from "@/helpers/professionalOptions";
import { ALLOWED_PHOTO_TYPES } from "@/helpers/validators";
import type { ProfessionalFilesState } from "@/hooks/useProfessionalFiles";
import type { Media } from "@/types/api";

function Thumb({ media, alt, onRemove, removeLabel }: {
  media: Media;
  alt: string;
  onRemove: () => void;
  removeLabel: string;
}) {
  return (
    <div className="relative">
      <div className="relative size-24 overflow-hidden rounded-option bg-page">
        <Image src={media.url} alt={alt} fill unoptimized className="object-cover" />
      </div>
      <button
        type="button"
        onClick={onRemove}
        aria-label={removeLabel}
        className="absolute -right-1.5 -top-1.5 flex size-6 items-center justify-center rounded-full bg-ink text-xs text-surface hover:bg-danger"
      >
        ×
      </button>
    </div>
  );
}

function FilePicker({ label, multiple, disabled, loading, onFiles }: {
  label: string;
  multiple?: boolean;
  disabled?: boolean;
  loading: boolean;
  onFiles: (files: File[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={inputRef}
        type="file"
        multiple={multiple}
        accept={ALLOWED_PHOTO_TYPES.join(",")}
        className="hidden"
        onChange={(event) => {
          onFiles(Array.from(event.target.files ?? []));
          event.target.value = "";
        }}
      />
      <Button
        type="button"
        variant="secondary"
        size="sm"
        loading={loading}
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
      >
        {label}
      </Button>
    </>
  );
}

/**
 * Foto del rostro, logo y fotos de trabajos (F02). Van al bucket publico: se
 * ensenaran a los clientes. Se guardan en el perfil al pulsar "Guardar".
 */
export function MediaFields({ files, profilePhoto, logo, workPhotos, onChange }: {
  files: ProfessionalFilesState;
  profilePhoto: Media | null;
  logo: Media | null;
  workPhotos: Media[];
  onChange: (field: "profilePhoto" | "logo" | "workPhotos", value: Media | Media[] | null) => void;
}) {
  const t = useTranslations("profile");

  const single = (field: "profilePhoto" | "logo", current: Media | null, label: string) => (
    <div className="space-y-2">
      <p className="text-[15px] font-semibold text-ink">{label}</p>
      {current && (
        <Thumb
          media={current}
          alt={label}
          onRemove={() => onChange(field, null)}
          removeLabel={`${t("mediaRemove")}: ${label}`}
        />
      )}
      <FilePicker
        label={current ? t("mediaReplace") : t("mediaAdd")}
        loading={files.uploading}
        onFiles={async ([file]) => {
          if (!file) return;
          const uploaded = await files.uploadMedia(file);
          if (uploaded) onChange(field, uploaded);
        }}
      />
    </div>
  );

  return (
    <div className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        {single("profilePhoto", profilePhoto, t("profilePhotoLabel"))}
        {single("logo", logo, t("logoLabel"))}
      </div>
      <div className="space-y-2">
        <p className="text-[15px] font-semibold text-ink">{t("workPhotosLabel")}</p>
        <p className="text-help text-muted">{t("workPhotosHint", { max: MAX_WORK_PHOTOS })}</p>
        {workPhotos.length > 0 && (
          <div className="flex flex-wrap gap-3">
            {workPhotos.map((photo, index) => (
              <Thumb
                key={photo.key}
                media={photo}
                alt={t("workPhotoAlt", { index: index + 1 })}
                onRemove={() =>
                  onChange(
                    "workPhotos",
                    workPhotos.filter((item) => item.key !== photo.key),
                  )
                }
                removeLabel={`${t("mediaRemove")}: ${t("workPhotoAlt", { index: index + 1 })}`}
              />
            ))}
          </div>
        )}
        <FilePicker
          label={t("mediaAdd")}
          multiple
          loading={files.uploading}
          disabled={workPhotos.length >= MAX_WORK_PHOTOS}
          onFiles={async (picked) => {
            const room = MAX_WORK_PHOTOS - workPhotos.length;
            const uploaded: Media[] = [];
            for (const file of picked.slice(0, room)) {
              const media = await files.uploadMedia(file);
              if (media) uploaded.push(media);
            }
            if (uploaded.length > 0) onChange("workPhotos", [...workPhotos, ...uploaded]);
          }}
        />
      </div>
    </div>
  );
}
