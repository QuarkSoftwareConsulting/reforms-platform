import { cn } from "@/helpers/cn";

/**
 * Iconos de linea de la landing.
 *
 * Provisionales: cuando lleguen los definitivos del diseno se sustituyen aqui y
 * la pagina no cambia. Son decorativos (el texto de la tarjeta ya dice lo mismo),
 * por eso van con `aria-hidden`.
 */
const PATHS = {
  document: (
    <>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5M9 13h6M9 17h6" />
    </>
  ),
  list: <path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01" />,
  user: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </>
  ),
  group: (
    <>
      <circle cx="12" cy="7" r="3" />
      <circle cx="5" cy="9" r="2.5" />
      <circle cx="19" cy="9" r="2.5" />
      <path d="M6 20a6 6 0 0 1 12 0M1 19a4.5 4.5 0 0 1 5-4.4M23 19a4.5 4.5 0 0 0-5-4.4" />
    </>
  ),
  tag: (
    <>
      <path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9z" />
      <circle cx="7.5" cy="7.5" r="1.5" />
    </>
  ),
  coins: (
    <>
      <ellipse cx="12" cy="6" rx="7" ry="3" />
      <path d="M5 6v4c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 10v4c0 1.7 3.1 3 7 3s7-1.3 7-3v-4M5 14v4c0 1.7 3.1 3 7 3s7-1.3 7-3v-4" />
    </>
  ),
  lock: (
    <>
      <rect x="4" y="10" width="16" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </>
  ),
} as const;

export type LandingIconName = keyof typeof PATHS;

export function LandingIcon({ name, className }: { name: LandingIconName; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden
      fill="none"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("size-10 shrink-0 stroke-accent", className)}
    >
      {PATHS[name]}
    </svg>
  );
}
