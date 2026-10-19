"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, Tag } from "@/components/ui/Card";
import { CheckboxField, TextField } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import {
  CATEGORY_NAME_MAX,
  SERVICE_NAME_MAX,
  cleanName,
  nameError,
  parsePriceCents,
  parseSortOrder,
  priceInput,
  type CatalogFieldError,
} from "@/helpers/catalog";
import { formatMoney } from "@/helpers/currency";
import { useAdminCatalog, type AdminCatalogState } from "@/hooks/useAdminCatalog";
import { type AppLocale } from "@/i18n/routing";
import type { AdminCatalogCategory, AdminCatalogService } from "@/types/api";

type Errors = Partial<Record<"name_es" | "name_en" | "price" | "sort_order", CatalogFieldError>>;

/** Lo que el admin va a borrar, para el dialogo de confirmacion. */
type DeleteTarget =
  | { kind: "category"; category: AdminCatalogCategory }
  | { kind: "service"; category: AdminCatalogCategory; service: AdminCatalogService };

/**
 * Catalogo de oficios: categorias y sus servicios. Lo que ya se uso solo se desactiva;
 * borrar es para lo creado por error (el API responde CATALOG_ITEM_IN_USE si no).
 */
export function AdminCatalog() {
  const t = useTranslations("admin.catalog");
  const tCommon = useTranslations("common");
  const catalog = useAdminCatalog();
  const [deleting, setDeleting] = useState<DeleteTarget | null>(null);

  async function confirmDelete() {
    if (!deleting) return;
    if (deleting.kind === "category") await catalog.deleteCategory(deleting.category.id);
    else await catalog.deleteService(deleting.category.id, deleting.service.id);
    // Tambien si falla (p. ej. en uso): el motivo queda en el aviso de arriba.
    setDeleting(null);
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-secondary">{t("intro")}</p>
      {catalog.error && <Alert tone="error">{catalog.error}</Alert>}
      {catalog.notice && <Alert tone="success">{catalog.notice}</Alert>}

      <NewCategoryForm catalog={catalog} />

      {catalog.loading ? (
        <p className="text-help text-muted">{tCommon("loading")}</p>
      ) : catalog.categories.length === 0 ? (
        <p className="text-help text-muted">{t("empty")}</p>
      ) : (
        <ul className="space-y-4">
          {catalog.categories.map((category) => (
            <li key={category.id}>
              <CategoryCard
                category={category}
                catalog={catalog}
                onDelete={(target) => setDeleting(target)}
              />
            </li>
          ))}
        </ul>
      )}

      <Modal
        open={deleting !== null}
        title={
          deleting
            ? t("confirmTitle", {
                name: deleting.kind === "category" ? deleting.category.name_es : deleting.service.name_es,
              })
            : ""
        }
        onClose={() => setDeleting(null)}
        dismissible={catalog.pending === null}
        actions={
          <>
            <Button
              type="button"
              variant="secondary"
              disabled={catalog.pending !== null}
              onClick={() => setDeleting(null)}
            >
              {tCommon("cancel")}
            </Button>
            <Button
              type="button"
              variant="danger"
              loading={catalog.pending !== null}
              onClick={() => void confirmDelete()}
            >
              {t("confirm")}
            </Button>
          </>
        }
      >
        <p>{t("confirmBody")}</p>
      </Modal>
    </div>
  );
}

function NewCategoryForm({ catalog }: { catalog: AdminCatalogState }) {
  const t = useTranslations("admin.catalog");
  const tValidation = useTranslations("validation");
  const [nameEs, setNameEs] = useState("");
  const [nameEn, setNameEn] = useState("");
  const [price, setPrice] = useState("");
  const [errors, setErrors] = useState<Errors>({});

  async function submit(event: FormEvent) {
    event.preventDefault();
    const cents = parsePriceCents(price);
    const next: Errors = {
      name_es: nameError(nameEs, CATEGORY_NAME_MAX) ?? undefined,
      name_en: nameError(nameEn, CATEGORY_NAME_MAX) ?? undefined,
      price: cents === null ? "catalogPrice" : undefined,
    };
    setErrors(next);
    if (Object.values(next).some(Boolean) || cents === null) return;
    const created = await catalog.createCategory({
      name_es: cleanName(nameEs),
      name_en: cleanName(nameEn),
      suggested_price_cents: cents,
    });
    if (created) {
      setNameEs("");
      setNameEn("");
      setPrice("");
    }
  }

  const message = (key: CatalogFieldError | undefined) =>
    key ? tValidation(key, { max: CATEGORY_NAME_MAX }) : undefined;

  return (
    <Card className="space-y-4">
      <h2 className="text-card-title font-bold text-ink">{t("newCategory")}</h2>
      <form className="grid gap-4 md:grid-cols-3" onSubmit={(event) => void submit(event)} noValidate>
        <TextField
          label={t("nameEs")}
          value={nameEs}
          onChange={(event) => setNameEs(event.target.value)}
          error={message(errors.name_es)}
          required
        />
        <TextField
          label={t("nameEn")}
          value={nameEn}
          onChange={(event) => setNameEn(event.target.value)}
          error={message(errors.name_en)}
          required
        />
        <TextField
          label={t("price")}
          hint={t("priceHint")}
          value={price}
          onChange={(event) => setPrice(event.target.value)}
          error={message(errors.price)}
          inputMode="decimal"
          required
        />
        <div className="md:col-span-3">
          {/* El unico boton primario de la vista: crear es la accion principal. */}
          <Button type="submit" loading={catalog.pending === "create"}>
            {t("create")}
          </Button>
        </div>
      </form>
    </Card>
  );
}

function CategoryCard({
  category,
  catalog,
  onDelete,
}: {
  category: AdminCatalogCategory;
  catalog: AdminCatalogState;
  onDelete: (target: DeleteTarget) => void;
}) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("admin.catalog");
  const [editing, setEditing] = useState(false);
  const busy = catalog.pending === `category:${category.id}`;

  return (
    <Card className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h3 className="text-card-title font-bold text-ink">
            {category.name_es} <span className="font-normal text-muted">· {category.name_en}</span>
          </h3>
          <p className="text-help text-muted">
            {t("slug", { slug: category.slug })} ·{" "}
            {t("suggested", { amount: formatMoney(category.suggested_lead_price, locale) })} ·{" "}
            {t("order", { order: category.sort_order })}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Tag tone={category.active ? "trade" : "neutral"}>
            {category.active ? t("statusActive") : t("statusInactive")}
          </Tag>
          {!editing && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              aria-label={t("editNamed", { name: category.name_es })}
              onClick={() => setEditing(true)}
            >
              {t("edit")}
            </Button>
          )}
        </div>
      </header>

      {editing && (
        <CategoryEditForm
          category={category}
          busy={busy}
          onCancel={() => setEditing(false)}
          onSave={async (payload) => {
            if (await catalog.updateCategory(category.id, payload)) setEditing(false);
          }}
          onDelete={() => onDelete({ kind: "category", category })}
        />
      )}

      <section className="space-y-3 border-t border-divider pt-4">
        <h4 className="text-label font-semibold text-ink">
          {t("services", { count: category.services.length })}
        </h4>
        {category.services.length === 0 ? (
          <p className="text-help text-muted">{t("noServices")}</p>
        ) : (
          <ul className="space-y-2">
            {category.services.map((service) => (
              <li key={service.id}>
                <ServiceRow
                  category={category}
                  service={service}
                  catalog={catalog}
                  onDelete={() => onDelete({ kind: "service", category, service })}
                />
              </li>
            ))}
          </ul>
        )}
        <NewServiceForm category={category} catalog={catalog} />
      </section>
    </Card>
  );
}

function CategoryEditForm({
  category,
  busy,
  onCancel,
  onSave,
  onDelete,
}: {
  category: AdminCatalogCategory;
  busy: boolean;
  onCancel: () => void;
  onSave: (payload: {
    name_es: string;
    name_en: string;
    suggested_price_cents: number;
    sort_order: number;
    active: boolean;
  }) => Promise<void>;
  onDelete: () => void;
}) {
  const t = useTranslations("admin.catalog");
  const tCommon = useTranslations("common");
  const tValidation = useTranslations("validation");
  const [nameEs, setNameEs] = useState(category.name_es);
  const [nameEn, setNameEn] = useState(category.name_en);
  const [price, setPrice] = useState(priceInput(category.suggested_lead_price.amount_cents));
  const [order, setOrder] = useState(String(category.sort_order));
  const [active, setActive] = useState(category.active);
  const [errors, setErrors] = useState<Errors>({});

  async function submit(event: FormEvent) {
    event.preventDefault();
    const cents = parsePriceCents(price);
    const sortOrder = parseSortOrder(order);
    const next: Errors = {
      name_es: nameError(nameEs, CATEGORY_NAME_MAX) ?? undefined,
      name_en: nameError(nameEn, CATEGORY_NAME_MAX) ?? undefined,
      price: cents === null ? "catalogPrice" : undefined,
      sort_order: sortOrder === null ? "catalogSortOrder" : undefined,
    };
    setErrors(next);
    if (Object.values(next).some(Boolean) || cents === null || sortOrder === null) return;
    await onSave({
      name_es: cleanName(nameEs),
      name_en: cleanName(nameEn),
      suggested_price_cents: cents,
      sort_order: sortOrder,
      active,
    });
  }

  const message = (key: CatalogFieldError | undefined) =>
    key ? tValidation(key, { max: CATEGORY_NAME_MAX }) : undefined;

  return (
    <form
      className="grid gap-4 rounded-option bg-page p-4 md:grid-cols-2"
      onSubmit={(event) => void submit(event)}
      noValidate
      aria-label={t("editNamed", { name: category.name_es })}
    >
      <TextField
        label={t("nameEs")}
        value={nameEs}
        onChange={(event) => setNameEs(event.target.value)}
        error={message(errors.name_es)}
        required
      />
      <TextField
        label={t("nameEn")}
        value={nameEn}
        onChange={(event) => setNameEn(event.target.value)}
        error={message(errors.name_en)}
        required
      />
      <TextField
        label={t("price")}
        hint={t("priceHint")}
        value={price}
        onChange={(event) => setPrice(event.target.value)}
        error={message(errors.price)}
        inputMode="decimal"
        required
      />
      <TextField
        label={t("sortOrder")}
        hint={t("sortOrderHint")}
        value={order}
        onChange={(event) => setOrder(event.target.value)}
        error={message(errors.sort_order)}
        inputMode="numeric"
        required
      />
      <div className="md:col-span-2">
        <CheckboxField
          label={t("categoryActive")}
          checked={active}
          onChange={(event) => setActive(event.target.checked)}
        />
      </div>
      <div className="flex flex-wrap items-center gap-3 md:col-span-2">
        <Button type="submit" variant="secondary" loading={busy}>
          {t("save")}
        </Button>
        <Button type="button" variant="text" disabled={busy} onClick={onCancel}>
          {tCommon("cancel")}
        </Button>
        <Button type="button" variant="danger" size="sm" className="ml-auto" disabled={busy} onClick={onDelete}>
          {t("delete")}
        </Button>
      </div>
    </form>
  );
}

function ServiceRow({
  category,
  service,
  catalog,
  onDelete,
}: {
  category: AdminCatalogCategory;
  service: AdminCatalogService;
  catalog: AdminCatalogState;
  onDelete: () => void;
}) {
  const t = useTranslations("admin.catalog");
  const tCommon = useTranslations("common");
  const tValidation = useTranslations("validation");
  const [editing, setEditing] = useState(false);
  const [nameEs, setNameEs] = useState(service.name_es);
  const [nameEn, setNameEn] = useState(service.name_en);
  const [order, setOrder] = useState(String(service.sort_order));
  const [active, setActive] = useState(service.active);
  const [errors, setErrors] = useState<Errors>({});
  const busy = catalog.pending === `service:${service.id}`;

  function startEditing() {
    setNameEs(service.name_es);
    setNameEn(service.name_en);
    setOrder(String(service.sort_order));
    setActive(service.active);
    setErrors({});
    setEditing(true);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const sortOrder = parseSortOrder(order);
    const next: Errors = {
      name_es: nameError(nameEs, SERVICE_NAME_MAX) ?? undefined,
      name_en: nameError(nameEn, SERVICE_NAME_MAX) ?? undefined,
      sort_order: sortOrder === null ? "catalogSortOrder" : undefined,
    };
    setErrors(next);
    if (Object.values(next).some(Boolean) || sortOrder === null) return;
    const saved = await catalog.updateService(category.id, service.id, {
      name_es: cleanName(nameEs),
      name_en: cleanName(nameEn),
      sort_order: sortOrder,
      active,
    });
    if (saved) setEditing(false);
  }

  const message = (key: CatalogFieldError | undefined) =>
    key ? tValidation(key, { max: SERVICE_NAME_MAX }) : undefined;

  if (!editing) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-option border border-line px-4 py-3">
        <p className="text-[14.5px] text-ink">
          {service.name_es} <span className="text-muted">· {service.name_en}</span>
          {!service.active && (
            <Tag tone="neutral" className="ml-2">
              {t("serviceStatusInactive")}
            </Tag>
          )}
        </p>
        <Button
          type="button"
          variant="text"
          aria-label={t("editNamed", { name: service.name_es })}
          onClick={startEditing}
        >
          {t("edit")}
        </Button>
      </div>
    );
  }

  return (
    <form
      className="grid gap-4 rounded-option bg-page p-4 md:grid-cols-3"
      onSubmit={(event) => void submit(event)}
      noValidate
      aria-label={t("editNamed", { name: service.name_es })}
    >
      <TextField
        label={t("nameEs")}
        value={nameEs}
        onChange={(event) => setNameEs(event.target.value)}
        error={message(errors.name_es)}
        required
      />
      <TextField
        label={t("nameEn")}
        value={nameEn}
        onChange={(event) => setNameEn(event.target.value)}
        error={message(errors.name_en)}
        required
      />
      <TextField
        label={t("sortOrder")}
        value={order}
        onChange={(event) => setOrder(event.target.value)}
        error={message(errors.sort_order)}
        inputMode="numeric"
        required
      />
      <div className="md:col-span-3">
        <CheckboxField
          label={t("serviceActive")}
          checked={active}
          onChange={(event) => setActive(event.target.checked)}
        />
      </div>
      <div className="flex flex-wrap items-center gap-3 md:col-span-3">
        <Button type="submit" variant="secondary" size="sm" loading={busy}>
          {t("save")}
        </Button>
        <Button type="button" variant="text" disabled={busy} onClick={() => setEditing(false)}>
          {tCommon("cancel")}
        </Button>
        <Button type="button" variant="danger" size="sm" className="ml-auto" disabled={busy} onClick={onDelete}>
          {t("delete")}
        </Button>
      </div>
    </form>
  );
}

function NewServiceForm({
  category,
  catalog,
}: {
  category: AdminCatalogCategory;
  catalog: AdminCatalogState;
}) {
  const t = useTranslations("admin.catalog");
  const tValidation = useTranslations("validation");
  const [nameEs, setNameEs] = useState("");
  const [nameEn, setNameEn] = useState("");
  const [errors, setErrors] = useState<Errors>({});

  async function submit(event: FormEvent) {
    event.preventDefault();
    const next: Errors = {
      name_es: nameError(nameEs, SERVICE_NAME_MAX) ?? undefined,
      name_en: nameError(nameEn, SERVICE_NAME_MAX) ?? undefined,
    };
    setErrors(next);
    if (Object.values(next).some(Boolean)) return;
    const added = await catalog.createService(category.id, {
      name_es: cleanName(nameEs),
      name_en: cleanName(nameEn),
    });
    if (added) {
      setNameEs("");
      setNameEn("");
    }
  }

  const message = (key: CatalogFieldError | undefined) =>
    key ? tValidation(key, { max: SERVICE_NAME_MAX }) : undefined;

  return (
    <form
      className="grid items-end gap-3 md:grid-cols-[1fr_1fr_auto]"
      onSubmit={(event) => void submit(event)}
      noValidate
      aria-label={t("newServiceIn", { name: category.name_es })}
    >
      <TextField
        label={t("newServiceEs")}
        value={nameEs}
        onChange={(event) => setNameEs(event.target.value)}
        error={message(errors.name_es)}
      />
      <TextField
        label={t("newServiceEn")}
        value={nameEn}
        onChange={(event) => setNameEn(event.target.value)}
        error={message(errors.name_en)}
      />
      <Button
        type="submit"
        variant="secondary"
        loading={catalog.pending === `new-service:${category.id}`}
      >
        {t("addService")}
      </Button>
    </form>
  );
}
