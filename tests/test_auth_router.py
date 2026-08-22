from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.auth import security


async def test_register_forces_normal_role_and_does_not_expose_password(client):
    response = await client.post(
        "/auth/register",
        json={
            "nombre": "Nueva Persona",
            "email": "nueva@example.com",
            "password": "secreto123",
            "rol": "admin",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "nueva@example.com"
    assert body["rol"] == "usuario"
    assert "password_hash" not in body


async def test_register_duplicate_email_returns_400(client, mock_database, monkeypatch):
    async def duplicate(_document):
        raise DuplicateKeyError("duplicate email")

    monkeypatch.setattr(
        "app.routers.auth.users_collection.insert_one",
        duplicate,
    )
    response = await client.post(
        "/auth/register",
        json={
            "nombre": "Duplicada",
            "email": "duplicada@example.com",
            "password": "secreto123",
        },
    )
    assert response.status_code == 400
    assert "Ya existe" in response.json()["detail"]


async def test_login_happy_path_returns_bearer_token(client, mock_database):
    user = {
        "_id": ObjectId(),
        "nombre": "Ana",
        "email": "ana@example.com",
        "password_hash": security.hash_password("secreto123"),
        "rol": "usuario",
    }
    await mock_database["usuarios"].insert_one(user)
    response = await client.post(
        "/auth/login",
        data={"username": user["email"], "password": "secreto123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert security.decode_access_token(body["access_token"])["sub"] == str(user["_id"])


async def test_login_wrong_password_and_unknown_email_return_401(client, mock_database):
    await mock_database["usuarios"].insert_one({
        "_id": ObjectId(),
        "nombre": "Ana",
        "email": "ana@example.com",
        "password_hash": security.hash_password("secreto123"),
    })
    for email, password in [
        ("ana@example.com", "incorrecta"),
        ("nadie@example.com", "secreto123"),
    ]:
        response = await client.post(
            "/auth/login",
            data={"username": email, "password": password},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Email o contraseña incorrectos"


async def test_me_requires_authentication(client):
    response = await client.get("/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_user(client, normal_user):
    response = await client.get("/auth/me", headers=normal_user)
    assert response.status_code == 200
    body = response.json()
    assert body["rol"] == "usuario"
    assert "password_hash" not in body


async def test_logout_blacklists_token_and_rejects_it_from_me(client, normal_user, mock_database):
    response = await client.post("/auth/logout", headers=normal_user)
    assert response.status_code == 200
    assert response.json()["mensaje"] == "Sesión cerrada correctamente"
    assert await mock_database["token_blacklist"].count_documents({}) == 1
    rejected = await client.get("/auth/me", headers=normal_user)
    assert rejected.status_code == 401


async def test_logout_can_be_verified_with_real_dependency(client, normal_user):
    response = await client.post("/auth/logout", headers=normal_user)
    assert response.status_code == 200
