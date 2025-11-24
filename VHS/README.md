# VHS · Video Harvester Service

**Versión**: 0.1.2

Servicio FastAPI que descarga, convierte y transcribe vídeos o audios mediante `yt-dlp` y perfiles rápidos de `ffmpeg`. Este directorio está listo para vivir como repositorio independiente y generar su propia imagen de Docker.

## Requisitos

- Python 3.11+
- `ffmpeg` disponible en el sistema

## Variables de entorno

Copia `example.env` a `.env` y ajusta las rutas o claves necesarias:

```bash
cp example.env .env
```

Las variables más relevantes son `CACHE_DIR`, `USAGE_LOG_PATH`, las opciones de `TRANSCRIPTION_*` y `WHISPER_ASR_*`.

## Ejecución local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn vhs.main:app --reload --host 0.0.0.0 --port 8601
```

## Construcción de la imagen

Para generar una imagen dedicada a VHS sin depender de Videorama:

```bash
docker build -t ghcr.io/successbyfailure/vhs:latest -f Dockerfile .
docker run --env-file .env -p 8601:8601 ghcr.io/successbyfailure/vhs:latest
```

El contenedor expone `/api/health`, `/api/probe`, `/api/download`, `/api/cache`, `/api/transcribe/upload` y `/api/ffmpeg/upload`.

## Ficheros clave

- `vhs/main.py`: aplicación FastAPI principal.
- `templates/`: vistas HTML (`/` y `/docs/api`).
- `assets/`: recursos estáticos utilizados por las plantillas.
- `versions.json`: versión publicada del servicio.
