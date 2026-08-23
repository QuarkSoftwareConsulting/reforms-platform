/**
 * Cliente HTTP base.
 *
 * Adjunta el ID token de Firebase, traduce los errores del API a `ApiError` con su
 * `code` estable (que la UI convierte en mensaje traducido) y reintenta una sola
 * vez ante un 401 forzando la renovacion del token.
 */

import type { ApiErrorBody, Locale } from "@/types/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";
const API_PREFIX = "/api/v1";

/** Error del API con el codigo de negocio que devuelve el backend. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown> | null;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message || body.code);
    this.name = "ApiError";
    this.code = body.code;
    this.status = status;
    this.details = body.details ?? null;
  }

  /** True si el error se resuelve cambiando algo en la UI, no reintentando. */
  get isBusinessError(): boolean {
    return this.status >= 400 && this.status < 500;
  }
}

/** Obtiene el ID token actual. Lo inyecta `useAuth`; en SSR no hay ninguno. */
export type TokenProvider = (forceRefresh?: boolean) => Promise<string | null>;

let tokenProvider: TokenProvider = async () => null;

export function setTokenProvider(provider: TokenProvider): void {
  tokenProvider = provider;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  locale?: Locale;
  /** Peticion publica: no adjunta ni exige token (formulario del cliente). */
  anonymous?: boolean;
  signal?: AbortSignal;
  /** Revalidacion de Next para peticiones desde Server Components. */
  revalidate?: number | false;
}

async function buildHeaders(options: RequestOptions, forceRefresh: boolean): Promise<HeadersInit> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Accept-Language": options.locale ?? "es",
  };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (!options.anonymous) {
    const token = await tokenProvider(forceRefresh);
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }
  return headers;
}

async function parseError(response: Response): Promise<ApiError> {
  let body: ApiErrorBody = { code: "NETWORK_ERROR", message: response.statusText };
  try {
    const parsed = (await response.json()) as Partial<ApiErrorBody>;
    if (parsed && typeof parsed.code === "string") {
      body = { code: parsed.code, message: parsed.message ?? "", details: parsed.details ?? null };
    }
  } catch {
    // Respuesta sin JSON (proxy caido, 502...): se queda el error genérico.
  }
  return new ApiError(response.status, body);
}

async function send<T>(path: string, options: RequestOptions, retried: boolean): Promise<T> {
  const response = await fetch(`${API_URL}${API_PREFIX}${path}`, {
    method: options.method ?? "GET",
    headers: await buildHeaders(options, retried),
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
    cache: options.revalidate === undefined ? "no-store" : undefined,
    next: options.revalidate === undefined ? undefined : { revalidate: options.revalidate || 0 },
  });

  if (response.status === 401 && !retried && !options.anonymous) {
    // El token pudo caducar entre el render y la peticion: se renueva y reintenta.
    return send<T>(path, options, true);
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return send<T>(path, options, false);
}

export const apiBaseUrl = `${API_URL}${API_PREFIX}`;
