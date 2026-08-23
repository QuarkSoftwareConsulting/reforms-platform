import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Combina clases de Tailwind resolviendo conflictos (la ultima gana). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
