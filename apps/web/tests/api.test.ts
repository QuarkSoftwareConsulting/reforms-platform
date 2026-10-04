/** Tests del cliente HTTP: cabeceras, token y traduccion de errores. */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, request, setTokenProvider } from "@/services/api";

const fetchMock = vi.fn();

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api client", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    setTokenProvider(async () => "token-abc");
  });

  it("attaches the bearer token and the language header", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));

    await request("/leads", { locale: "en" });

    const [, init] = fetchMock.mock.calls[0]!;
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer token-abc");
    expect(headers["Accept-Language"]).toBe("en");
  });

  it("omits the token on anonymous requests", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));

    await request("/leads", { method: "POST", body: { a: 1 }, anonymous: true });

    const [, init] = fetchMock.mock.calls[0]!;
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("retries once with a refreshed token on 401", async () => {
    const refreshCalls: (boolean | undefined)[] = [];
    setTokenProvider(async (forceRefresh) => {
      refreshCalls.push(forceRefresh);
      return "token-abc";
    });

    fetchMock
      .mockResolvedValueOnce(jsonResponse({ code: "UNAUTHENTICATED", message: "x" }, 401))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));

    await request("/leads");

    expect(fetchMock).toHaveBeenCalledTimes(2);
    // La segunda vez se fuerza la renovacion del token.
    expect(refreshCalls).toEqual([false, true]);
  });

  it("does not retry forever on a persistent 401", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ code: "UNAUTHENTICATED", message: "expired" }, 401));

    await expect(request("/leads")).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("preserves the backend error code", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ code: "LEAD_CAP_REACHED", message: "full" }, 409));

    await expect(request("/leads/x/purchase", { method: "POST" })).rejects.toMatchObject({
      code: "LEAD_CAP_REACHED",
      status: 409,
    });
  });

  it.each([
    [502, "SERVICE_UNAVAILABLE"],
    [503, "SERVICE_UNAVAILABLE"],
    [413, "PAYLOAD_TOO_LARGE"],
    [429, "TOO_MANY_REQUESTS"],
    [404, "UNEXPECTED_RESPONSE"],
  ])("names a %i without the backend's JSON after its status", async (status, code) => {
    // La escribe un proxy o el balanceador, no nuestra API: no trae `code`.
    fetchMock.mockResolvedValue(new Response("<html>error</html>", { status }));

    const error = await request("/leads").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe(code);
  });

  it("flags 4xx errors as business errors", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ code: "VALIDATION_ERROR", message: "" }, 422));
    const error = (await request("/leads").catch((caught: unknown) => caught)) as ApiError;

    expect(error.isBusinessError).toBe(true);
  });

  it("returns undefined for 204 responses", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(request("/leads/x")).resolves.toBeUndefined();
  });
});
