/**
 * Feature flags en el frontend.
 *
 * Lo que se vigila: una flag apagada o que no existe oculta lo que protege, y si el API
 * no responde la pagina (o el build) no se rompe: todo cuenta como apagado.
 */

import { render, renderHook, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const requestMock = vi.fn();

vi.mock("@/services/api", () => ({
  request: (...args: unknown[]) => requestMock(...args),
}));

const { featureFlagsService } = await import("@/services/featureFlags.service");
const { FeatureFlagsProvider, useFeatureFlag } = await import("@/hooks/useFeatureFlag");
const { Feature } = await import("@/components/features/Feature");

function withFlags(flags: Record<string, boolean>) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <FeatureFlagsProvider flags={flags}>{children}</FeatureFlagsProvider>;
  };
}

describe("featureFlagsService", () => {
  beforeEach(() => {
    requestMock.mockReset();
  });

  it("reads them without a session and cached for a minute", async () => {
    requestMock.mockResolvedValue({ flags: { "new-checkout": true } });

    expect(await featureFlagsService.list()).toEqual({ "new-checkout": true });
    expect(requestMock).toHaveBeenCalledWith("/feature-flags", {
      anonymous: true,
      revalidate: 60,
    });
  });

  it("treats every flag as off when the API does not answer", async () => {
    requestMock.mockRejectedValue(new TypeError("fetch failed"));

    expect(await featureFlagsService.list()).toEqual({});
  });
});

describe("useFeatureFlag", () => {
  it("is on only when the flag is enabled", () => {
    const wrapper = withFlags({ on: true, off: false });

    expect(renderHook(() => useFeatureFlag("on"), { wrapper }).result.current).toBe(true);
    expect(renderHook(() => useFeatureFlag("off"), { wrapper }).result.current).toBe(false);
    // No existe en la tabla: lo nuevo nace oculto.
    expect(renderHook(() => useFeatureFlag("missing"), { wrapper }).result.current).toBe(false);
  });

  it("is off outside the provider", () => {
    expect(renderHook(() => useFeatureFlag("on")).result.current).toBe(false);
  });
});

describe("Feature", () => {
  it("shows its content only with the flag on, and the fallback otherwise", () => {
    render(
      <FeatureFlagsProvider flags={{ "admin.reports": true, "new-checkout": false }}>
        <Feature name="admin.reports">
          <p>informes</p>
        </Feature>
        <Feature name="new-checkout" fallback={<p>checkout actual</p>}>
          <p>checkout nuevo</p>
        </Feature>
      </FeatureFlagsProvider>,
    );

    expect(screen.queryByText("informes")).not.toBeNull();
    expect(screen.queryByText("checkout nuevo")).toBeNull();
    expect(screen.queryByText("checkout actual")).not.toBeNull();
  });
});
