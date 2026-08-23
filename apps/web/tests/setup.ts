import "@testing-library/dom";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// jsdom no implementa estas APIs y algunos componentes las tocan al montar.
if (!globalThis.URL.createObjectURL) {
  globalThis.URL.createObjectURL = () => "blob:test";
  globalThis.URL.revokeObjectURL = () => undefined;
}
