# Instrucciones para GitHub Copilot

Las convenciones de este repositorio viven en [`AGENTS.md`](../AGENTS.md) (raíz), con
archivos más específicos en [`apps/api/AGENTS.md`](../apps/api/AGENTS.md) y
[`apps/web/AGENTS.md`](../apps/web/AGENTS.md). Léelos antes de proponer cambios.

Resumen mínimo:

- Monorepo: `apps/api` (FastAPI hexagonal, Python 3.13 + uv) y `apps/web` (Next.js 15 + pnpm).
- **Puertos: 8010 (API) y 3010 (web)**, no 8000/3000.
- `app/domain/` y `app/application/` no importan `sqlalchemy`, `fastapi`, `stripe`,
  `firebase_admin`, `boto3` ni `pydantic`. mypy corre en modo estricto sobre ambos.
- Cada solicitud se vende a un máximo de 3 profesionales. La plaza se reserva antes de
  cobrar y solo el webhook firmado de Stripe desbloquea el contacto del cliente.
- Los datos de contacto del cliente nunca salen por el explorador: `LeadPublicView` no
  tiene campos para ellos. No los añadas.
- Cero cadenas de UI incrustadas: van a `apps/web/messages/es.json` y `en.json`, con las
  mismas claves en ambos.
- Comentarios y commits en español, identificadores en inglés, código fuente ASCII.
- Antes de terminar: `pnpm lint && pnpm test`.

Procedimientos paso a paso para tareas recurrentes (son documentación legible, no solo
para Claude Code):

- `.claude/skills/verificar-flujo-compra/SKILL.md` — comprobar el flujo de compra completo.
- `.claude/skills/nueva-migracion/SKILL.md` — migraciones de Alembic sin romper nada.
- `.claude/skills/nuevo-caso-de-uso/SKILL.md` — añadir funcionalidad al backend hexagonal.
