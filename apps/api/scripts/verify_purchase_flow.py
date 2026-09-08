#!/usr/bin/env python
"""Verificacion end-to-end del flujo de compra de un contacto.

Ejercita el recorrido completo contra los servicios REALES que hay en local
(Postgres+PostGIS, emulador de Firebase Auth, adaptador de Stripe) en vez de
fakes, porque los fakes no detectan los desajustes con los SDK: el bug de
`event.data.object` (un StripeObject, no un dict) sobrevivio a toda la suite
unitaria y solo aparecio aqui.

Uso:
    pnpm verify:flow                    # desde la raiz del repo
    pnpm verify:flow -- --keep          # no borra los datos de prueba
    pnpm verify:flow -- --verbose       # muestra los cuerpos de las respuestas
    uv run python -m scripts.verify_purchase_flow   # desde apps/api

Requiere: `pnpm infra:up`, `pnpm api:dev` y el emulador de Firebase Auth.
Sale con codigo 1 en el primer fallo.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import httpx

API_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = API_ROOT / ".env"

CLIENT_NAME = "Verificacion Automatica"
CLIENT_PHONE = "+34611000999"
CLIENT_EMAIL = "verificacion@example.test"
POSTAL_CODE = "28001"
DESCRIPTION = (
    "Lead creado por scripts/verify_purchase_flow.py para comprobar el flujo "
    "de compra de punta a punta. Se borra al terminar."
)

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


class VerificationError(AssertionError):
    """Un paso de la verificacion no cumplio lo que se espera del sistema."""


# --------------------------------------------------------------------------
# Utilidades de salida
# --------------------------------------------------------------------------


@dataclass
class Report:
    passed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def ok(self, message: str) -> None:
        self.passed.append(message)
        print(f"  {GREEN}OK{RESET}   {message}")

    def skip(self, message: str, reason: str) -> None:
        self.skipped.append(f"{message} ({reason})")
        print(f"  {YELLOW}SKIP{RESET} {message}{DIM} — {reason}{RESET}")

    def step(self, title: str) -> None:
        print(f"\n{title}")

    def detail(self, message: str) -> None:
        print(f"       {DIM}{message}{RESET}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def load_env(path: Path) -> dict[str, str]:
    """Lee el .env del backend para no duplicar configuracion en este script."""
    if not path.exists():
        raise VerificationError(f"No existe {path}. Crealo con: cp .env.example apps/api/.env")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        values[key.strip()] = raw.strip().strip('"').strip("'")
    return values


# --------------------------------------------------------------------------
# Clientes
# --------------------------------------------------------------------------


class Emulator:
    """Cliente del emulador de Firebase Auth (no necesita service account)."""

    def __init__(self, client: httpx.AsyncClient, host: str, api_key: str) -> None:
        # El host llega como "127.0.0.1:9099" o "http://127.0.0.1:9099".
        base = host if host.startswith("http") else f"http://{host}"
        self._url = f"{base.rstrip('/')}/identitytoolkit.googleapis.com/v1"
        self._client = client
        self._key = api_key

    async def is_up(self) -> bool:
        try:
            await self._client.get(self._url, timeout=2.0)
        except httpx.HTTPError:
            return False
        return True

    async def sign_up(self, email: str, password: str = "verificacion123") -> str:
        response = await self._client.post(
            f"{self._url}/accounts:signUp?key={self._key}",
            json={"email": email, "password": password, "returnSecureToken": True},
        )
        require(
            response.status_code == 200,
            f"El emulador rechazo el registro de {email}: {response.text}",
        )
        return str(response.json()["idToken"])

    async def sign_up_admin(self, email: str, password: str = "verificacion123") -> str:
        """Registra un usuario con el custom claim `admin`.

        El rol de admin no vive en nuestra BD: lo decide un custom claim de
        Firebase. El emulador permite fijarlo con su API privilegiada, donde
        cualquier bearer vale porque no valida el token.
        """
        created = await self._client.post(
            f"{self._url}/accounts:signUp?key={self._key}",
            json={"email": email, "password": password, "returnSecureToken": True},
        )
        require(
            created.status_code == 200,
            f"El emulador rechazo el registro de {email}: {created.text}",
        )
        uid = created.json()["localId"]

        updated = await self._client.post(
            f"{self._url}/accounts:update",
            json={"localId": uid, "customAttributes": json.dumps({"admin": True})},
            headers={"Authorization": "Bearer owner"},
        )
        require(
            updated.status_code == 200,
            f"No se pudo fijar el claim de admin: {updated.text}",
        )

        # El token del registro se emitio antes del claim: hay que reautenticar.
        signed_in = await self._client.post(
            f"{self._url}/accounts:signInWithPassword?key={self._key}",
            json={"email": email, "password": password, "returnSecureToken": True},
        )
        require(
            signed_in.status_code == 200,
            f"No se pudo reautenticar al admin: {signed_in.text}",
        )
        return str(signed_in.json()["idToken"])


class Api:
    """Cliente del API con salida legible para diagnosticar fallos."""

    def __init__(self, client: httpx.AsyncClient, base_url: str, verbose: bool) -> None:
        self._client = client
        self._base = f"{base_url.rstrip('/')}/api/v1"
        self._verbose = verbose

    async def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json_body: Any | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        expect: int | tuple[int, ...] | None = None,
    ) -> httpx.Response:
        request_headers = dict(headers or {})
        if token:
            request_headers["Authorization"] = f"Bearer {token}"

        response = await self._client.request(
            method,
            f"{self._base}{path}",
            json=json_body,
            content=content,
            headers=request_headers,
        )
        if self._verbose:
            print(
                f"       {DIM}{method} {path} -> {response.status_code} "
                f"{response.text[:300]}{RESET}"
            )
        if expect is not None:
            allowed = (expect,) if isinstance(expect, int) else expect
            require(
                response.status_code in allowed,
                f"{method} {path} devolvio {response.status_code}, se esperaba "
                f"{allowed}. Cuerpo: {response.text[:400]}",
            )
        return response


# --------------------------------------------------------------------------
# Pasos de la verificacion
# --------------------------------------------------------------------------


def sign_stripe_event(payload: str, secret: str) -> str:
    """Construye la cabecera Stripe-Signature igual que la firma Stripe.

    Es solo un HMAC-SHA256 de "timestamp.payload", asi que podemos emitir
    eventos autenticos sin cuenta de Stripe y ejercitar el adaptador real.
    """
    timestamp = int(time.time())
    signature = hmac.new(
        secret.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


def checkout_completed_event(purchase_id: str, session_id: str, event_id: str) -> str:
    return json.dumps(
        {
            "id": event_id,
            "object": "event",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "object": "checkout.session",
                    "payment_intent": f"pi_verify_{uuid.uuid4().hex[:12]}",
                    "amount_total": 500,
                    "currency": "eur",
                    "metadata": {"purchase_id": purchase_id},
                }
            },
        },
        separators=(",", ":"),
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8010")
    parser.add_argument("--api-key", default="demo-api-key", help="apiKey del emulador")
    parser.add_argument("--keep", action="store_true", help="no borrar los datos de prueba")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    env = load_env(ENV_FILE)
    report = Report()
    run_id = uuid.uuid4().hex[:8]
    created_lead_ids: list[str] = []
    created_emails: list[str] = []

    dsn = env.get("DATABASE_URL", "").replace("+asyncpg", "")
    require(bool(dsn), "Falta DATABASE_URL en apps/api/.env")
    webhook_secret = env.get("STRIPE_WEBHOOK_SECRET", "")
    require(bool(webhook_secret), "Falta STRIPE_WEBHOOK_SECRET en apps/api/.env")
    stripe_key = env.get("STRIPE_SECRET_KEY", "")
    # Una clave de plantilla no sirve para hablar con Stripe de verdad.
    stripe_configured = bool(re.fullmatch(r"sk_(test|live)_[A-Za-z0-9]{10,}", stripe_key))

    print(f"{DIM}run {run_id} · API {args.base_url}{RESET}")

    async with httpx.AsyncClient(timeout=20.0) as client:
        api = Api(client, args.base_url, args.verbose)
        emulator = Emulator(
            client, env.get("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099"), args.api_key
        )
        db = await asyncpg.connect(dsn)

        try:
            # ---------------- 0. Requisitos previos ----------------------
            report.step("0 · Requisitos previos")
            health = await api._client.get(f"{args.base_url}/health", timeout=5.0)
            require(
                health.status_code == 200 and health.json().get("database") is True,
                f"El API no responde o no ve la BD en {args.base_url}/health. "
                "Arrancalo con: pnpm api:dev",
            )
            report.ok("API arriba y conectada a Postgres")

            require(
                await emulator.is_up(),
                "El emulador de Firebase Auth no responde. Arrancalo con:\n"
                "  npx -y firebase-tools emulators:start --only auth "
                "--project reforma-hub-dev --config infra/firebase.json",
            )
            report.ok("Emulador de Firebase Auth arriba")

            categories = (await api.request("GET", "/categories", expect=200)).json()
            require(
                len(categories) > 0,
                "No hay categorias. Carga las semillas con: pnpm api:seed",
            )
            category = next(c for c in categories if c["slug"] == "carpinteria")
            report.ok(f"Catalogo cargado ({len(categories)} oficios)")

            # ---------------- 1. El cliente publica ----------------------
            report.step("1 · El cliente publica una solicitud (sin cuenta)")
            created = (
                await api.request(
                    "POST",
                    "/leads",
                    json_body={
                        "category_id": category["id"],
                        "title": f"[verify {run_id}] Reparar armario de cocina",
                        "description": DESCRIPTION,
                        "postal_code": POSTAL_CODE,
                        "client_name": CLIENT_NAME,
                        "client_phone": CLIENT_PHONE,
                        "client_email": CLIENT_EMAIL,
                        "photo_keys": [],
                        "consent": {"accepted": True},
                    },
                    expect=201,
                )
            ).json()
            lead_id = created["id"]
            created_lead_ids.append(lead_id)
            require(created["status"] == "published", "El lead no quedo publicado")
            require(created["city"] == "Madrid", f"CP {POSTAL_CODE} no resolvio a Madrid")
            report.ok(f"Lead publicado y geolocalizado en {created['city']}")

            rejected = await api.request(
                "POST",
                "/leads",
                json_body={
                    "category_id": category["id"],
                    "title": f"[verify {run_id}] sin consentimiento",
                    "description": DESCRIPTION,
                    "postal_code": POSTAL_CODE,
                    "client_name": CLIENT_NAME,
                    "client_phone": CLIENT_PHONE,
                    "client_email": None,
                    "photo_keys": [],
                    "consent": {"accepted": False},
                },
                expect=422,
            )
            require(
                rejected.json()["code"] == "CONSENT_REQUIRED",
                f"Sin consentimiento se esperaba CONSENT_REQUIRED, llego "
                f"{rejected.json().get('code')}",
            )
            report.ok("Publicar sin consentimiento se rechaza (CONSENT_REQUIRED)")

            # ---------------- 2. Consentimiento auditable ----------------
            report.step("2 · Registro auditable del consentimiento (RGPD)")
            consent = await db.fetchrow(
                "SELECT policy_version, ip_address, user_agent, max_recipients "
                "FROM lead_consents WHERE lead_id = $1",
                uuid.UUID(lead_id),
            )
            assert consent is not None, "No se registro el consentimiento del cliente"
            require(
                bool(consent["ip_address"]),
                "El consentimiento no guardo la IP (debe venir del servidor)",
            )
            require(
                bool(consent["user_agent"]),
                "El consentimiento no guardo el user-agent",
            )
            report.ok(
                f"Consentimiento auditado: politica {consent['policy_version']}, "
                f"IP {consent['ip_address']}, {consent['max_recipients']} destinatarios"
            )

            # ---------------- 3. El profesional se registra --------------
            report.step("3 · El profesional se registra y completa su perfil")

            async def register_professional(label: str) -> tuple[str, uuid.UUID]:
                """Crea cuenta en el emulador + perfil, y devuelve token e id."""
                email = f"verify-{run_id}-{label}@example.test"
                created_emails.append(email)
                new_token = await emulator.sign_up(email)
                created_profile = (
                    await api.request(
                        "PUT",
                        "/me/professional",
                        token=new_token,
                        json_body={
                            "business_name": f"{label} Verify {run_id}",
                            "phone": "+34600111222",
                            "postal_code": POSTAL_CODE,
                            "service_radius_km": 25,
                            "category_ids": [category["id"]],
                        },
                        expect=200,
                    )
                ).json()
                return new_token, uuid.UUID(created_profile["id"])

            first_email = f"verify-{run_id}-comprador@example.test"
            created_emails.append(first_email)
            token = await emulator.sign_up(first_email)

            me = (await api.request("GET", "/me", token=token, expect=200)).json()
            require(
                me["email"] == first_email,
                f"El backend no verifico el ID token de Firebase: {me}",
            )
            require(
                me["professional"] is None,
                "Una cuenta nueva no deberia tener perfil profesional",
            )
            report.ok("ID token de Firebase verificado por el backend")

            profile = (
                await api.request(
                    "PUT",
                    "/me/professional",
                    token=token,
                    json_body={
                        "business_name": f"comprador Verify {run_id}",
                        "phone": "+34600111222",
                        "postal_code": POSTAL_CODE,
                        "service_radius_km": 25,
                        "category_ids": [category["id"]],
                    },
                    expect=200,
                )
            ).json()
            report.ok(
                f"Perfil creado en {profile['city']} con radio {profile['service_radius_km']} km"
            )

            # ---------------- 4. El explorador oculta la PII -------------
            report.step("4 · El explorador muestra el lead SIN datos de contacto")
            listing = await api.request("GET", "/leads", token=token, expect=200)
            body = listing.text
            for pii in (CLIENT_NAME, CLIENT_PHONE, CLIENT_EMAIL):
                require(
                    pii not in body,
                    f"FUGA DE PII: el explorador expuso {pii!r}",
                )
            item = next((i for i in listing.json()["items"] if i["id"] == lead_id), None)
            assert item is not None, "El lead publicado no aparece en el explorador"
            require(
                item["remaining_slots"] == 3,
                f"Se esperaban 3 plazas libres, hay {item['remaining_slots']}",
            )
            report.ok("Sin nombre, telefono ni email en el listado")
            report.ok(
                f"Datos visibles: {item['city']}, {item['distance_km']} km, "
                f"{item['price']['formatted']}, {item['remaining_slots']} plazas"
            )

            detail = (await api.request("GET", f"/leads/{lead_id}", token=token, expect=200)).json()
            require(detail["is_unlocked"] is False, "El detalle llego desbloqueado")
            require(detail["contact"] is None, "FUGA DE PII: el detalle trajo contacto")
            report.ok("El detalle mantiene el contacto bloqueado antes de pagar")

            # ---------------- 5. Reserva de plaza ------------------------
            report.step("5 · Reserva de plaza antes de cobrar")
            if stripe_configured:
                purchase = (
                    await api.request(
                        "POST",
                        f"/leads/{lead_id}/purchase",
                        token=token,
                        expect=201,
                    )
                ).json()
                purchase_id = purchase["purchase_id"]
                require(
                    purchase["checkout_url"].startswith("https://"),
                    "Stripe no devolvio una URL de checkout valida",
                )
                report.ok("Sesion de checkout creada en Stripe (clave de test real)")
                session_id = (
                    await db.fetchval(
                        "SELECT stripe_checkout_session_id FROM lead_purchases WHERE id = $1",
                        uuid.UUID(purchase_id),
                    )
                    or f"cs_verify_{run_id}"
                )
            else:
                # Sin clave real, POST /purchase devuelve 503 y libera la plaza (eso
                # tambien se verifica). Para poder seguir con el webhook se inserta
                # la reserva que habria creado el checkout.
                failed = await api.request(
                    "POST", f"/leads/{lead_id}/purchase", token=token, expect=503
                )
                require(
                    failed.json()["code"] == "PAYMENT_GATEWAY_ERROR",
                    f"Sin clave de Stripe se esperaba PAYMENT_GATEWAY_ERROR, llego "
                    f"{failed.json().get('code')}",
                )
                freed = await db.fetchval(
                    "SELECT count(*) FROM lead_purchases WHERE lead_id = $1 "
                    "AND status IN ('reserved','paid','refunded')",
                    uuid.UUID(lead_id),
                )
                require(
                    freed == 0,
                    "Tras fallar la pasarela la plaza siguio ocupada: un fallo de "
                    "infraestructura no debe consumir una de las 3 plazas",
                )
                report.ok("Fallo de pasarela devuelve 503 y libera la plaza al instante")
                report.skip(
                    "Creacion de la sesion de Stripe Checkout",
                    "sin STRIPE_SECRET_KEY de test",
                )

                purchase_id = str(uuid.uuid4())
                session_id = f"cs_verify_{run_id}"
                professional_id = uuid.UUID(profile["id"])
                await db.execute(
                    """
                    INSERT INTO lead_purchases (
                        id, lead_id, professional_id, amount_cents, currency, status,
                        reserved_until, stripe_checkout_session_id, created_at, updated_at
                    ) VALUES ($1, $2, $3, 500, 'EUR', 'reserved',
                              now() + interval '30 minutes', $4, now(), now())
                    """,
                    uuid.UUID(purchase_id),
                    uuid.UUID(lead_id),
                    professional_id,
                    session_id,
                )
                report.detail("reserva insertada directamente para seguir con el webhook")

            # ---------------- 6. El webhook desbloquea -------------------
            report.step("6 · Solo el webhook firmado desbloquea el contacto")
            still_locked = (
                await api.request("GET", f"/leads/{lead_id}", token=token, expect=200)
            ).json()
            require(
                still_locked["is_unlocked"] is False,
                "El contacto se desbloqueo sin confirmacion de pago",
            )
            report.ok("Con la reserva creada, el contacto sigue bloqueado")

            forged = await api.request(
                "POST",
                "/webhooks/stripe",
                content=b'{"id":"evt_forjado","type":"checkout.session.completed"}',
                headers={
                    "Stripe-Signature": "t=1,v1=deadbeef",
                    "Content-Type": "application/json",
                },
                expect=401,
            )
            require(
                forged.json()["code"] == "UNAUTHENTICATED",
                "Una firma forjada deberia dar UNAUTHENTICATED",
            )
            report.ok("Webhook con firma forjada rechazado (401)")

            event_id = f"evt_verify_{run_id}"
            payload = checkout_completed_event(purchase_id, session_id, event_id)
            signature = sign_stripe_event(payload, webhook_secret)
            first = (
                await api.request(
                    "POST",
                    "/webhooks/stripe",
                    content=payload.encode(),
                    headers={
                        "Stripe-Signature": signature,
                        "Content-Type": "application/json",
                    },
                    expect=200,
                )
            ).json()
            require(
                first["handled"] is True,
                f"El webhook firmado no se proceso: {first}",
            )
            report.ok("Webhook firmado procesado (adaptador real de Stripe)")

            # ---------------- 7. Idempotencia ---------------------------
            report.step("7 · Idempotencia ante reenvio de Stripe")
            replay = (
                await api.request(
                    "POST",
                    "/webhooks/stripe",
                    content=payload.encode(),
                    headers={
                        "Stripe-Signature": signature,
                        "Content-Type": "application/json",
                    },
                    expect=200,
                )
            ).json()
            require(
                replay["duplicate"] is True and replay["handled"] is False,
                f"El reenvio deberia marcarse como duplicado: {replay}",
            )
            count = await db.fetchval(
                "SELECT purchases_count FROM leads WHERE id = $1", uuid.UUID(lead_id)
            )
            require(
                count == 1,
                f"El contador del lead se incremento {count} veces con un solo pago",
            )
            report.ok("Reenvio marcado como duplicado y contador incrementado una vez")

            # ---------------- 8. Contacto desbloqueado ------------------
            report.step("8 · El contacto queda desbloqueado para quien pago")
            unlocked = (
                await api.request("GET", f"/leads/{lead_id}", token=token, expect=200)
            ).json()
            require(unlocked["is_unlocked"] is True, "El pago no desbloqueo el contacto")
            require(
                unlocked["contact"]["phone"] == CLIENT_PHONE,
                f"El telefono desbloqueado no coincide: {unlocked['contact']}",
            )
            require(
                unlocked["lead"]["remaining_slots"] == 2,
                f"Tras una venta deberian quedar 2 plazas, quedan "
                f"{unlocked['lead']['remaining_slots']}",
            )
            report.ok("Contacto completo visible y una plaza consumida")

            history = (await api.request("GET", "/me/purchases", token=token, expect=200)).json()
            entry = next((e for e in history if e["lead_id"] == lead_id), None)
            assert entry is not None, "La compra no aparece en el historial"
            require(
                entry["purchase"]["status"] == "paid" and entry["is_unlocked"],
                f"La entrada del historial no refleja el pago: {entry['purchase']}",
            )
            report.ok("La compra aparece como pagada en 'Mis contactos'")

            # ---------------- 9. Otro profesional no ve la PII ----------
            report.step("9 · La compra de uno no desbloquea para otro")
            other_token, other_professional_id = await register_professional("segundo")
            other_detail = (
                await api.request("GET", f"/leads/{lead_id}", token=other_token, expect=200)
            ).json()
            require(
                other_detail["is_unlocked"] is False and other_detail["contact"] is None,
                "FUGA DE PII: otro profesional vio el contacto sin pagarlo",
            )
            report.ok("El segundo profesional sigue viendo el contacto bloqueado")

            # ---------------- 10. Lead capping --------------------------
            report.step("10 · El lead se agota a las 3 compras")
            # Ya hay 1 venta pagada (la del webhook). Se rellenan las 2 restantes con
            # profesionales distintos: el indice unico parcial impide que un mismo
            # profesional ocupe dos plazas del mismo lead.
            _, third_professional_id = await register_professional("tercero")
            for index, professional in enumerate(
                (other_professional_id, third_professional_id), start=2
            ):
                await db.execute(
                    """
                    INSERT INTO lead_purchases (
                        id, lead_id, professional_id, amount_cents, currency, status,
                        paid_at, stripe_checkout_session_id, created_at, updated_at
                    ) VALUES ($1, $2, $3, 500, 'EUR', 'paid', now(), $4, now(), now())
                    """,
                    uuid.uuid4(),
                    uuid.UUID(lead_id),
                    professional,
                    f"cs_verify_{run_id}_{index}",
                )
            await db.execute(
                """
                UPDATE leads
                SET purchases_count = (
                        SELECT count(*) FROM lead_purchases
                        WHERE lead_id = $1 AND status IN ('paid','refunded')
                    )
                WHERE id = $1
                """,
                uuid.UUID(lead_id),
            )
            await db.execute(
                "UPDATE leads SET status = 'exhausted' "
                "WHERE id = $1 AND purchases_count >= max_purchases",
                uuid.UUID(lead_id),
            )
            sold = await db.fetchval(
                "SELECT purchases_count FROM leads WHERE id = $1", uuid.UUID(lead_id)
            )
            require(
                sold == 3,
                f"El escenario del cap necesita 3 ventas registradas, hay {sold}",
            )
            report.ok("Tres plazas vendidas: el lead queda agotado")

            fourth_token, _ = await register_professional("sobrante")
            capped = await api.request(
                "POST", f"/leads/{lead_id}/purchase", token=fourth_token, expect=409
            )
            require(
                capped.json()["code"] == "LEAD_CAP_REACHED",
                f"Se esperaba LEAD_CAP_REACHED, llego {capped.json().get('code')}",
            )
            report.ok("El profesional que sobra recibe 409 LEAD_CAP_REACHED")

            exhausted_listing = (
                await api.request("GET", "/leads", token=fourth_token, expect=200)
            ).json()
            require(
                all(i["id"] != lead_id for i in exhausted_listing["items"]),
                "Un lead agotado sigue apareciendo en el explorador",
            )
            report.ok("El lead agotado desaparece del explorador")

            # ---------------- 11. Precio por lead (solo admin) ----------
            report.step("11 · El admin fija el precio de un contacto")
            priced = (
                await api.request(
                    "POST",
                    "/leads",
                    json_body={
                        "category_id": category["id"],
                        "title": f"[verify {run_id}] Lead con precio propio",
                        "description": DESCRIPTION,
                        "postal_code": POSTAL_CODE,
                        "client_name": CLIENT_NAME,
                        "client_phone": CLIENT_PHONE,
                        "client_email": None,
                        "photo_keys": [],
                        "consent": {"accepted": True},
                    },
                    expect=201,
                )
            ).json()
            created_lead_ids.append(priced["id"])

            # Un profesional no puede tocar precios aunque conozca la ruta.
            forbidden = await api.request(
                "GET", f"/admin/leads/{priced['id']}/price", token=token, expect=403
            )
            require(
                forbidden.json()["code"] == "PERMISSION_DENIED",
                f"Sin rol admin se esperaba PERMISSION_DENIED, llego "
                f"{forbidden.json().get('code')}",
            )
            report.ok("Un profesional recibe 403 en los endpoints de precio")

            admin_token = await emulator.sign_up_admin(f"verify-{run_id}-admin@example.test")
            created_emails.append(f"verify-{run_id}-admin@example.test")

            initial = (
                await api.request(
                    "GET",
                    f"/admin/leads/{priced['id']}/price",
                    token=admin_token,
                    expect=200,
                )
            ).json()
            require(
                initial["is_custom"] is False,
                "Un lead nuevo no deberia tener precio propio",
            )
            require(
                initial["sale_price"]["amount_cents"] == initial["suggested_price"]["amount_cents"],
                f"Sin precio propio se cobra el sugerido: {initial}",
            )
            report.ok(
                f"Sin precio propio se cobra el sugerido del oficio "
                f"({initial['suggested_price']['formatted']})"
            )

            overridden = (
                await api.request(
                    "PUT",
                    f"/admin/leads/{priced['id']}/price",
                    token=admin_token,
                    json_body={"amount_cents": 1500, "currency": "EUR"},
                    expect=200,
                )
            ).json()
            require(
                overridden["is_custom"] is True
                and overridden["sale_price"]["amount_cents"] == 1500,
                f"El precio propio no se aplico: {overridden}",
            )
            require(
                overridden["suggested_price"]["amount_cents"]
                == initial["suggested_price"]["amount_cents"],
                "Fijar el precio de un lead no debe cambiar el sugerido del oficio",
            )
            report.ok("El admin fija 15.00 € sin tocar el sugerido del oficio")

            # Lo que ve el profesional debe ser el precio de venta, no el sugerido.
            seen = (
                await api.request("GET", f"/leads/{priced['id']}", token=token, expect=200)
            ).json()
            require(
                seen["lead"]["price"]["amount_cents"] == 1500,
                f"El explorador sigue mostrando el precio viejo: {seen['lead']['price']}",
            )
            report.ok("El profesional ve el precio fijado por el admin")

            cleared = (
                await api.request(
                    "PUT",
                    f"/admin/leads/{priced['id']}/price",
                    token=admin_token,
                    json_body={"amount_cents": None, "currency": None},
                    expect=200,
                )
            ).json()
            require(
                cleared["is_custom"] is False
                and cleared["sale_price"]["amount_cents"]
                == initial["suggested_price"]["amount_cents"],
                f"Borrar el precio propio no devolvio al sugerido: {cleared}",
            )
            report.ok("Borrar el precio propio devuelve el lead al sugerido")

            rejected_price = await api.request(
                "PUT",
                f"/admin/leads/{priced['id']}/price",
                token=admin_token,
                json_body={"amount_cents": 10_000_000, "currency": "EUR"},
                expect=(422, 400),
            )
            report.detail(f"tope de precio respetado ({rejected_price.json().get('code')})")
            report.ok("Un precio absurdo se rechaza (red contra el error de tecleo)")

        except VerificationError as error:
            print(f"\n  {RED}FALLO{RESET} {error}")
            print(
                f"\n{RED}Verificacion interrumpida.{RESET} "
                f"{len(report.passed)} comprobaciones pasaron antes del fallo."
            )
            return 1
        except (httpx.HTTPError, asyncpg.PostgresError) as error:
            print(f"\n  {RED}ERROR{RESET} {type(error).__name__}: {error}")
            return 1
        finally:
            if args.keep:
                print(f"\n{DIM}--keep: se conservan los datos del run {run_id}{RESET}")
            else:
                await cleanup(db, created_lead_ids, run_id)
                print(f"\n{DIM}datos de prueba del run {run_id} eliminados{RESET}")
            await db.close()

    print(
        f"\n{GREEN}Flujo de compra verificado.{RESET} "
        f"{len(report.passed)} comprobaciones OK, {len(report.skipped)} omitidas."
    )
    if report.skipped:
        print(f"\n{YELLOW}No verificado contra el servicio real:{RESET}")
        for item in report.skipped:
            print(f"  · {item}")
        print(
            f"{DIM}Configura STRIPE_SECRET_KEY (clave de test) en apps/api/.env "
            f"para cubrirlo.{RESET}"
        )
    return 0


async def cleanup(db: asyncpg.Connection, lead_ids: list[str], run_id: str) -> None:
    """Borra lo que creo este run. Los usuarios del emulador se van al pararlo."""
    for lead_id in lead_ids:
        await db.execute("DELETE FROM lead_purchases WHERE lead_id = $1", uuid.UUID(lead_id))
        await db.execute("DELETE FROM leads WHERE id = $1", uuid.UUID(lead_id))
    await db.execute(
        "DELETE FROM processed_payment_events WHERE event_id LIKE $1",
        f"evt_verify_{run_id}%",
    )
    await db.execute(
        """
        DELETE FROM users WHERE id IN (
            SELECT user_id FROM professionals WHERE business_name LIKE $1
        )
        """,
        f"%Verify {run_id}%",
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
