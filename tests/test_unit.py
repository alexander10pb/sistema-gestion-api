from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import jwt
import pytest
from bson import ObjectId
from fastapi import HTTPException
from pydantic import ValidationError

import main
from app import database
from app.auth import dependencies
from app.auth.schemas import RolUsuario, UsuarioOut
from app.auth.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.schemas.evento import EventoCreate, EventoUpdate
from app.schemas.inscripcion import EstadoInscripcion, InscripcionOut
from app.schemas.producto import CategoriaProducto, ProductoCreate
from app.utils import evento_helper, producto_helper, validar_object_id


def test_producto_helper_defaults_and_serializes_id():
    product = producto_helper({
        "_id": ObjectId("64f1c2a9b3e2a1a1a1a1a1a1"),
        "nombre": "Café",
        "precio": 5000,
        "categoria": "bebida",
    })
    assert product == {
        "_id": "64f1c2a9b3e2a1a1a1a1a1a1",
        "nombre": "Café",
        "descripcion": None,
        "precio": 5000,
        "categoria": "bebida",
        "disponible": True,
        "imagen_url": None,
    }


def test_evento_helper_defaults_and_clamps_available_slots():
    event = evento_helper({
        "_id": ObjectId("64f1c2a9b3e2a1a1a1a1a1a1"),
        "nombre": "Taller",
        "categoria": "Tecnología",
        "fecha": datetime.now(timezone.utc),
        "lugar": "Aula",
        "cupo_maximo": 2,
        "inscritos": 4,
    })
    assert event["activo"] is True
    assert event["cupos_disponibles"] == 0
    assert event["imagen_url"] is None


def test_validar_object_id_accepts_valid_id():
    value = validar_object_id("64f1c2a9b3e2a1a1a1a1a1a1", "producto")
    assert value == ObjectId("64f1c2a9b3e2a1a1a1a1a1a1")


def test_validar_object_id_rejects_malformed_id_with_entity():
    with pytest.raises(HTTPException) as error:
        validar_object_id("not-an-id", "evento")
    assert error.value.status_code == 400
    assert "evento" in error.value.detail


def test_password_hash_round_trip_and_wrong_password():
    password_hash = hash_password("secreto123")
    assert password_hash != "secreto123"
    assert verify_password("secreto123", password_hash)
    assert not verify_password("incorrecta", password_hash)


def test_access_tokens_have_distinct_jti_and_future_expiration():
    first, first_jti, first_exp = create_access_token("abc")
    second, second_jti, second_exp = create_access_token("abc")
    assert first != second
    assert first_jti != second_jti
    assert first_exp > datetime.now(timezone.utc)
    assert second_exp > datetime.now(timezone.utc)
    assert decode_access_token(first)["sub"] == "abc"


def test_decode_access_token_rejects_tampered_token():
    token, _, _ = create_access_token("abc")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token[:-1] + ("a" if token[-1] != "a" else "b"))


def test_decode_access_token_rejects_expired_token():
    token = jwt.encode(
        {
            "sub": "abc",
            "jti": "expired",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda: "not-a-token",
        lambda: jwt.encode({"sub": "abc"}, SECRET_KEY, algorithm=ALGORITHM),
        lambda: jwt.encode({"jti": "abc"}, SECRET_KEY, algorithm=ALGORITHM),
        lambda: jwt.encode(
            {"sub": "not-an-object-id", "jti": "abc"},
            SECRET_KEY,
            algorithm=ALGORITHM,
        ),
    ],
)
async def test_get_current_user_rejects_invalid_tokens(token_factory):
    with pytest.raises(HTTPException) as error:
        await dependencies.get_current_user(token_factory())
    assert error.value.status_code == 401


async def test_get_current_user_rejects_blacklisted_token(mock_database):
    user = {"_id": ObjectId(), "nombre": "Ana", "email": "ana@example.com"}
    await mock_database["usuarios"].insert_one(user)
    token, jti, _ = create_access_token(str(user["_id"]))
    await mock_database["token_blacklist"].insert_one({"jti": jti})
    with pytest.raises(HTTPException) as error:
        await dependencies.get_current_user(token)
    assert error.value.status_code == 401


async def test_get_current_user_rejects_missing_user(mock_database):
    token, _, _ = create_access_token(str(ObjectId()))
    with pytest.raises(HTTPException) as error:
        await dependencies.get_current_user(token)
    assert error.value.status_code == 401


async def test_get_current_user_defaults_missing_role(mock_database):
    user = {"_id": ObjectId(), "nombre": "Ana", "email": "ana@example.com"}
    await mock_database["usuarios"].insert_one(user)
    token, _, _ = create_access_token(str(user["_id"]))
    current = await dependencies.get_current_user(token)
    assert current["rol"] == "usuario"


async def test_get_current_admin_requires_admin():
    with pytest.raises(HTTPException) as error:
        await dependencies.get_current_admin({"rol": "usuario"})
    assert error.value.status_code == 403
    admin = {"rol": "admin"}
    assert await dependencies.get_current_admin(admin) is admin


def test_evento_fecha_must_be_future_for_create_and_update():
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    for model in (EventoCreate, EventoUpdate):
        with pytest.raises(ValidationError):
            model.model_validate({
                "nombre": "Evento",
                "categoria": "Tech",
                "fecha": past,
                "lugar": "Aula",
                "cupo_maximo": 10,
            })


def test_evento_naive_datetime_is_treated_as_utc():
    future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)
    model = EventoCreate(
        nombre="Evento",
        categoria="Tech",
        fecha=future,
        lugar="Aula",
        cupo_maximo=10,
    )
    assert model.fecha.tzinfo is None


def test_evento_update_accepts_a_future_datetime():
    future = datetime.now(timezone.utc) + timedelta(days=1)
    model = EventoUpdate(fecha=future)
    assert model.fecha == future


def test_schema_constraints_and_enums():
    with pytest.raises(ValidationError):
        ProductoCreate(nombre="", precio=0, categoria="invalid")
    with pytest.raises(ValidationError):
        ProductoCreate(
            nombre="x" * 101,
            precio=1,
            categoria=CategoriaProducto.bebida,
        )
    with pytest.raises(ValidationError):
        EventoCreate(
            nombre="x" * 151,
            categoria="Tech",
            fecha=datetime.now(timezone.utc) + timedelta(days=1),
            lugar="Aula",
            cupo_maximo=0,
        )
    assert CategoriaProducto.bebida.value == "bebida"
    assert EstadoInscripcion.activa.value == "activa"
    assert EstadoInscripcion.cancelada.value == "cancelada"
    assert RolUsuario.ADMIN.value == "admin"


def test_usuario_out_populates_mongo_id_alias():
    user = UsuarioOut.model_validate({
        "_id": "abc",
        "nombre": "Ana",
        "email": "ana@example.com",
    })
    assert user.id == "abc"
    assert user.rol == RolUsuario.USUARIO


async def test_crear_indices_requests_all_four_indexes(mock_database, monkeypatch):
    spies = {}
    for name, collection in mock_database.items():
        spy = AsyncMock()
        monkeypatch.setattr(collection, "create_index", spy)
        spies[name] = spy
    await database.crear_indices()
    assert spies["usuarios"].await_args.args == ("email",)
    assert spies["token_blacklist"].await_args.args == ("expira_en",)
    assert spies["eventos"].await_args.args == ("fecha",)
    assert spies["inscripciones"].await_args.args == ([
        ("evento_id", 1),
        ("usuario_id", 1),
    ],)
    assert spies["usuarios"].await_args.kwargs == {"unique": True}
    assert spies["token_blacklist"].await_args.kwargs == {"expireAfterSeconds": 0}
    assert spies["inscripciones"].await_args.kwargs["unique"] is True


async def test_root_status(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "mensaje": "API de la cafetería funcionando correctamente",
        "docs": "/docs",
    }
