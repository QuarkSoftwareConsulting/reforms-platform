"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { VerificationDossierView } from "@/components/features/VerificationDossierView";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, Tag } from "@/components/ui/Card";
import { SelectField, TextAreaField, TextField } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { Pagination } from "@/components/ui/Pagination";
import { formatMoney } from "@/helpers/currency";
import { formatDate } from "@/helpers/date";
import type { VerificationStatus } from "@/helpers/professionalOptions";
import { useAdminUsers } from "@/hooks/useAdminUsers";
import { useAuth } from "@/hooks/useAuth";
import type { AppLocale } from "@/i18n/routing";
import type { AdminUser, UserRole } from "@/types/api";

const ROLES: UserRole[] = ["professional", "admin"];
const VERIFICATION_STATUSES: VerificationStatus[] = ["incomplete", "pending", "approved", "rejected"];

/**
 * Directorio de usuarios con cuenta: rol, estado del alta y de la recarga. Desde aqui
 * se da o quita el rol de admin y se abre el expediente de un profesional. El backend
 * impide cambiarse el propio rol y quitar al ultimo admin; aqui solo se avisa antes.
 */
export function AdminUsers() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("admin");
  const tSubscription = useTranslations("subscription");
  const tCommon = useTranslations("common");
  const auth = useAuth();
  const users = useAdminUsers();
  const [target, setTarget] = useState<AdminUser | null>(null);
  const [note, setNote] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const dossier = users.dossier;

  const nextRole: UserRole | null = target
    ? target.role === "admin"
      ? "professional"
      : "admin"
    : null;

  function closeModal(): void {
    setTarget(null);
    setNote("");
    users.clearRoleError();
  }

  async function confirmRoleChange(): Promise<void> {
    if (!target || !nextRole) return;
    setNotice(null);
    if (await users.changeRole(target.id, nextRole, note)) {
      closeModal();
      setNotice(t("users.roleChanged"));
    }
  }

  return (
    <Card className="space-y-4">
      <header className="space-y-1">
        <h2 className="text-h2 font-bold text-ink">{t("users.title")}</h2>
        <p className="text-help text-muted">{t("users.subtitle")}</p>
      </header>

      {users.error && <Alert tone="error">{users.error}</Alert>}
      {dossier.error && <Alert tone="error">{dossier.error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}
      {dossier.lastRejection && (
        <Alert tone="success">
          {dossier.lastRejection.refunded
            ? t("verification.rejectedRefunded", {
                amount: formatMoney(dossier.lastRejection.refunded, locale),
              })
            : t("verification.rejectedNothingToRefund")}
        </Alert>
      )}

      {dossier.dossier ? (
        <VerificationDossierView
          dossier={dossier.dossier}
          deciding={dossier.deciding}
          onApprove={dossier.approve}
          onReject={dossier.reject}
          onBack={dossier.close}
        />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <TextField
              label={t("users.search")}
              value={users.filters.query}
              onChange={(event) => users.setFilters({ ...users.filters, query: event.target.value })}
            />
            <SelectField
              label={t("users.role")}
              value={users.filters.role ?? ""}
              onChange={(event) =>
                users.setFilters({
                  ...users.filters,
                  role: (event.target.value || undefined) as UserRole | undefined,
                })
              }
            >
              <option value="">{t("users.all")}</option>
              {ROLES.map((role) => (
                <option key={role} value={role}>
                  {t(`users.roles.${role}`)}
                </option>
              ))}
            </SelectField>
            <SelectField
              label={t("users.verificationStatus")}
              value={users.filters.verificationStatus ?? ""}
              onChange={(event) =>
                users.setFilters({
                  ...users.filters,
                  verificationStatus: (event.target.value || undefined) as
                    | VerificationStatus
                    | undefined,
                })
              }
            >
              <option value="">{t("users.all")}</option>
              {VERIFICATION_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {t(`verification.status.${status}`)}
                </option>
              ))}
            </SelectField>
          </div>

          {!users.loading && users.items.length === 0 ? (
            <p className="text-secondary">{t("users.empty")}</p>
          ) : (
            <ul
              className={`divide-y divide-divider rounded-option border border-line ${users.loading ? "opacity-60" : ""}`}
              aria-busy={users.loading}
            >
              {users.items.map((user) => {
                const professional = user.professional;
                const isSelf = auth.me?.user_id === user.id;
                return (
                  <li key={user.id} className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
                    <div className="min-w-0 space-y-1">
                      <p className="flex flex-wrap items-center gap-2">
                        <span className="break-all font-semibold text-ink">{user.email}</span>
                        <Tag tone={user.role === "admin" ? "trade-dark" : "neutral"}>
                          {t(`users.roles.${user.role}`)}
                        </Tag>
                      </p>
                      <p className="text-help text-muted">
                        {professional
                          ? `${professional.business_name} · ${t(`verification.status.${professional.verification_status}`)}`
                          : t("users.noProfile")}
                      </p>
                      {professional && (
                        <p className="text-help text-muted">
                          {t("account")}:{" "}
                          {professional.account
                            ? `${tSubscription(`status.${professional.account.status}`)} · ${t("balance")} ${formatMoney(professional.account.balance, locale)}`
                            : t("noAccount")}
                        </p>
                      )}
                      <p className="text-help text-muted">
                        {t("users.since", { date: formatDate(user.created_at, locale) })}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {professional && (
                        <Button
                          type="button"
                          variant="text"
                          size="sm"
                          onClick={() => void dossier.open(professional.id)}
                        >
                          {t("users.viewDossier")}
                        </Button>
                      )}
                      {!isSelf && (
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => {
                            setNotice(null);
                            setTarget(user);
                          }}
                        >
                          {user.role === "admin" ? t("users.makeProfessional") : t("users.makeAdmin")}
                        </Button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}

          <Pagination
            page={users.page}
            pages={users.pages}
            label={t("pagination.page", { page: users.page + 1, pages: users.pages })}
            previous={t("pagination.previous")}
            next={t("pagination.next")}
            onChange={users.setPage}
          />
        </>
      )}

      <Modal
        open={target !== null}
        title={target ? t("users.confirmTitle", { email: target.email }) : ""}
        onClose={closeModal}
        dismissible={!users.changingRole}
        actions={
          <>
            <Button type="button" variant="secondary" disabled={users.changingRole} onClick={closeModal}>
              {tCommon("cancel")}
            </Button>
            <Button type="button" loading={users.changingRole} onClick={() => void confirmRoleChange()}>
              {t("users.confirm")}
            </Button>
          </>
        }
      >
        <p>{nextRole === "admin" ? t("users.confirmPromote") : t("users.confirmDemote")}</p>
        {users.roleError && <Alert tone="error">{users.roleError}</Alert>}
        <TextAreaField
          label={t("users.noteLabel")}
          hint={t("users.noteHint")}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          maxLength={500}
        />
      </Modal>
    </Card>
  );
}
