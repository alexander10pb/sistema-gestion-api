from bson import ObjectId


async def _insert_product(collection, **overrides):
    product = {
        "_id": ObjectId(),
        "nombre": "Café",
        "descripcion": "Café negro",
        "precio": 5000,
        "categoria": "bebida",
        "disponible": True,
    }
    product.update(overrides)
    await collection.insert_one(product)
    return product


async def test_list_products_without_and_with_filters(client, mock_database):
    await _insert_product(mock_database["productos"], nombre="Café", categoria="bebida")
    await _insert_product(
        mock_database["productos"],
        nombre="Sopa",
        categoria="almuerzo",
        disponible=False,
    )
    all_products = await client.get("/productos")
    assert all_products.status_code == 200
    assert len(all_products.json()) == 2

    filtered = await client.get(
        "/productos",
        params={"categoria": "bebida", "disponible": "true"},
    )
    assert filtered.status_code == 200
    assert [item["nombre"] for item in filtered.json()] == ["Café"]


async def test_get_product_by_id_404_and_malformed_id_400(client):
    missing = await client.get(f"/productos/{ObjectId()}")
    assert missing.status_code == 404
    malformed = await client.get("/productos/not-an-id")
    assert malformed.status_code == 400
    assert "producto" in malformed.json()["detail"]


async def test_get_product_happy_path_and_upload_unknown_product(
    client,
    normal_user,
    mock_database,
):
    product = await _insert_product(mock_database["productos"])
    response = await client.get(f"/productos/{product['_id']}")
    assert response.status_code == 200
    assert response.json()["nombre"] == "Café"
    missing_image = await client.post(
        f"/productos/{ObjectId()}/imagen",
        headers=normal_user,
        files={"archivo": ("new.jpg", b"data", "image/jpeg")},
    )
    assert missing_image.status_code == 404


async def test_create_product_requires_auth_and_validates_body(client, normal_user):
    anonymous = await client.post(
        "/productos",
        json={
            "nombre": "Té",
            "precio": 1000,
            "categoria": "bebida",
        },
    )
    assert anonymous.status_code == 401
    for payload in [
        {"nombre": "Té", "precio": 0, "categoria": "bebida"},
        {"nombre": "Té", "precio": 1000, "categoria": "no-categoria"},
    ]:
        invalid = await client.post("/productos", json=payload, headers=normal_user)
        assert invalid.status_code == 422


async def test_create_product_happy_path(client, normal_user):
    response = await client.post(
        "/productos",
        headers=normal_user,
        json={
            "nombre": "Té",
            "descripcion": "Té caliente",
            "precio": 1000,
            "categoria": "bebida",
            "disponible": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["nombre"] == "Té"


async def test_update_product_empty_body_unknown_and_happy_path(
    client,
    normal_user,
    mock_database,
):
    product = await _insert_product(mock_database["productos"])
    empty = await client.put(
        f"/productos/{product['_id']}",
        headers=normal_user,
        json={},
    )
    assert empty.status_code == 400
    missing = await client.put(
        f"/productos/{ObjectId()}",
        headers=normal_user,
        json={"precio": 6000},
    )
    assert missing.status_code == 404
    updated = await client.put(
        f"/productos/{product['_id']}",
        headers=normal_user,
        json={"precio": 6000, "disponible": False},
    )
    assert updated.status_code == 200
    assert updated.json()["precio"] == 6000
    assert updated.json()["disponible"] is False


async def test_delete_product_404_and_happy_path_destroys_image(
    client,
    normal_user,
    mock_database,
    cloudinary_mocks,
):
    missing = await client.delete(
        f"/productos/{ObjectId()}",
        headers=normal_user,
    )
    assert missing.status_code == 404
    product = await _insert_product(
        mock_database["productos"],
        imagen_public_id="cafeteria/old-product",
    )
    response = await client.delete(
        f"/productos/{product['_id']}",
        headers=normal_user,
    )
    assert response.status_code == 204
    assert await mock_database["productos"].find_one({"_id": product["_id"]}) is None
    cloudinary_mocks["destroy"].assert_called_once_with(
        "cafeteria/old-product",
        resource_type="image",
    )


async def test_upload_product_image_rejects_bad_extension_and_oversized_file(
    client,
    normal_user,
    mock_database,
):
    product = await _insert_product(mock_database["productos"])
    bad_extension = await client.post(
        f"/productos/{product['_id']}/imagen",
        headers=normal_user,
        files={"archivo": ("document.txt", b"data", "text/plain")},
    )
    assert bad_extension.status_code == 400
    oversized = await client.post(
        f"/productos/{product['_id']}/imagen",
        headers=normal_user,
        files={"archivo": ("large.jpg", b"x" * (5 * 1024 * 1024 + 1), "image/jpeg")},
    )
    assert oversized.status_code == 400


async def test_upload_product_image_cloudinary_error_returns_500(
    client,
    normal_user,
    mock_database,
    monkeypatch,
):
    product = await _insert_product(mock_database["productos"])
    monkeypatch.setattr(
        "cloudinary.uploader.upload",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    response = await client.post(
        f"/productos/{product['_id']}/imagen",
        headers=normal_user,
        files={"archivo": ("new.jpg", b"data", "image/jpeg")},
    )
    assert response.status_code == 500
    assert "offline" in response.json()["detail"]


async def test_upload_product_image_stores_references_and_destroys_previous(
    client,
    normal_user,
    mock_database,
    cloudinary_mocks,
):
    product = await _insert_product(
        mock_database["productos"],
        imagen_url="https://old",
        imagen_public_id="cafeteria/old-product",
    )
    response = await client.post(
        f"/productos/{product['_id']}/imagen",
        headers=normal_user,
        files={"archivo": ("new.jpg", b"data", "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json()["imagen_url"].startswith("https://res.cloudinary")
    saved = await mock_database["productos"].find_one({"_id": product["_id"]})
    assert saved["imagen_public_id"] == "cafeteria/new"
    cloudinary_mocks["destroy"].assert_called_once_with(
        "cafeteria/old-product",
        resource_type="image",
    )


async def test_product_image_cleanup_errors_do_not_fail_request(
    client,
    normal_user,
    mock_database,
    monkeypatch,
):
    product = await _insert_product(
        mock_database["productos"],
        imagen_public_id="cafeteria/old-product",
    )
    monkeypatch.setattr(
        "cloudinary.uploader.destroy",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("cleanup failed")),
    )
    uploaded = await client.post(
        f"/productos/{product['_id']}/imagen",
        headers=normal_user,
        files={"archivo": ("new.jpg", b"data", "image/jpeg")},
    )
    assert uploaded.status_code == 200
    deleted = await client.delete(
        f"/productos/{product['_id']}/imagen",
        headers=normal_user,
    )
    assert deleted.status_code == 200
    await mock_database["productos"].update_one(
        {"_id": product["_id"]},
        {"$set": {"imagen_public_id": "cafeteria/again"}},
    )
    removed = await client.delete(
        f"/productos/{product['_id']}",
        headers=normal_user,
    )
    assert removed.status_code == 204


async def test_delete_product_image_404_and_happy_path_clears_fields(
    client,
    normal_user,
    mock_database,
    cloudinary_mocks,
):
    missing = await client.delete(
        f"/productos/{ObjectId()}/imagen",
        headers=normal_user,
    )
    assert missing.status_code == 404
    product = await _insert_product(
        mock_database["productos"],
        imagen_url="https://old",
        imagen_public_id="cafeteria/old-product",
    )
    response = await client.delete(
        f"/productos/{product['_id']}/imagen",
        headers=normal_user,
    )
    assert response.status_code == 200
    assert response.json()["imagen_url"] is None
    saved = await mock_database["productos"].find_one({"_id": product["_id"]})
    assert saved["imagen_url"] is None
    assert saved["imagen_public_id"] is None
    cloudinary_mocks["destroy"].assert_called_once()
