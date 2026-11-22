import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LocaleSwitch } from "@/components/features/LocaleSwitch";

import { messages, renderWithIntl } from "./render";

let pathname = "/es/proyectos";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));

describe("LocaleSwitch", () => {
  beforeEach(() => {
    pathname = "/es/proyectos";
    window.history.replaceState(null, "", "/es/proyectos");
  });

  it("marks the current language and links to the same page in the other one", () => {
    renderWithIntl(<LocaleSwitch />);

    const es = screen.getByRole("link", { name: messages.nav.languageEs });
    const en = screen.getByRole("link", { name: messages.nav.languageEn });
    expect(es.getAttribute("aria-current")).toBe("true");
    expect(en.getAttribute("aria-current")).toBeNull();
    expect(en.getAttribute("href")).toBe("/en/proyectos");
  });

  it("keeps nested paths, the query and the anchor", () => {
    pathname = "/es/proyectos/abc-123";
    window.history.replaceState(null, "", "/es/proyectos/abc-123?categoria=pintura#fotos");

    renderWithIntl(<LocaleSwitch />);

    expect(screen.getByRole("link", { name: messages.nav.languageEn }).getAttribute("href")).toBe(
      "/en/proyectos/abc-123?categoria=pintura#fotos",
    );
  });

  it("goes back to the home page of the other language", () => {
    pathname = "/en";
    window.history.replaceState(null, "", "/en");

    renderWithIntl(<LocaleSwitch />, "en");

    expect(screen.getByRole("link", { name: messages.nav.languageEs }).getAttribute("href")).toBe("/es");
  });
});
