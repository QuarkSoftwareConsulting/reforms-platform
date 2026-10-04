"use client";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";

/**
 * Confirmacion previa al envio del alta (F02). Enviarla fija tipo, razon social, NIF y
 * documentos, asi que se avisa antes en vez de ofrecer un boton suelto en la pagina.
 */
export function ReviewConfirmDialog({ open, submitting, onConfirm, onCancel }: {
  open: boolean;
  submitting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const t = useTranslations("profile.reviewDialog");
  return (
    <Modal
      open={open}
      title={t("title")}
      onClose={onCancel}
      dismissible={!submitting}
      actions={
        <>
          <Button type="button" variant="secondary" disabled={submitting} onClick={onCancel}>
            {t("cancel")}
          </Button>
          <Button type="button" variant="accent" loading={submitting} onClick={onConfirm}>
            {t("confirm")}
          </Button>
        </>
      }
    >
      <p>{t("body")}</p>
      <p className="font-semibold text-ink">{t("warning")}</p>
    </Modal>
  );
}
