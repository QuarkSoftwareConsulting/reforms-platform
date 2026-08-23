/** Utilidades de render: envuelven el arbol con los providers que la app necesita. */

import { render, type RenderResult } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactElement } from "react";

import messages from "../messages/es.json";

export function renderWithIntl(ui: ReactElement, locale = "es"): RenderResult {
  return render(
    <NextIntlClientProvider locale={locale} messages={messages}>
      {ui}
    </NextIntlClientProvider>,
  );
}

export { messages };
