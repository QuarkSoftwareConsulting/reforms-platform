/** Configuracion de rutas i18n. */

export const locales = ["es", "en"] as const;
export type AppLocale = (typeof locales)[number];

export const defaultLocale: AppLocale = "es";

export function isAppLocale(value: string): value is AppLocale {
  return (locales as readonly string[]).includes(value);
}

/**
 * Segmentos de URL por idioma.
 *
 * Las rutas en espanol se mantienen en espanol tambien en la version inglesa
 * ("/en/proyectos") para no partir los enlaces ya indexados; traducirlas es un
 * cambio aislado a este mapa cuando el SEO en ingles lo justifique.
 */
export const routes = {
  home: "",
  publish: "/publicar",
  projects: "/proyectos",
  myContacts: "/mis-contactos",
  profile: "/perfil",
  login: "/login",
  register: "/registro",
} as const;

export function path(locale: AppLocale, route: keyof typeof routes, suffix = ""): string {
  return `/${locale}${routes[route]}${suffix}`;
}
