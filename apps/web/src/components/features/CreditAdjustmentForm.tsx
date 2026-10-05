"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { SelectField, TextAreaField, TextField } from "@/components/ui/Field";
import type { AdjustmentDirection } from "@/helpers/credit";
import { formatMoney } from "@/helpers/currency";
import { useCreditAdjustment } from "@/hooks/useCreditAdjustment";
import type { AppLocale } from "@/i18n/routing";
import type { AdminAccount } from "@/types/api";

/**
 * Abono o cargo manual de saldo, con nota obligatoria (queda en el libro).
 *
 * Es la via para compensar una compra reembolsada (4.6) o regularizar una deuda
 * por una recarga devuelta: un abono salda primero la deuda.
 */
export function CreditAdjustmentForm({
  professionalId,
  onAdjusted,
}: {
  professionalId: string;
  onAdjusted: (account: AdminAccount) => void;
}) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("admin.adjustment");
  const adjustment = useCreditAdjustment(professionalId);
  const [direction, setDirection] = useState<AdjustmentDirection>("credit");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [done, setDone] = useState<AdminAccount | null>(null);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setDone(null);
    const account = await adjustment.submit(direction, amount, note);
    if (account) {
      setAmount("");
      setNote("");
      setDone(account);
      onAdjusted(account);
    }
  };

  return (
    <details className="rounded-control border border-line p-3">
      <summary className="cursor-pointer text-sm font-semibold text-brand">{t("open")}</summary>
      <form className="mt-3 space-y-3" onSubmit={(event) => void onSubmit(event)} noValidate>
        <SelectField
          label={t("direction")}
          value={direction}
          onChange={(event) => setDirection(event.target.value as AdjustmentDirection)}
        >
          <option value="credit">{t("credit")}</option>
          <option value="debit">{t("debit")}</option>
        </SelectField>
        <TextField
          label={t("amount")}
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          inputMode="decimal"
          required
        />
        <TextAreaField
          label={t("note")}
          hint={t("noteHint")}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          maxLength={500}
          required
        />
        {adjustment.error && <Alert tone="error">{adjustment.error}</Alert>}
        {done && (
          <Alert tone="info">
            {done.debt
              ? t("doneWithDebt", {
                  balance: formatMoney(done.balance, locale),
                  debt: formatMoney(done.debt, locale),
                })
              : t("done", { balance: formatMoney(done.balance, locale) })}
          </Alert>
        )}
        <Button type="submit" variant="secondary" loading={adjustment.pending}>
          {t("submit")}
        </Button>
      </form>
    </details>
  );
}
