/**
 * Secciones del backoffice. Cada una es una subruta (`/admin/solicitudes`...): se puede
 * enlazar, el boton "atras" funciona y solo se cargan los datos de la que se abre.
 *
 * Fuera del componente de navegacion porque las paginas (Server Components) lo leen
 * para su titulo, y de un modulo "use client" solo recibirian una referencia.
 */
export const ADMIN_SECTIONS = [
  { key: "overview", suffix: "" },
  { key: "professionals", suffix: "/profesionales" },
  { key: "leads", suffix: "/solicitudes" },
  { key: "purchases", suffix: "/compras" },
  { key: "pricing", suffix: "/precios" },
] as const;

export type AdminSection = (typeof ADMIN_SECTIONS)[number]["key"];
