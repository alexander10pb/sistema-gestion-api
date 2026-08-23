---
name: runtime-api-testing
description: How to bring up sistema-gestion-api (FastAPI + MongoDB/Motor) locally and exercise its golden paths and error paths end-to-end via Swagger UI, including fault injection for 503/500 handling.
---

# Runtime (end-to-end) testing of sistema-gestion-api

The repo blueprint only sets up the unit-test path (mongomock, no real Mongo). For
end-to-end/runtime testing you must start a real MongoDB and a real uvicorn process.

## Bring up the stack

```bash
cd /path/to/sistema-gestion-api
docker run -d --name mongo-smoke -p 27017:27017 mongo:7   # do NOT use --rm: you may need docker stop/start for fault injection
MONGO_URI=mongodb://localhost:27017 DB_NAME=test_local SECRET_KEY=testsecret123 \
  PYTHONPATH=. nohup .venv/bin/uvicorn main:app --port 8000 >/tmp/uvicorn.log 2>&1 &
```

Swagger UI: http://localhost:8000/docs — a good recording surface for this API.

Gotchas:
- `pip install -r requirements.txt` may fail on non-existent pins (e.g. `websockets==17.0.1`,
  `certifi==2026.7.22`, `starlette==1.4.1`). If so, use the existing `.venv` or install
  unpinned: `fastapi uvicorn motor pymongo passlib bcrypt==4.0.1 PyJWT python-dotenv
  python-multipart cloudinary email-validator pydantic httpx`. Note `bcrypt==4.0.1` is
  needed for passlib compatibility.
- `POST /auth/register` always creates `rol=usuario`. Promote an admin directly in Mongo:
  `docker exec mongo-smoke mongosh <db> --eval 'db.usuarios.updateOne({email:"admin@test.com"},{$set:{rol:"admin"}})'`
- No `CLOUDINARY_URL` → image endpoints return **503** ("El servicio de imágenes no está
  configurado"). That is the expected outcome, not a failure.

## Swagger UI tips
- You must click **Try it out** before parameter inputs accept text; use ctrl+a before typing
  to replace a previous value (triple-click alone sometimes leaves the old text).
- The `Authorize` dialog uses the OAuth2 password flow, so you can only authorize with real
  credentials. To test garbage/expired tokens, use a shell script with a hand-crafted JWT
  instead of the UI.
- After restarting uvicorn or Mongo you must re-`Authorize`; existing tokens survive
  restarts only if `SECRET_KEY` is unchanged, but blacklisted tokens stay rejected.

## Fault injection recipes
- **Mongo down → 503**: `docker stop mongo-smoke`, then hit any DB-backed endpoint. The
  response takes ~30 s (pymongo server-selection timeout), so any HTTP client must use a
  timeout > 60 s or you will see a client-side ReadTimeout and misdiagnose it as a failure.
  Recover with `docker start mongo-smoke`.
- **Unexpected exception → generic 500**: insert a `productos` document missing the required
  `nombre` field via mongosh and GET it; the response must be exactly
  `{"detail":"Error interno del servidor"}` with the traceback only in `/tmp/uvicorn.log`.
- **Corrupt-hash login → 401**: `db.usuarios.updateOne({email:...},{$set:{password_hash:"not-a-hash"}})`.
- **Cupo race**: create an event with `cupo_maximo: 1` and fire two users' `POST
  /eventos/{id}/inscribirse` from threads; expect exactly one 201 and one 409, never a 500,
  and `inscritos` must end at 1.

## Devin Secrets Needed
- None. `SECRET_KEY` can be any value; Cloudinary credentials are optional (absence is a
  tested 503 path).
