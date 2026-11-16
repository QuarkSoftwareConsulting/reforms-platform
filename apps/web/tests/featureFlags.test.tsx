/**
 * Feature flags en el frontend.
 *
 * Lo que se vigila: una flag apagada o que no existe oculta lo que protege, y si el API
 * no responde la pagina no se rompe: todo cuenta como apagado.
 */

import { render, renderHook, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const requestMock = vi.fn();

vi.mock("@/services/api", () => ({
  request: (...args: unknown[]) => requestMock(...args),
}));

const { featureFlagsService } = await import("@/services/featureFlags.service");
const { FeatureFlagsProvider, useFeatureFlag } = await import("@/hooks/useFeatureFlag");
const { Feature } = await import("@/components/features/Feature");

function Wrapper({ children }: { children: ReactNode }) {
  return <FeatureFlagsProvider>{children}</FeatureFlagsProvider>;
}

beforeEach(() => {
  requestMock.mockReset();
});

describe("featureFlagsService", () => {
  it("reads them without a session and without the Next cache", async () => {
    requestMock.mockResolvedValue({ flags: { "new-checkout": true } });

    expect(await featureFlagsService.list()).toEqual({ "new-checkout": true });
    // Sin `revalidate`: si el layout volviera a pedirlas, regeneraria todas las paginas.
    expect(requestMock).toHaveBeenCalledWith("/feature-flags", { anonymous: true });
  });

  it("treats every flag as off when the API does not answer", async () => {
    requestMock.mockRejectedValue(new TypeError("fetch failed"));

    expect(await featureFlagsService.list()).toEqual({});
  });
});

describe("useFeatureFlag", () => {
  it("is on only when the flag is enabled", async () => {
    requestMock.mockResolvedValue({ flags: { on: true, off: false } });

    const { result } = renderHook(
      () => [useFeatureFlag("on"), useFeatureFlag("off"), useFeatureFlag("missing")],
      { wrapper: Wrapper },
    );

    // Hasta que responde el API, todo apagado.
    expect(result.current).toEqual([false, false, false]);
    // "missing" no existe en la tabla: lo nuevo nace oculto.
    await waitFor(() => expect(result.current).toEqual([true, false, false]));
  });

  it("is off outside the provider", () => {
    expect(renderHook(() => useFeatureFlag("on")).result.current).toBe(false);
  });
});

describe("Feature", () => {
  it("shows its content only with the flag on, and the fallback otherwise", async () => {
    requestMock.mockResolvedValue({ flags: { "admin.reports": true, "new-checkout": false } });

    render(
      <FeatureFlagsProvider>
        <Feature name="admin.reports">
          <p>informes</p>
        </Feature>
        <Feature name="new-checkout" fallback={<p>checkout actual</p>}>
          <p>checkout nuevo</p>
        </Feature>
      </FeatureFlagsProvider>,
    );

    expect(await screen.findByText("informes")).not.toBeNull();
    expect(screen.queryByText("checkout nuevo")).toBeNull();
    expect(screen.queryByText("checkout actual")).not.toBeNull();
  });
});
