/** Datos de sitio que necesitan el SEO y los enlaces absolutos. */

/**
 * URL publica del sitio.
 *
 * Hace falta para `metadataBase`, el sitemap y el JSON-LD: sin ella Next emite
 * URLs relativas en Open Graph, que los rastreadores descartan.
 */
export function siteUrl(): string {
  return (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3010").replace(/\/$/, "");
}

/** Ruta absoluta a partir de una ruta de la aplicacion. */
export function absoluteUrl(path: string): string {
  return `${siteUrl()}${path.startsWith("/") ? path : `/${path}`}`;
}

/** Lockup completo (marca + logotipo). Fondo blanco opaco: es la imagen que
 *  comparten Open Graph y el JSON-LD, donde la transparencia no ayuda. */
export const LOGO_PATH = "/logo-voyareformar.png";
export const LOGO_SIZE = { width: 1204, height: 1003 } as const;

/** Isotipo suelto con fondo transparente, para las superficies oscuras. */
export const ISOTYPE_PATH = "/isotipo-voyareformar.png";
