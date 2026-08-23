from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import httpx
import pytest
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient

import main
from app import database
from app.auth import dependencies
from app.auth.security import create_access_token, hash_password
from app.routers import auth, eventos, productos


@pytest.fixture(autouse=True)
def mock_database(monkeypatch):
    client = AsyncMongoMockClient()
    db = client["test_db"]
    collections = {
        "productos": db.get_collection("productos"),
        "usuarios": db.get_collection("usuarios"),
        "token_blacklist": db.get_collection("token_blacklist"),
        "eventos": db.get_collection("eventos"),
        "inscripciones": db.get_collection("inscripciones"),
    }

    monkeypatch.setattr(database, "client", client)
    monkeypatch.setattr(database, "database", db)
    monkeypatch.setattr(database, "productos_collection", collections["productos"])
    monkeypatch.setattr(database, "users_collection", collections["usuarios"])
    monkeypatch.setattr(database, "token_blacklist_collection", collections["token_blacklist"])
    monkeypatch.setattr(database, "eventos_collection", collections["eventos"])
    monkeypatch.setattr(database, "inscripciones_collection", collections["inscripciones"])

    monkeypatch.setattr(auth, "users_collection", collections["usuarios"])
    monkeypatch.setattr(auth, "token_blacklist_collection", collections["token_blacklist"])
    monkeypatch.setattr(productos, "productos_collection", collections["productos"])
    monkeypatch.setattr(eventos, "eventos_collection", collections["eventos"])
    monkeypatch.setattr(eventos, "inscripciones_collection", collections["inscripciones"])
    monkeypatch.setattr(dependencies, "users_collection", collections["usuarios"])
    monkeypatch.setattr(dependencies, "token_blacklist_collection", collections["token_blacklist"])
    return collections


@pytest.fixture(autouse=True)
def cloudinary_mocks(monkeypatch):
    upload = Mock(return_value={
        "secure_url": "https://res.cloudinary.com/test/image/upload/v1/new",
        "public_id": "cafeteria/new",
    })
    destroy = Mock(return_value={"result": "ok"})
    monkeypatch.setattr("cloudinary.uploader.upload", upload)
    monkeypatch.setattr("cloudinary.uploader.destroy", destroy)
    return {"upload": upload, "destroy": destroy}


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


async def _create_user(collection, *, role="usuario", name="Ana Torres", email=None):
    user_id = ObjectId()
    email = email or f"{role}-{user_id}@example.com"
    user = {
        "_id": user_id,
        "nombre": name,
        "email": email,
        "password_hash": hash_password("secreto123"),
        "rol": role,
    }
    await collection.insert_one(user)
    return user


@pytest.fixture
async def normal_user(mock_database):
    user = await _create_user(mock_database["usuarios"])
    token, _, _ = create_access_token(str(user["_id"]))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_user(mock_database):
    user = await _create_user(
        mock_database["usuarios"],
        role="admin",
        name="Admin User",
    )
    token, _, _ = create_access_token(str(user["_id"]))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def normal_user_record(mock_database):
    return await _create_user(mock_database["usuarios"])


@pytest.fixture
async def admin_user_record(mock_database):
    return await _create_user(
        mock_database["usuarios"],
        role="admin",
        name="Admin User",
    )


@pytest.fixture
def future_date():
    return datetime.now(timezone.utc) + timedelta(days=30)
