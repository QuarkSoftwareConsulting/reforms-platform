import Image from "next/image";

import { cn } from "@/helpers/cn";

/**
 * Iconos de la landing, servidos desde `public/icons`.
 *
 * Los archivos vienen del diseno con nombre numerado; el mapa da a cada uno el
 * nombre de lo que representa. Son decorativos (el texto de la tarjeta ya dice
 * lo mismo), por eso van con `alt` vacio.
 */
const ICONS = {
  review: "icono-2", // portapapeles con check
  details: "icono-4", // ubicacion y documento
  decide: "icono-7", // etiqueta de precio con ojo
  cap: "icono-5", // solicitud repartida entre cinco personas
  price: "icono-3", // etiqueta con euro
  topup: "icono-1", // cartera con euro
  privacy: "icono-6", // contacto con candado
} as const;

export type LandingIconName = keyof typeof ICONS;

export function LandingIcon({ name, className }: { name: LandingIconName; className?: string }) {
  // Cada archivo tiene su propia proporcion: se encajan en una caja cuadrada.
  return (
    <span className={cn("relative block size-10 shrink-0", className)}>
      <Image
        src={`/icons/${ICONS[name]}.svg`}
        alt=""
        fill
        sizes="64px"
        className="object-contain object-left"
      />
    </span>
  );
}
