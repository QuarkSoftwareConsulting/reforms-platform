"""El formato de los errores 422 que el frontend usa para decir que campo corregir."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, field_validator

from app.domain.exceptions import ConsentDateInFutureError
from app.infrastructure.api.middlewares.error_handler import register_exception_handlers


class Body(BaseModel):
    description: str = Field(min_length=20, max_length=4000)
    keys: list[str] = Field(default_factory=list)

    @field_validator("keys")
    @classmethod
    def _check_keys(cls, keys: list[str]) -> list[str]:
        if keys:
            raise ValueError("clave no valida")
        return keys


def make_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/items")
    async def create(body: Body) -> dict[str, str]:
        return {"ok": body.description}

    @app.get("/future")
    async def future() -> None:
        raise ConsentDateInFutureError()

    return TestClient(app, raise_server_exceptions=False)


def test_field_errors_carry_the_field_the_type_and_the_numeric_limits() -> None:
    response = make_client().post("/items", json={"description": "corta"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["details"]["errors"] == [
        {
            "field": "description",
            "type": "string_too_short",
            "message": "String should have at least 20 characters",
            "limits": {"min_length": 20},
        }
    ]


def test_missing_field_has_no_limits() -> None:
    response = make_client().post("/items", json={})

    error = response.json()["details"]["errors"][0]
    assert (error["field"], error["type"], error["limits"]) == ("description", "missing", {})


def test_validator_exception_is_not_serialised_nor_leaked() -> None:
    # `ctx` trae la excepcion original del validador: ni serializable ni para el cliente.
    response = make_client().post("/items", json={"description": "x" * 30, "keys": ["../secreto"]})

    assert response.status_code == 422
    error = response.json()["details"]["errors"][0]
    assert error["field"] == "keys"
    assert error["limits"] == {}
    assert "secreto" not in response.text


def test_domain_validation_error_keeps_its_own_code() -> None:
    response = make_client().get("/future")

    assert response.status_code == 422
    assert response.json()["code"] == "CONSENT_DATE_IN_FUTURE"
