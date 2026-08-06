# Cafetería API — Backend (FastAPI + MongoDB)

API REST para administrar el menú de una cafetería institucional (desayunos, almuerzos, bebidas y postres): listar, crear, actualizar y eliminar productos.

## Requisitos

- Python 3.10+
- MongoDB corriendo localmente o en Atlas

## Instalación

```bash
cd cafeteria-api
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # y ajusta MONGO_URI si usas Atlas
```

## Ejecutar

```bash
uvicorn main:app --reload
```

- API: http://127.0.0.1:8000
- Swagger UI (documentación interactiva): http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Especificación OpenAPI en JSON: http://127.0.0.1:8000/openapi.json

## Autenticación

La API usa JWT (Bearer token). Consultar el menú es público; crear, actualizar y eliminar productos requiere estar autenticado.

| Método | Ruta             | Descripción                                              | Requiere token |
|--------|------------------|-----------------------------------------------------------|:---:|
| POST   | `/auth/register` | Registra un usuario (`nombre`, `email`, `password`)        | No |
| POST   | `/auth/login`    | Inicia sesión (form-data: `username`=email, `password`) y devuelve el `access_token` | No |
| POST   | `/auth/logout`   | Cierra la sesión invalidando el token actual                | Sí |
| GET    | `/auth/me`       | Devuelve los datos del usuario autenticado                  | Sí |

El login usa el formato estándar OAuth2 (`application/x-www-form-urlencoded`), así que funciona directo con el botón **Authorize** de Swagger UI (`/docs`): pega el email en `username` y la contraseña en `password`.

Para el logout, la API guarda el `jti` del token en una colección de "tokens invalidados" con expiración automática (índice TTL) igual a la fecha de expiración del propio JWT — así el token queda inutilizable de inmediato sin tener que esperar a que expire, y la colección se limpia sola.

### Ejemplo de uso con curl

```bash
# Registro
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Ana Torres","email":"ana@institucion.edu","password":"contraseña123"}'

# Login
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=ana@institucion.edu&password=contraseña123"
# -> { "access_token": "...", "token_type": "bearer" }

# Crear un producto (requiere el token del login)
curl -X POST http://127.0.0.1:8000/productos \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Jugo de mora","precio":4500,"categoria":"bebida"}'

# Logout
curl -X POST http://127.0.0.1:8000/auth/logout \
  -H "Authorization: Bearer <access_token>"
```

## Endpoints de productos

| Método | Ruta                  | Descripción                                  | Requiere token |
|--------|-----------------------|-----------------------------------------------|:---:|
| GET    | `/productos`           | Lista los productos (filtros opcionales: `categoria`, `disponible`) | No |
| GET    | `/productos/{id}`      | Obtiene un producto por id                    | No |
| POST   | `/productos`           | Crea un nuevo producto                        | Sí |
| PUT    | `/productos/{id}`      | Actualiza un producto existente               | Sí |
| DELETE | `/productos/{id}`      | Elimina un producto                           | Sí |

### Ejemplo de body para POST/PUT

```json
{
  "nombre": "Sándwich de pollo",
  "descripcion": "Pan integral con pollo y vegetales",
  "precio": 8500,
  "categoria": "almuerzo",
  "disponible": true
}
```

`categoria` acepta: `desayuno`, `almuerzo`, `bebida`, `postre`.

## Estructura del proyecto

```
cafeteria-api/
├── main.py                  # Punto de entrada de FastAPI
├── requirements.txt
├── .env.example
└── app/
    ├── database.py           # Conexión a MongoDB (Motor) + índices
    ├── schemas.py             # Modelos Pydantic de productos (request/response)
    ├── utils.py                # Helper para convertir documentos de Mongo
    ├── auth/
    │   ├── security.py          # Hash de contraseñas y JWT
    │   ├── schemas.py            # Modelos Pydantic de usuarios/tokens
    │   └── dependencies.py       # Dependencia get_current_user (protección de rutas)
    └── routers/
        ├── auth.py               # Endpoints de registro, login, logout, /me
        └── productos.py           # Endpoints CRUD de productos
```

## Notas de seguridad (plus sobre lo pedido en la guía)

- Las contraseñas se guardan con **bcrypt** (hash + salt), nunca en texto plano.
- El **logout real** invalida el token del lado del servidor (blacklist con TTL), algo que muchas implementaciones "de tutorial" omiten (solo borran el token en el cliente).
- El email de usuario tiene un **índice único** en Mongo para evitar registros duplicados.
- `SECRET_KEY` y tiempo de expiración del token son configurables por variable de entorno — nunca hardcodeados.
- CORS está abierto (`*`) solo para facilitar las pruebas locales; en un entorno real se debería restringir a los orígenes del front-end.
 