import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminCatalog } from "@/components/features/AdminCatalog";
import { nameError, parsePriceCents, parseSortOrder, priceInput } from "@/helpers/catalog";
import { adminService } from "@/services/admin.service";
import { ApiError } from "@/services/api";
import { revalidationService } from "@/services/revalidation.service";
import type { AdminCatalogCategory } from "@/types/api";

import { messages, renderWithIntl } from "./render";

vi.mock("@/services/admin.service", () => ({
  adminService: {
    catalog: vi.fn(),
    createCategory: vi.fn(),
    updateCategory: vi.fn(),
    deleteCategory: vi.fn(),
    createService: vi.fn(),
    updateService: vi.fn(),
    deleteService: vi.fn(),
    requestServiceImageUpload: vi.fn(),
  },
}));
vi.mock("@/services/revalidation.service", () => ({
  revalidationService: { revalidate: vi.fn() },
}));

const t = messages.admin.catalog;

const eur = (cents: number) => ({ amount_cents: cents, currency: "EUR", formatted: "" });

function category(overrides: Partial<AdminCatalogCategory> = {}): AdminCatalogCategory {
  return {
    id: "cat-1",
    slug: "carpinteria",
    name_es: "Carpintería",
    name_en: "Carpentry",
    suggested_lead_price: eur(500),
    sort_order: 1,
    active: true,
    services: [
      {
        id: "svc-1",
        slug: "puertas",
        name_es: "Puertas",
        name_en: "Doors",
        sort_order: 1,
        active: true,
        featured: false,
        image_key: null,
        landing_name_es: null,
        landing_name_en: null,
        image_url: null,
      },
    ],
    ...overrides,
  };
}

// Las etiquetas llevan el asterisco de obligatorio detras: se busca por prefijo.
const label = (text: string) => new RegExp(`^${text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`);

async function renderCatalog(items: AdminCatalogCategory[] = [category()]) {
  vi.mocked(adminService.catalog).mockResolvedValue(items);
  renderWithIntl(<AdminCatalog />);
  if (items[0]) await screen.findByText(items[0].name_es);
}

describe("catalog helpers", () => {
  it.each([
    ["12,50", 1250],
    ["12.5", 1250],
    ["7", 700],
    ["1000", 100_000],
  ])("reads the price %j in euros as cents", (raw, cents) => {
    expect(parsePriceCents(raw)).toBe(cents);
  });

  it.each(["", "0", "-3", "abc", "1000,01", "1,234", "5,"])("refuses the price %j", (raw) => {
    expect(parsePriceCents(raw)).toBeNull();
  });

  it("formats cents back for the edit field", () => {
    expect(priceInput(1250)).toBe("12,50");
  });

  it("needs letters or numbers and respects the limit", () => {
    expect(nameError("  ", 120)).toBe("catalogNameRequired");
    expect(nameError("¡¡!!", 120)).toBe("catalogNameRequired");
    expect(nameError("x".repeat(121), 120)).toBe("catalogNameTooLong");
    expect(nameError("  Albañilería  ", 120)).toBeNull();
  });

  it("accepts whole sort orders up to 10000", () => {
    expect(parseSortOrder("3")).toBe(3);
    expect(parseSortOrder("1.5")).toBeNull();
    expect(parseSortOrder("10001")).toBeNull();
  });
});

describe("AdminCatalog", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists categories with their services, slug and status", async () => {
    await renderCatalog([
      category(),
      category({ id: "cat-2", slug: "mudanzas", name_es: "Mudanzas", active: false, services: [] }),
    ]);

    expect(screen.getByText("Puertas")).toBeTruthy();
    expect(screen.getByText(/URL: carpinteria/)).toBeTruthy();
    expect(screen.getByText(t.statusInactive)).toBeTruthy();
    expect(screen.getByText(t.noServices)).toBeTruthy();
  });

  it("creates a category with clean names and the price in cents", async () => {
    vi.mocked(adminService.createCategory).mockResolvedValue(
      category({ id: "cat-9", slug: "jardineria", name_es: "Jardinería", services: [] }),
    );
    await renderCatalog();
    const form = screen.getByRole("heading", { name: t.newCategory }).closest("div") as HTMLElement;

    fireEvent.change(within(form).getByLabelText(label(t.nameEs)), { target: { value: "  Jardinería " } });
    fireEvent.change(within(form).getByLabelText(label(t.nameEn)), { target: { value: "Gardening" } });
    fireEvent.change(within(form).getByLabelText(label(t.price)), { target: { value: "7,50" } });
    fireEvent.click(within(form).getByRole("button", { name: t.create }));

    await screen.findByText(t.created);
    expect(adminService.createCategory).toHaveBeenCalledWith(
      { name_es: "Jardinería", name_en: "Gardening", suggested_price_cents: 750 },
      "es",
    );
    expect(screen.getByText("Jardinería")).toBeTruthy();
  });

  it("does not call the API with an invalid name or price", async () => {
    await renderCatalog();
    const form = screen.getByRole("heading", { name: t.newCategory }).closest("div") as HTMLElement;

    fireEvent.change(within(form).getByLabelText(label(t.price)), { target: { value: "0" } });
    fireEvent.click(within(form).getByRole("button", { name: t.create }));

    expect(await screen.findAllByText(messages.validation.catalogNameRequired)).toHaveLength(2);
    expect(screen.getByText(messages.validation.catalogPrice)).toBeTruthy();
    expect(adminService.createCategory).not.toHaveBeenCalled();
  });

  it("deactivates a category from its edit form", async () => {
    vi.mocked(adminService.updateCategory).mockResolvedValue(category({ active: false }));
    await renderCatalog();

    fireEvent.click(screen.getByRole("button", { name: `Editar «Carpintería»` }));
    const form = screen.getByRole("form", { name: `Editar «Carpintería»` });
    fireEvent.click(within(form).getByLabelText(t.categoryActive));
    fireEvent.click(within(form).getByRole("button", { name: t.save }));

    await screen.findByText(t.saved);
    expect(adminService.updateCategory).toHaveBeenCalledWith(
      "cat-1",
      {
        name_es: "Carpintería",
        name_en: "Carpentry",
        suggested_price_cents: 500,
        sort_order: 1,
        active: false,
      },
      "es",
    );
    expect(screen.getByText(t.statusInactive)).toBeTruthy();
  });

  it("asks before deleting and explains when it is in use", async () => {
    vi.mocked(adminService.deleteCategory).mockRejectedValue(
      new ApiError(409, { code: "CATALOG_ITEM_IN_USE", message: "in use" }),
    );
    await renderCatalog();

    fireEvent.click(screen.getByRole("button", { name: `Editar «Carpintería»` }));
    fireEvent.click(screen.getByRole("button", { name: t.delete }));
    const dialog = screen.getByRole("dialog");
    expect(adminService.deleteCategory).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole("button", { name: t.confirm }));

    await screen.findByText(messages.errors.CATALOG_ITEM_IN_USE);
    expect(adminService.deleteCategory).toHaveBeenCalledWith("cat-1", "es");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByText("Carpintería")).toBeTruthy();
  });

  it("removes a deleted service from the list", async () => {
    vi.mocked(adminService.deleteService).mockResolvedValue(undefined);
    await renderCatalog();

    fireEvent.click(screen.getByRole("button", { name: `Editar «Puertas»` }));
    const form = screen.getByRole("form", { name: `Editar «Puertas»` });
    fireEvent.click(within(form).getByRole("button", { name: t.delete }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: t.confirm }));

    await waitFor(() => expect(screen.queryByText("Puertas")).toBeNull());
    expect(adminService.deleteService).toHaveBeenCalledWith("cat-1", "svc-1", "es");
  });

  it("adds a service to its category", async () => {
    const added = category();
    added.services.push({
      id: "svc-2",
      slug: "tarimas",
      name_es: "Tarimas",
      name_en: "Floors",
      sort_order: 2,
      active: true,
      featured: false,
      image_key: null,
      landing_name_es: null,
      landing_name_en: null,
      image_url: null,
    });
    vi.mocked(adminService.createService).mockResolvedValue(added);
    await renderCatalog();

    const form = screen.getByRole("form", { name: `Añadir servicio a «Carpintería»` });
    fireEvent.change(within(form).getByLabelText(t.newServiceEs), { target: { value: "Tarimas" } });
    fireEvent.change(within(form).getByLabelText(t.newServiceEn), { target: { value: "Floors" } });
    fireEvent.click(within(form).getByRole("button", { name: t.addService }));

    await screen.findByText("Tarimas");
    expect(adminService.createService).toHaveBeenCalledWith(
      "cat-1",
      { name_es: "Tarimas", name_en: "Floors" },
      "es",
    );
  });
});

describe("AdminCatalog: servicios destacados en la landing", () => {
  beforeEach(() => vi.clearAllMocks());

  function openService() {
    fireEvent.click(screen.getByRole("button", { name: `Editar «Puertas»` }));
    return screen.getByRole("form", { name: `Editar «Puertas»` });
  }

  it("does not feature a service without its photo", async () => {
    await renderCatalog();
    const form = openService();

    fireEvent.click(within(form).getByLabelText(t.featured));
    fireEvent.click(within(form).getByRole("button", { name: t.save }));

    expect(await within(form).findByText(messages.validation.catalogPhotoRequired)).toBeTruthy();
    expect(adminService.updateService).not.toHaveBeenCalled();
  });

  it("uploads the photo, saves it featured and refreshes the public pages", async () => {
    vi.mocked(adminService.requestServiceImageUpload).mockResolvedValue({
      storage_key: "catalog/services/svc-1/0001/puertas.webp",
      upload_url: "https://bucket.test/upload",
      method: "PUT",
      headers: { "Content-Type": "image/webp" },
      expires_in_seconds: 900,
    });
    const put = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", put);
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:preview" }));
    vi.mocked(adminService.updateService).mockResolvedValue(category());
    await renderCatalog();
    const form = openService();

    const photo = new File(["x"], "puertas.webp", { type: "image/webp" });
    fireEvent.change(within(form).getByLabelText(t.photo), { target: { files: [photo] } });
    await within(form).findByRole("img", { name: `Foto actual de «Puertas»` });
    fireEvent.click(within(form).getByLabelText(t.featured));
    fireEvent.click(within(form).getByRole("button", { name: t.save }));

    await screen.findByText(t.saved);
    expect(put).toHaveBeenCalledWith("https://bucket.test/upload", expect.objectContaining({ method: "PUT" }));
    expect(adminService.updateService).toHaveBeenCalledWith(
      "cat-1",
      "svc-1",
      expect.objectContaining({
        featured: true,
        image_key: "catalog/services/svc-1/0001/puertas.webp",
      }),
      "es",
    );
    expect(revalidationService.revalidate).toHaveBeenCalledWith(["catalog"]);
    vi.unstubAllGlobals();
  });

  it("rejects a photo in a format the landing cannot show", async () => {
    await renderCatalog();
    const form = openService();

    const heic = new File(["x"], "puertas.heic", { type: "image/heic" });
    fireEvent.change(within(form).getByLabelText(t.photo), { target: { files: [heic] } });

    expect(await within(form).findByText(messages.validation.catalogPhotoType)).toBeTruthy();
    expect(adminService.requestServiceImageUpload).not.toHaveBeenCalled();
  });

  it("sends the short landing names, empty as null, and checks their length", async () => {
    vi.mocked(adminService.updateService).mockResolvedValue(category());
    await renderCatalog();
    const form = openService();

    fireEvent.change(within(form).getByLabelText(t.landingNameEs), {
      target: { value: "x".repeat(41) },
    });
    fireEvent.click(within(form).getByRole("button", { name: t.save }));
    const tooLong = messages.validation.catalogNameTooLong.replace("{max}", "40");
    expect(await within(form).findByText(tooLong)).toBeTruthy();
    expect(adminService.updateService).not.toHaveBeenCalled();

    fireEvent.change(within(form).getByLabelText(t.landingNameEs), {
      target: { value: "  Puertas  " },
    });
    fireEvent.click(within(form).getByRole("button", { name: t.save }));

    await screen.findByText(t.saved);
    expect(adminService.updateService).toHaveBeenCalledWith(
      "cat-1",
      "svc-1",
      expect.objectContaining({ landing_name_es: "Puertas", landing_name_en: null }),
      "es",
    );
  });
});
