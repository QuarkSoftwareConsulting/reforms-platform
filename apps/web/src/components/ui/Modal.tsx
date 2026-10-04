"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select, textarea';

/**
 * Dialogo modal accesible: foco dentro mientras esta abierto, Escape y clic fuera
 * lo cierran, y al cerrar el foco vuelve a donde estaba. No usa `<dialog>` nativo
 * porque jsdom no implementa `showModal()` y los tests no podrian abrirlo.
 * Con `dismissible={false}` (p. ej. mientras envia) ni Escape ni el clic fuera cierran.
 */
export function Modal({
  open,
  title,
  children,
  actions,
  onClose,
  dismissible = true,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  actions: ReactNode;
  onClose: () => void;
  dismissible?: boolean;
}) {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);
  // El cierre llega por prop y cambia en cada render: se lee de una ref para que
  // el efecto no reabra el foco cada vez que el padre se vuelve a pintar.
  const closeRef = useRef({ onClose, dismissible });
  closeRef.current = { onClose, dismissible };

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    panel.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && closeRef.current.dismissible) {
        event.stopPropagation();
        closeRef.current.onClose();
        return;
      }
      if (event.key !== "Tab" || !panel.current) return;
      const items = Array.from(panel.current.querySelectorAll<HTMLElement>(FOCUSABLE));
      const first = items[0];
      const last = items[items.length - 1];
      if (!first || !last) {
        event.preventDefault();
        return;
      }
      if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previous?.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      // Sin hex en componentes: el velo sale del token de tinta.
      style={{ backgroundColor: "color-mix(in srgb, var(--vr-ink) 45%, transparent)" }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && closeRef.current.dismissible) {
          closeRef.current.onClose();
        }
      }}
    >
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="w-full max-w-md space-y-4 rounded-panel bg-surface p-6 shadow-floating outline-none"
      >
        <h2 id={titleId} className="text-card-title font-semibold text-ink">
          {title}
        </h2>
        <div className="space-y-3 text-body text-secondary">{children}</div>
        <div className="flex flex-wrap justify-end gap-3 pt-2">{actions}</div>
      </div>
    </div>
  );
}
