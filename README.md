# Videorama

Servicio web mínimo que envuelve a [yt-dlp](https://github.com/yt-dlp/yt-dlp) para descargar
videos o pistas de audio y mantener un caché local durante 24 horas.

## Características

- Interfaz web simple (SPA) para solicitar descargas de video (MP4) o audio (MP3).
- API REST en `/api` con endpoints:
  - `GET /api/health`: verificación rápida del servicio.
  - `GET /api/download?url=...&format=video|audio`: genera y devuelve el archivo.
  - `GET /api/cache`: listado informativo del contenido en caché.
- Caché de descargas en disco durante 24h (configurable mediante `CACHE_TTL_SECONDS`).
- Basado en FastAPI + yt-dlp para aprovechar todos los proveedores soportados.

## Requisitos

- Docker y Docker Compose (o Python 3.11+ si deseas ejecutar el proyecto sin contenedores).

## Ejecución con Docker Compose

```bash
docker compose up --build
```

El servicio quedará disponible en `http://localhost:8000` con la interfaz web y la API.

### Variables de entorno útiles

| Variable | Descripción | Valor por defecto |
| --- | --- | --- |
| `CACHE_TTL_SECONDS` | Tiempo de vida de cada descarga en caché | `86400` (24h) |
| `CACHE_DIR` | Ruta interna donde se guarda la caché | `data/cache` |

Puedes sobrescribirlas en `docker-compose.yml` o al ejecutar `docker compose`.

## Ejecución local (sin Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Flujo de trabajo

1. Introduce la URL de cualquier proveedor soportado por yt-dlp y elige si deseas video o audio.
2. El backend busca en caché, descarga en caso necesario y devuelve el archivo.
3. Las descargas se guardan durante 24h para acelerar solicitudes repetidas y reducir el uso de red.

## Licencia

MIT
