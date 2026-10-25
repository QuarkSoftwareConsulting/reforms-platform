/** La ruta que regenera la landing: solo el admin, y solo etiquetas conocidas. */

import { beforeEach, describe, expect, it, vi } from "vitest";

const revalidateTag = vi.fn();
const meWith = vi.fn();
vi.mock("next/cache", () => ({ revalidateTag }));
vi.mock("@/services/professional.service", () => ({ professionalService: { meWith } }));

const { POST } = await import("@/app/api/revalidate/route");
const { NextRequest } = await import("next/server");

function call(body: unknown, authorization: string | null = "Bearer token") {
  const headers = new Headers({ "Content-Type": "application/json" });
  if (authorization) headers.set("authorization", authorization);
  return POST(
    new NextRequest("http://localhost/api/revalidate", {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    }),
  );
}

describe("POST /api/revalidate", () => {
  beforeEach(() => {
    revalidateTag.mockReset();
    meWith.mockReset();
  });

  it("revalidates the known tags for an admin", async () => {
    meWith.mockResolvedValue({ role: "admin" });

    const response = await call({ tags: ["catalog", "pricing", "users"] });

    expect(response.status).toBe(200);
    expect(meWith).toHaveBeenCalledWith("Bearer token");
    expect(revalidateTag.mock.calls).toEqual([["catalog"], ["pricing"]]);
  });

  it("refuses a professional", async () => {
    meWith.mockResolvedValue({ role: "professional" });
    expect((await call({ tags: ["catalog"] })).status).toBe(403);
    expect(revalidateTag).not.toHaveBeenCalled();
  });

  it("refuses without a token or with an invalid one", async () => {
    expect((await call({ tags: ["catalog"] }, null)).status).toBe(401);
    meWith.mockRejectedValue(new Error("401"));
    expect((await call({ tags: ["catalog"] })).status).toBe(401);
    expect(revalidateTag).not.toHaveBeenCalled();
  });
});
