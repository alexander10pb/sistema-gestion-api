from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.auth.security import create_access_token


def event_payload(future_date, **overrides):
    payload = {
        "nombre": "Taller de Python",
        "descripcion": "Introducción",
        "categoria": "Tecnología",
        "fecha": future_date.isoformat(),
        "lugar": "Aula 302",
        "cupo_maximo": 2,
    }
    payload.update(overrides)
    return payload


async def _insert_event(collection, future_date, **overrides):
    event = {
        "_id": ObjectId(),
        "nombre": "Evento",
        "descripcion": None,
        "categoria": "Tecnología",
        "fecha": future_date,
        "lugar": "Aula",
        "cupo_maximo": 2,
        "activo": True,
        "inscritos": 0,
        "imagen_url": None,
        "imagen_public_id": None,
    }
    event.update(overrides)
    await collection.insert_one(event)
    return event


async def _insert_registration(collection, event_id, user_id, *, state="activa", when=None):
    registration = {
        "_id": ObjectId(),
        "evento_id": str(event_id),
        "usuario_id": str(user_id),
        "fecha_inscripcion": when or datetime.now(timezone.utc),
        "estado": state,
    }
    await collection.insert_one(registration)
    return registration


async def test_list_events_returns_only_active_events_sorted_by_date(
    client,
    mock_database,
    future_date,
):
    await _insert_event(
        mock_database["eventos"],
        future_date + timedelta(days=2),
        nombre="Después",
    )
    await _insert_event(
        mock_database["eventos"],
        future_date,
        nombre="Primero",
    )
    await _insert_event(
        mock_database["eventos"],
        future_date - timedelta(days=1),
        nombre="Inactivo",
        activo=False,
    )
    response = await client.get("/eventos")
    assert response.status_code == 200
    assert [item["nombre"] for item in response.json()] == ["Primero", "Después"]


async def test_get_event_by_id_404_and_malformed_id(client):
    missing = await client.get(f"/eventos/{ObjectId()}")
    assert missing.status_code == 404
    malformed = await client.get("/eventos/not-an-id")
    assert malformed.status_code == 400
    assert "evento" in malformed.json()["detail"]


async def test_get_event_happy_path(client, mock_database, future_date):
    event = await _insert_event(mock_database["eventos"], future_date)
    response = await client.get(f"/eventos/{event['_id']}")
    assert response.status_code == 200
    assert response.json()["nombre"] == "Evento"


async def test_create_event_requires_admin_and_initializes_fields(
    client,
    normal_user,
    admin_user,
    future_date,
):
    payload = event_payload(future_date)
    anonymous = await client.post("/eventos", json=payload)
    assert anonymous.status_code == 401
    forbidden = await client.post("/eventos", json=payload, headers=normal_user)
    assert forbidden.status_code == 403
    response = await client.post("/eventos", json=payload, headers=admin_user)
    assert response.status_code == 201
    body = response.json()
    assert body["activo"] is True
    assert body["inscritos"] == 0
    assert body["cupos_disponibles"] == 2
    assert body["imagen_url"] is None


async def test_update_event_empty_unknown_capacity_and_happy_path(
    client,
    admin_user,
    mock_database,
    future_date,
):
    event = await _insert_event(mock_database["eventos"], future_date, cupo_maximo=3, inscritos=1)
    await _insert_registration(
        mock_database["inscripciones"],
        event["_id"],
        ObjectId(),
    )
    await _insert_registration(
        mock_database["inscripciones"],
        event["_id"],
        ObjectId(),
    )
    empty = await client.put(
        f"/eventos/{event['_id']}",
        headers=admin_user,
        json={},
    )
    assert empty.status_code == 400
    missing = await client.put(
        f"/eventos/{ObjectId()}",
        headers=admin_user,
        json={"nombre": "Nuevo"},
    )
    assert missing.status_code == 404
    too_small = await client.put(
        f"/eventos/{event['_id']}",
        headers=admin_user,
        json={"cupo_maximo": 0},
    )
    assert too_small.status_code == 422
    capacity_below_active = await client.put(
        f"/eventos/{event['_id']}",
        headers=admin_user,
        json={"cupo_maximo": 1},
    )
    assert capacity_below_active.status_code == 400
    updated = await client.put(
        f"/eventos/{event['_id']}",
        headers=admin_user,
        json={"nombre": "Actualizado", "cupo_maximo": 4},
    )
    assert updated.status_code == 200
    assert updated.json()["nombre"] == "Actualizado"
    assert updated.json()["cupo_maximo"] == 4


async def test_update_event_handles_document_disappearing_during_update(
    client,
    admin_user,
    mock_database,
    future_date,
    monkeypatch,
):
    event = await _insert_event(mock_database["eventos"], future_date)
    monkeypatch.setattr(
        "app.routers.eventos.eventos_collection.update_one",
        AsyncMock(return_value=type("Result", (), {"matched_count": 0})()),
    )
    response = await client.put(
        f"/eventos/{event['_id']}",
        headers=admin_user,
        json={"nombre": "Actualizado"},
    )
    assert response.status_code == 404


async def test_delete_event_deactivates_without_removing(
    client,
    admin_user,
    mock_database,
    future_date,
):
    event = await _insert_event(mock_database["eventos"], future_date)
    response = await client.delete(f"/eventos/{event['_id']}", headers=admin_user)
    assert response.status_code == 204
    saved = await mock_database["eventos"].find_one({"_id": event["_id"]})
    assert saved["activo"] is False

    missing = await client.delete(f"/eventos/{ObjectId()}", headers=admin_user)
    assert missing.status_code == 404


async def test_event_image_upload_validation_error_and_happy_path(
    client,
    admin_user,
    mock_database,
    future_date,
    cloudinary_mocks,
):
    event = await _insert_event(
        mock_database["eventos"],
        future_date,
        imagen_public_id="cafeteria/old-event",
    )
    bad = await client.post(
        f"/eventos/{event['_id']}/imagen",
        headers=admin_user,
        files={"archivo": ("event.txt", b"data", "text/plain")},
    )
    assert bad.status_code == 400
    oversized = await client.post(
        f"/eventos/{event['_id']}/imagen",
        headers=admin_user,
        files={"archivo": ("event.jpg", b"x" * (5 * 1024 * 1024 + 1), "image/jpeg")},
    )
    assert oversized.status_code == 400
    response = await client.post(
        f"/eventos/{event['_id']}/imagen",
        headers=admin_user,
        files={"archivo": ("event.jpg", b"data", "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json()["imagen_url"].startswith("https://res.cloudinary")
    cloudinary_mocks["destroy"].assert_called_once_with(
        "cafeteria/old-event",
        resource_type="image",
    )


async def test_event_image_upload_unknown_and_cloudinary_error(
    client,
    admin_user,
    mock_database,
    future_date,
    monkeypatch,
):
    missing = await client.post(
        f"/eventos/{ObjectId()}/imagen",
        headers=admin_user,
        files={"archivo": ("event.jpg", b"data", "image/jpeg")},
    )
    assert missing.status_code == 404
    event = await _insert_event(mock_database["eventos"], future_date)
    monkeypatch.setattr(
        "cloudinary.uploader.upload",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    response = await client.post(
        f"/eventos/{event['_id']}/imagen",
        headers=admin_user,
        files={"archivo": ("event.jpg", b"data", "image/jpeg")},
    )
    assert response.status_code == 500
    assert "offline" in response.json()["detail"]


async def test_event_image_cleanup_errors_do_not_fail_request(
    client,
    admin_user,
    mock_database,
    future_date,
    monkeypatch,
):
    event = await _insert_event(
        mock_database["eventos"],
        future_date,
        imagen_public_id="cafeteria/old-event",
    )
    monkeypatch.setattr(
        "cloudinary.uploader.destroy",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("cleanup failed")),
    )
    uploaded = await client.post(
        f"/eventos/{event['_id']}/imagen",
        headers=admin_user,
        files={"archivo": ("new.jpg", b"data", "image/jpeg")},
    )
    assert uploaded.status_code == 200
    deleted = await client.delete(
        f"/eventos/{event['_id']}/imagen",
        headers=admin_user,
    )
    assert deleted.status_code == 200


async def test_delete_event_image_404_and_clears_references(
    client,
    admin_user,
    mock_database,
    future_date,
    cloudinary_mocks,
):
    missing = await client.delete(
        f"/eventos/{ObjectId()}/imagen",
        headers=admin_user,
    )
    assert missing.status_code == 404
    event = await _insert_event(
        mock_database["eventos"],
        future_date,
        imagen_url="https://old",
        imagen_public_id="cafeteria/old-event",
    )
    response = await client.delete(
        f"/eventos/{event['_id']}/imagen",
        headers=admin_user,
    )
    assert response.status_code == 200
    saved = await mock_database["eventos"].find_one({"_id": event["_id"]})
    assert saved["imagen_url"] is None
    assert saved["imagen_public_id"] is None
    cloudinary_mocks["destroy"].assert_called_once()


async def test_register_event_unknown_already_registered_full_inactive_and_happy(
    client,
    normal_user,
    mock_database,
    future_date,
):
    unknown = await client.post(
        f"/eventos/{ObjectId()}/inscribirse",
        headers=normal_user,
    )
    assert unknown.status_code == 404

    event = await _insert_event(mock_database["eventos"], future_date)
    first = await client.post(
        f"/eventos/{event['_id']}/inscribirse",
        headers=normal_user,
    )
    assert first.status_code == 201
    assert first.json()["estado"] == "activa"
    saved = await mock_database["eventos"].find_one({"_id": event["_id"]})
    assert saved["inscritos"] == 1
    duplicate = await client.post(
        f"/eventos/{event['_id']}/inscribirse",
        headers=normal_user,
    )
    assert duplicate.status_code == 409
    assert "Ya estás inscrito" in duplicate.json()["detail"]

    full = await _insert_event(
        mock_database["eventos"],
        future_date,
        cupo_maximo=1,
        inscritos=1,
    )
    full_response = await client.post(
        f"/eventos/{full['_id']}/inscribirse",
        headers=normal_user,
    )
    assert full_response.status_code == 409
    inactive = await _insert_event(
        mock_database["eventos"],
        future_date,
        activo=False,
    )
    inactive_response = await client.post(
        f"/eventos/{inactive['_id']}/inscribirse",
        headers=normal_user,
    )
    assert inactive_response.status_code == 409


async def test_register_event_duplicate_key_returns_seat_and_409(
    client,
    normal_user,
    mock_database,
    future_date,
    monkeypatch,
):
    event = await _insert_event(mock_database["eventos"], future_date)
    monkeypatch.setattr(
        "app.routers.eventos.inscripciones_collection.insert_one",
        lambda *args, **kwargs: (_ for _ in ()).throw(DuplicateKeyError("duplicate")),
    )
    response = await client.post(
        f"/eventos/{event['_id']}/inscribirse",
        headers=normal_user,
    )
    assert response.status_code == 409
    saved = await mock_database["eventos"].find_one({"_id": event["_id"]})
    assert saved["inscritos"] == 0


async def test_register_event_missing_created_document_returns_500_and_seat(
    client,
    normal_user,
    mock_database,
    future_date,
    monkeypatch,
):
    event = await _insert_event(mock_database["eventos"], future_date)
    monkeypatch.setattr(
        "app.routers.eventos.inscripciones_collection.find_one",
        AsyncMock(side_effect=[None, None]),
    )
    response = await client.post(
        f"/eventos/{event['_id']}/inscribirse",
        headers=normal_user,
    )
    assert response.status_code == 500
    saved = await mock_database["eventos"].find_one({"_id": event["_id"]})
    assert saved["inscritos"] == 0


async def test_cancel_registration_404_missing_event_and_registration_and_happy(
    client,
    normal_user_record,
    mock_database,
    future_date,
):
    token, _, _ = create_access_token(str(normal_user_record["_id"]))
    headers = {"Authorization": f"Bearer {token}"}
    missing = await client.delete(f"/eventos/{ObjectId()}/inscribirse", headers=headers)
    assert missing.status_code == 404
    event = await _insert_event(mock_database["eventos"], future_date)
    no_registration = await client.delete(
        f"/eventos/{event['_id']}/inscribirse",
        headers=headers,
    )
    assert no_registration.status_code == 404
    registration = await _insert_registration(
        mock_database["inscripciones"],
        event["_id"],
        normal_user_record["_id"],
    )
    await mock_database["eventos"].update_one(
        {"_id": event["_id"]},
        {"$set": {"inscritos": 1}},
    )
    cancelled = await client.delete(
        f"/eventos/{event['_id']}/inscribirse",
        headers=headers,
    )
    assert cancelled.status_code == 204
    saved_registration = await mock_database["inscripciones"].find_one({"_id": registration["_id"]})
    assert saved_registration["estado"] == "cancelada"
    saved_event = await mock_database["eventos"].find_one({"_id": event["_id"]})
    assert saved_event["inscritos"] == 0


async def test_cancel_registration_conflict_when_update_changes_nothing(
    client,
    normal_user_record,
    mock_database,
    future_date,
    monkeypatch,
):
    from app.auth.security import create_access_token

    event = await _insert_event(mock_database["eventos"], future_date, inscritos=1)
    await _insert_registration(
        mock_database["inscripciones"],
        event["_id"],
        normal_user_record["_id"],
    )
    token, _, _ = create_access_token(str(normal_user_record["_id"]))
    monkeypatch.setattr(
        "app.routers.eventos.inscripciones_collection.update_one",
        AsyncMock(
            return_value=type("Result", (), {"modified_count": 0})(),
        ),
    )
    response = await client.delete(
        f"/eventos/{event['_id']}/inscribirse",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


async def test_my_registrations_only_returns_callers_active_registrations(
    client,
    normal_user_record,
    mock_database,
    future_date,
):
    event = await _insert_event(mock_database["eventos"], future_date)
    await _insert_registration(
        mock_database["inscripciones"],
        event["_id"],
        normal_user_record["_id"],
    )
    await _insert_registration(
        mock_database["inscripciones"],
        event["_id"],
        normal_user_record["_id"],
        state="cancelada",
    )
    await _insert_registration(
        mock_database["inscripciones"],
        event["_id"],
        ObjectId(),
    )
    token, _, _ = create_access_token(str(normal_user_record["_id"]))
    response = await client.get(
        "/eventos/mis-inscripciones",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_list_registrations_requires_admin_and_404_unknown(
    client,
    normal_user,
    admin_user,
    mock_database,
    future_date,
):
    event = await _insert_event(mock_database["eventos"], future_date)
    forbidden = await client.get(
        f"/eventos/{event['_id']}/inscritos",
        headers=normal_user,
    )
    assert forbidden.status_code == 403
    unknown = await client.get(
        f"/eventos/{ObjectId()}/inscritos",
        headers=admin_user,
    )
    assert unknown.status_code == 404
    response = await client.get(
        f"/eventos/{event['_id']}/inscritos",
        headers=admin_user,
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_list_registrations_returns_active_entries(
    client,
    admin_user,
    mock_database,
    future_date,
):
    event = await _insert_event(mock_database["eventos"], future_date)
    registration = await _insert_registration(
        mock_database["inscripciones"],
        event["_id"],
        ObjectId(),
    )
    response = await client.get(
        f"/eventos/{event['_id']}/inscritos",
        headers=admin_user,
    )
    assert response.status_code == 200
    assert response.json()[0]["_id"] == str(registration["_id"])
