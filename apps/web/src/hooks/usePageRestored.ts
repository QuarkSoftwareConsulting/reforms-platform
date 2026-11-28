"use client";

/** Aviso de que el navegador ha restaurado la pagina desde su cache (bfcache). */

import { useEffect, useRef } from "react";

/**
 * Llama a `onRestored` cuando el navegador devuelve la pagina desde su cache de
 * pagina completa (boton "Atras" al volver de Stripe).
 *
 * Esa restauracion no vuelve a montar React: el estado queda tal cual se dejo al
 * salir, con los botones de pago en "Redirigiendo..." y deshabilitados para siempre.
 * Quien navega fuera a mitad de una accion lo reinicia aqui.
 */
export function usePageRestored(onRestored: () => void): void {
  // Con ref, el listener no se reinstala en cada render por un callback inline.
  const callback = useRef(onRestored);
  callback.current = onRestored;

  useEffect(() => {
    const handle = (event: PageTransitionEvent) => {
      if (event.persisted) callback.current();
    };
    window.addEventListener("pageshow", handle);
    return () => window.removeEventListener("pageshow", handle);
  }, []);
}
