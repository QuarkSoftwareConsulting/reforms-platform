"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { TextField } from "@/components/ui/Field";
import { useApiError } from "@/hooks/useApiError";
import { useAuth } from "@/hooks/useAuth";
import { path, type AppLocale } from "@/i18n/routing";

/**
 * Login y registro con Firebase.
 *
 * Tras autenticarse, redirige segun el estado del perfil: al explorador si ya
 * existe, o al onboarding de perfil si aun no lo ha creado.
 */
export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("auth");
  const auth = useAuth();
  const router = useRouter();
  const translateError = useApiError();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const isRegister = mode === "register";

  useEffect(() => {
    if (!auth.isAuthenticated || auth.loading) return;
    router.replace(path(locale, auth.hasProfile ? "projects" : "profile"));
  }, [auth.isAuthenticated, auth.loading, auth.hasProfile, router, locale]);

  const run = async (action: () => Promise<void>) => {
    setError(null);
    setSubmitting(true);
    try {
      await action();
      // La redireccion la hace el efecto de arriba cuando llega el perfil.
    } catch (caught) {
      setError(translateError(caught));
      setSubmitting(false);
    }
  };

  if (!auth.configured) {
    return (
      <div className="mx-auto max-w-md">
        <Alert tone="warning">{t("notConfigured")}</Alert>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md space-y-6">
      <header className="space-y-1 text-center">
        <h1 className="text-3xl font-bold text-slate-900">
          {isRegister ? t("registerTitle") : t("loginTitle")}
        </h1>
        <p className="text-slate-600">
          {isRegister ? t("registerSubtitle") : t("loginSubtitle")}
        </p>
      </header>

      <Card className="space-y-5">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void run(() =>
              isRegister
                ? auth.signUpWithEmail(email, password)
                : auth.signInWithEmail(email, password),
            );
          }}
          className="space-y-4"
        >
          <TextField
            label={t("emailLabel")}
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            autoComplete="email"
          />
          <TextField
            label={t("passwordLabel")}
            hint={isRegister ? t("passwordHint") : undefined}
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            minLength={6}
            autoComplete={isRegister ? "new-password" : "current-password"}
          />
          <Button type="submit" size="lg" fullWidth loading={submitting}>
            {isRegister ? t("submitRegister") : t("submitLogin")}
          </Button>
        </form>

        <div className="flex items-center gap-3 text-xs uppercase text-slate-400">
          <span className="h-px flex-1 bg-slate-200" />
          {t("or")}
          <span className="h-px flex-1 bg-slate-200" />
        </div>

        <Button
          type="button"
          variant="secondary"
          fullWidth
          onClick={() => void run(() => auth.signInWithGoogle())}
        >
          {t("googleLogin")}
        </Button>

        {error && <Alert tone="error">{error}</Alert>}
      </Card>

      <p className="text-center text-sm text-slate-600">
        {isRegister ? t("hasAccount") : t("noAccount")}{" "}
        <Link
          href={path(locale, isRegister ? "login" : "register")}
          className="font-semibold text-brand-700 hover:underline"
        >
          {isRegister ? t("goLogin") : t("goRegister")}
        </Link>
      </p>
    </div>
  );
}
