# Videorama

Servicio web mínimo que envuelve a [yt-dlp](https://github.com/yt-dlp/yt-dlp) para descargar
videos o pistas de audio y mantener un caché local durante 24 horas.

## Características

- Interfaz web simple (SPA) para solicitar descargas de video (MP4 en alta o baja calidad), audio (MP3 en dos calidades) o transcripciones en texto plano utilizando la API de OpenAI.
- API REST en `/api` con endpoints:
  - `GET /api/health`: verificación rápida del servicio.
- `GET /api/download?url=...&format=video_high|video_low|video|audio|audio_low|transcripcion|transcripcion_txt|transcripcion_srt`: genera y devuelve el archivo (o transcripción).
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
| `YTDLP_PROXY` | Proxy HTTP(S) usado por yt-dlp | _(vacío)_ |
| `YTDLP_COOKIES_FILE` | Ruta a un archivo de cookies (por ejemplo, exportado con la extensión «Get cookies.txt»). Útil para proveedores que requieren sesión como Instagram. | _(vacío)_ |
| `YTDLP_USER_AGENT` | User-Agent personalizado enviado en cada petición de yt-dlp. Útil para evitar bloqueos/403. | Cadena UA moderna de Chrome |
| `TRANSCRIPTION_ENDPOINT` | Endpoint compatible con la librería de OpenAI para generar transcripciones. | `https://api.openai.com/v1` |
| `TRANSCRIPTION_API_KEY` | Clave API usada para autenticar contra el endpoint de transcripción. | _(vacío)_ |
| `TRANSCRIPTION_MODEL` | Modelo usado para transcribir (por ejemplo, `gpt-4o-mini-transcribe`). | `gpt-4o-mini-transcribe` |

Puedes sobrescribirlas en `docker-compose.yml` o al ejecutar `docker compose`.

Si quieres mantener tus ajustes localmente, crea un archivo `.env` (puedes
partir de `example.env`) y define ahí las variables necesarias; la aplicación lo
cargará automáticamente al iniciar.

## Ejecución local (sin Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Flujo de trabajo

1. Introduce la URL de cualquier proveedor soportado por yt-dlp y elige si deseas video (alta o baja calidad), audio (normal o ligero) o transcripción.
2. El backend busca en caché, descarga en caso necesario y devuelve el archivo.
3. Las descargas se guardan durante 24h para acelerar solicitudes repetidas y reducir el uso de red.

## Licencia

MIT
