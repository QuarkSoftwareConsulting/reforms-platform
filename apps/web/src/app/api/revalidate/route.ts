import { revalidateTag } from "next/cache";
import { NextResponse, type NextRequest } from "next/server";

import { CACHE_TAGS, type CacheTag } from "@/helpers/cacheTags";
import { professionalService } from "@/services/professional.service";

/**
 * Regenera las paginas que usan una etiqueta de cache (catalogo, mensualidad).
 *
 * Solo el admin: se reenvia su token al API y se mira el rol de `/me`. Asi no hace falta
 * otro secreto compartido entre la web y el API.
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  const authorization = request.headers.get("authorization");
  if (!authorization) return new NextResponse(null, { status: 401 });
  try {
    const me = await professionalService.meWith(authorization);
    if (me.role !== "admin") return new NextResponse(null, { status: 403 });
  } catch {
    return new NextResponse(null, { status: 401 });
  }

  const body = (await request.json().catch(() => null)) as { tags?: unknown } | null;
  const requested = Array.isArray(body?.tags) ? body.tags : [];
  const tags = requested.filter((tag): tag is CacheTag => CACHE_TAGS.includes(tag as CacheTag));
  for (const tag of tags) revalidateTag(tag);
  return NextResponse.json({ revalidated: tags });
}
