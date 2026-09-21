import type { Config } from "tailwindcss";

/**
 * Sistema de diseno "Voy a Reformar".
 *
 * Los valores viven como variables CSS en `src/app/globals.css` (copia de
 * `design_handoff_voyareformar/tokens.css`); aqui solo se les pone nombre.
 * Los nombres son semanticos a proposito: no hay escala numerica, porque una
 * paleta de dos colores de marca no tiene grados intermedios que elegir.
 */
export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "var(--vr-blue)",
          hover: "var(--vr-blue-hover)",
          soft: "var(--vr-blue-soft)",
        },
        accent: {
          DEFAULT: "var(--vr-yellow)",
          hover: "var(--vr-yellow-hover)",
          disabled: "var(--vr-yellow-disabled)",
          // Texto sobre el acento deshabilitado. Sobre el acento normal el texto
          // es siempre `ink`: blanco sobre amarillo no cumple AA.
          "on-disabled": "var(--vr-text-on-yellow-disabled)",
        },
        ink: "var(--vr-ink)",
        page: "var(--vr-bg)",
        surface: "var(--vr-white)",
        line: "var(--vr-border)",
        "line-strong": "var(--vr-border-strong)",
        divider: "var(--vr-divider)",
        secondary: "var(--vr-text-secondary)",
        muted: "var(--vr-text-help)",
        disabled: "var(--vr-text-disabled)",
        "disabled-soft": "var(--vr-text-disabled-soft)",
        danger: {
          DEFAULT: "var(--vr-error)",
          bg: "var(--vr-error-bg)",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      fontSize: {
        // Tracking negativo solo en titulares; el cuerpo nunca lleva tracking.
        display: ["3.625rem", { lineHeight: "1.05", letterSpacing: "-1.4px" }],
        h1: ["2.25rem", { lineHeight: "1.1", letterSpacing: "-1px" }],
        h2: ["1.875rem", { lineHeight: "1.2", letterSpacing: "-0.6px" }],
        "card-title": ["1.0625rem", { lineHeight: "1.4" }],
        body: ["0.96875rem", { lineHeight: "1.6" }],
        help: ["0.8125rem", { lineHeight: "1.5" }],
        label: ["0.78125rem", { lineHeight: "1.2", letterSpacing: "1.2px" }],
      },
      borderRadius: {
        tag: "6px",
        control: "10px",
        option: "12px",
        card: "14px",
        panel: "18px",
      },
      boxShadow: {
        // Solo menus y modales. Las tarjetas de listado nunca llevan sombra.
        floating: "var(--vr-shadow-floating)",
        focus: "var(--vr-focus-ring)",
      },
      spacing: {
        // Escala base 4 del handoff, con los saltos que no trae Tailwind.
        "3.5": "14px",
        "15": "60px",
        "18": "72px",
      },
      maxWidth: {
        // Ancho del formulario de solicitud y ancho general de pagina.
        form: "980px",
        shell: "1280px",
      },
    },
  },
  plugins: [],
} satisfies Config;
