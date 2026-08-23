import type { ReactNode } from "react";

import "./globals.css";

/**
 * Layout raiz. El HTML real (con su `lang`) lo emite `[locale]/layout.tsx`,
 * porque el idioma se conoce solo dentro del segmento de idioma.
 */
export default function RootLayout({ children }: { children: ReactNode }) {
  return children;
}
