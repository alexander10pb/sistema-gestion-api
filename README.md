# Sistema de Gestión API — Backend (FastAPI + MongoDB)

API REST desarrollada con **FastAPI** y **MongoDB** para la gestión de usuarios, productos, eventos e inscripciones.

El sistema permite:

- Gestionar usuarios y autenticación.
- Autenticar usuarios mediante JWT.
- Administrar productos.
- Gestionar imágenes de productos mediante Cloudinary.
- Crear y administrar eventos.
- Registrar usuarios en eventos.
- Controlar el cupo máximo disponible.
- Evitar inscripciones duplicadas.
- Cancelar inscripciones.
- Consultar las inscripciones de un usuario.
- Consultar los usuarios inscritos en un evento.

---

## Tecnologías

- Python 3.10+
- FastAPI
- MongoDB
- MongoDB Atlas
- Motor
- Pydantic
- JWT
- bcrypt
- Uvicorn
- Cloudinary

---

## Requisitos

- Python 3.10 o superior
- MongoDB local o MongoDB Atlas
- Git
- Cuenta de Cloudinary para el almacenamiento de imágenes

---

## Instalación

Clonar el repositorio:

```bash
git clone <URL_DEL_REPOSITORIO>
cd sistema-gestion-api
```

Crear el entorno virtual:

```bash
python3 -m venv .venv
```

### Linux / macOS / WSL

```bash
source .venv/bin/activate
```

### Windows

```powershell
.venv\Scripts\activate
```

Instalar las dependencias:

```bash
pip install -r requirements.txt
```

Crear el archivo `.env`:

```bash
cp .env.example .env
```

En Windows también puedes crear el archivo `.env` manualmente.

Configurar las variables de entorno correspondientes.

---

# Variables de entorno

Las variables sensibles deben almacenarse en `.env` y **no deben subirse al repositorio**.

Ejemplo:

```env
MONGO_URI=mongodb://localhost:27017
DB_NAME=nombre_base_datos

SECRET_KEY=tu_clave_secreta

CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME
```

### MongoDB

`MONGO_URI` contiene la cadena de conexión a MongoDB local o MongoDB Atlas.

Ejemplo:

```env
MONGO_URI=mongodb+srv://usuario:password@cluster.mongodb.net/
```

### Cloudinary

Las imágenes de los productos se almacenan utilizando **Cloudinary**.

La conexión se configura mediante:

```env
CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME
```

La variable `CLOUDINARY_URL` permite que la aplicación se conecte a Cloudinary sin almacenar directamente las credenciales dentro del código fuente.

> **Importante:** no subir el archivo `.env` al repositorio. La variable `CLOUDINARY_URL` contiene credenciales privadas.

Consulta `.env.example` para conocer las variables requeridas por el proyecto.

---

# Ejecutar la aplicación

Desde la raíz del proyecto:

```bash
uvicorn main:app --reload
```

La API estará disponible en:

```text
http://127.0.0.1:8000
```

## Documentación

### Swagger UI

```text
http://127.0.0.1:8000/docs
```

### ReDoc

```text
http://127.0.0.1:8000/redoc
```

### Especificación OpenAPI

```text
http://127.0.0.1:8000/openapi.json
```

---

# Autenticación

La API utiliza **JWT (JSON Web Token)** mediante Bearer Authentication.

Algunas operaciones son públicas y otras requieren un usuario autenticado.

## Endpoints de autenticación

| Método | Ruta | Descripción | Token |
|--------|------|-------------|:-----:|
| POST | `/auth/register` | Registra un nuevo usuario | No |
| POST | `/auth/login` | Inicia sesión y obtiene un JWT | No |
| POST | `/auth/logout` | Cierra la sesión e invalida el token | Sí |
| GET | `/auth/me` | Obtiene los datos del usuario autenticado | Sí |

El login utiliza el formato estándar OAuth2:

```text
application/x-www-form-urlencoded
```

Por esta razón funciona directamente con el botón **Authorize** de Swagger UI.

Se debe utilizar:

```text
username = correo electrónico
password = contraseña
```

---

## Ejemplo de autenticación

### Registro

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Ana Torres",
    "email": "ana@institucion.edu",
    "password": "contraseña123"
  }'
```

### Login

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=ana@institucion.edu&password=contraseña123"
```

Respuesta:

```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

El `access_token` obtenido debe enviarse posteriormente mediante:

```text
Authorization: Bearer <access_token>
```

### Logout

```bash
curl -X POST http://127.0.0.1:8000/auth/logout \
  -H "Authorization: Bearer <access_token>"
```

La API guarda el `jti` del token invalidado en MongoDB utilizando una colección con índice TTL.

De esta manera, el token queda invalidado inmediatamente y el registro se elimina automáticamente cuando alcanza su fecha de expiración.

---

# Productos

El sistema permite administrar productos mediante operaciones CRUD.

Los productos pueden incluir imágenes almacenadas en **Cloudinary**.

## Endpoints

| Método | Ruta | Descripción | Token |
|--------|------|-------------|:-----:|
| GET | `/productos` | Lista los productos | No |
| GET | `/productos/{id}` | Obtiene un producto | No |
| POST | `/productos` | Crea un producto | Sí |
| PUT | `/productos/{id}` | Actualiza un producto | Sí |
| DELETE | `/productos/{id}` | Elimina un producto | Sí |

El listado permite utilizar filtros opcionales como:

```text
categoria
disponible
```

## Ejemplo de producto

```json
{
  "nombre": "Sándwich de pollo",
  "descripcion": "Pan integral con pollo y vegetales",
  "precio": 8500,
  "categoria": "almuerzo",
  "disponible": true
}
```

Las categorías disponibles son:

```text
desayuno
almuerzo
bebida
postre
```

---

# Imágenes de productos

El almacenamiento de imágenes se realiza mediante **Cloudinary**.

La aplicación utiliza la variable:

```env
CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME
```

Las imágenes no se almacenan directamente en el servidor de la API.

El flujo general es:

```text
Frontend
   │
   │ Imagen
   ▼
FastAPI
   │
   │ Upload
   ▼
Cloudinary
   │
   │ URL de imagen
   ▼
MongoDB
   │
   └── Guarda la referencia de la imagen
```

Esto permite que las imágenes permanezcan disponibles aunque la API sea desplegada nuevamente en un servidor diferente.

---

# Eventos

El sistema permite administrar eventos como:

- Charlas
- Talleres
- Actividades culturales
- Actividades deportivas
- Otras actividades institucionales

Cada evento contiene información general y permite controlar el número de participantes.

## Información de un evento

| Campo | Descripción |
|-------|-------------|
| `nombre` | Nombre del evento |
| `descripcion` | Descripción del evento |
| `fecha` | Fecha y hora del evento |
| `lugar` | Lugar donde se realizará |
| `cupo_maximo` | Cantidad máxima de participantes |
| `activo` | Indica si el evento está disponible |
| `inscritos` | Número de participantes inscritos |

La API calcula:

```text
cupos_disponibles = cupo_maximo - inscritos
```

## Endpoints

| Método | Ruta | Descripción | Token |
|--------|------|-------------|:-----:|
| GET | `/eventos` | Lista los eventos | No |
| GET | `/eventos/{evento_id}` | Obtiene un evento | No |
| POST | `/eventos` | Crea un evento | Sí |
| PUT | `/eventos/{evento_id}` | Actualiza un evento | Sí |
| DELETE | `/eventos/{evento_id}` | Desactiva un evento | Sí |

---

## Ejemplo de creación

```bash
curl -X POST http://127.0.0.1:8000/eventos \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Taller de Python",
    "descripcion": "Introducción al desarrollo con Python",
    "fecha": "2026-09-15T14:00:00",
    "lugar": "Laboratorio 302",
    "cupo_maximo": 30
  }'
```

Respuesta de ejemplo:

```json
{
  "_id": "68a123...",
  "nombre": "Taller de Python",
  "descripcion": "Introducción al desarrollo con Python",
  "fecha": "2026-09-15T14:00:00",
  "lugar": "Laboratorio 302",
  "cupo_maximo": 30,
  "activo": true,
  "inscritos": 0,
  "cupos_disponibles": 30
}
```

---

# Inscripciones

Los usuarios autenticados pueden inscribirse en los eventos disponibles.

El sistema controla automáticamente la disponibilidad de cupos.

## Endpoints

| Método | Ruta | Descripción | Token |
|--------|------|-------------|:-----:|
| POST | `/eventos/{evento_id}/inscribirse` | Inscribirse a un evento | Sí |
| DELETE | `/eventos/{evento_id}/inscribirse` | Cancelar una inscripción | Sí |
| GET | `/eventos/mis-inscripciones` | Consultar las inscripciones del usuario | Sí |
| GET | `/eventos/{evento_id}/inscritos` | Consultar los inscritos de un evento | Sí |

## Proceso de inscripción

Cuando un usuario intenta inscribirse, la API verifica:

1. Que el evento exista.
2. Que el evento esté activo.
3. Que el usuario no esté inscrito previamente.
4. Que existan cupos disponibles.
5. Registra la inscripción.
6. Actualiza la cantidad de inscritos.

Si el evento está lleno, la API rechaza la inscripción.

Ejemplo:

```text
Cupo máximo:        30
Inscritos:          30
Cupos disponibles:   0
```

Una nueva inscripción genera:

```text
409 Conflict
```

con un mensaje indicando que no existen cupos disponibles.

---

## Prevención de inscripciones duplicadas

La colección de inscripciones utiliza un índice único compuesto por:

```text
evento_id + usuario_id
```

Esto evita que un mismo usuario pueda registrar múltiples inscripciones para el mismo evento.

---

## Control de cupos

El contador de inscritos se mantiene dentro del documento del evento:

```json
{
  "cupo_maximo": 30,
  "inscritos": 15
}
```

La API utiliza una operación atómica de MongoDB para incrementar el contador únicamente cuando:

```text
inscritos < cupo_maximo
```

Esto permite controlar de manera más segura las inscripciones simultáneas y evita superar el cupo máximo establecido.

---

## Cancelación

Cuando un usuario cancela su inscripción, esta no se elimina físicamente de MongoDB.

Se actualiza su estado:

```text
activa → cancelada
```

Además, se libera nuevamente el cupo correspondiente.

Esto permite conservar el historial de las inscripciones.

---

# Base de datos

El proyecto utiliza **MongoDB** como sistema de almacenamiento y **Motor** como cliente asíncrono para realizar las operaciones desde FastAPI.

Las principales colecciones utilizadas son:

```text
usuarios
productos
eventos
inscripciones
token_blacklist
```

## Colección `usuarios`

Almacena la información de los usuarios y sus credenciales protegidas.

## Colección `productos`

Almacena los productos administrados por la API y la información asociada a sus imágenes.

Las imágenes son gestionadas mediante Cloudinary.

## Colección `eventos`

Almacena la información general de cada evento.

Ejemplo:

```json
{
  "_id": "...",
  "nombre": "Taller de Python",
  "descripcion": "Introducción al desarrollo con Python",
  "fecha": "2026-09-15T14:00:00",
  "lugar": "Laboratorio 302",
  "cupo_maximo": 30,
  "inscritos": 0,
  "activo": true
}
```

## Colección `inscripciones`

Relaciona usuarios con eventos.

Ejemplo:

```json
{
  "_id": "...",
  "evento_id": "...",
  "usuario_id": "...",
  "fecha_inscripcion": "2026-08-20T14:30:00",
  "estado": "activa"
}
```

## Colección `token_blacklist`

Almacena temporalmente los tokens invalidados durante el logout.

La colección utiliza un índice TTL para eliminar automáticamente los registros cuando alcanzan su fecha de expiración.

---

# Índices de MongoDB

La aplicación crea automáticamente los índices necesarios durante el inicio.

## Usuarios

Índice único para el correo:

```text
email
```

Esto evita registrar dos usuarios con el mismo correo.

## Tokens

Índice TTL sobre:

```text
expira_en
```

Permite eliminar automáticamente los tokens invalidados cuando expiran.

## Inscripciones

Índice compuesto único:

```text
evento_id + usuario_id
```

Evita inscripciones duplicadas del mismo usuario en el mismo evento.

---

# Estructura del proyecto

```text
sistema-gestion-api/
├── main.py                       # Punto de entrada de FastAPI
├── requirements.txt              # Dependencias
├── .env.example                  # Ejemplo de variables de entorno
├── .gitignore
└── app/
    ├── database.py               # Conexión a MongoDB + colecciones + índices
    ├── schemas.py                # Schemas Pydantic
    ├── utils.py                  # Funciones auxiliares
    │
    ├── auth/
    │   ├── security.py           # Hash de contraseñas y JWT
    │   ├── schemas.py            # Schemas de usuarios y tokens
    │   └── dependencies.py       # Dependencia get_current_user
    │
    └── routers/
        ├── auth.py               # Registro, login, logout y /me
        ├── productos.py          # CRUD de productos
        └── eventos.py            # Eventos e inscripciones
```

---

# Seguridad

El proyecto implementa diferentes medidas de seguridad:

- Las contraseñas se almacenan utilizando **bcrypt**, nunca en texto plano.
- La autenticación utiliza **JWT**.
- Las rutas protegidas requieren un Bearer Token válido.
- El logout invalida el token del lado del servidor.
- Los tokens invalidados se almacenan temporalmente mediante una blacklist con TTL.
- El correo electrónico de los usuarios tiene un índice único.
- La clave secreta y los tiempos de expiración se configuran mediante variables de entorno.
- Las inscripciones duplicadas se controlan mediante un índice único en MongoDB.
- El sistema valida el cupo máximo antes de registrar una inscripción.
- El contador de inscritos se actualiza mediante operaciones atómicas de MongoDB.
- Las credenciales de Cloudinary se manejan mediante variables de entorno.
- Las imágenes no se almacenan directamente en el servidor de la API.

---

# CORS

Actualmente CORS está configurado de forma abierta (`*`) para facilitar las pruebas y el desarrollo.

En un entorno de producción se recomienda restringir los orígenes permitidos exclusivamente a los dominios utilizados por el frontend.

---

# Despliegue

La API puede ser desplegada en servicios de hosting compatibles con aplicaciones Python/FastAPI.

Para producción se deben configurar como variables de entorno:

```env
MONGO_URI=...
DB_NAME=...
SECRET_KEY=...
CLOUDINARY_URL=...
```

No se deben incluir estas credenciales directamente en el código fuente ni subirlas al repositorio.

---

# Estado del proyecto

Actualmente la API cuenta con:

- [x] Registro de usuarios
- [x] Login con JWT
- [x] Logout con invalidación de token
- [x] Consulta del usuario autenticado
- [x] CRUD de productos
- [x] Carga de imágenes
- [x] Almacenamiento de imágenes mediante Cloudinary
- [x] CRUD de eventos
- [x] Inscripción a eventos
- [x] Cancelación de inscripciones
- [x] Consulta de inscripciones
- [x] Consulta de inscritos
- [x] Control de cupos
- [x] Control atómico del cupo disponible
- [x] Prevención de inscripciones duplicadas
- [x] Índices de MongoDB
- [x] Documentación Swagger
- [x] Documentación ReDoc
- [x] Configuración mediante variables de entorno