# Videorama · VHS Suite

 Videorama evoluciona hacia una pequeña suite de tres servicios que pueden convivir en
 el mismo `docker compose` o desplegarse por separado:

- **VHS (Video Harvester Service)**: el servicio FastAPI que ya conocías, ahora
  enfocado en capturar vídeos, generar audios/transcripciones y ejecutar
  transformaciones rápidas con `ffmpeg`.
- **Videorama Retro Library**: una biblioteca personal tipo YouTube de los años
  2000. Usa la API de VHS para adquirir contenido, clasificarlo automáticamente
  y ofrecer comandos básicos para gestionarlo.
- **VideoramaBot**: robot de Telegram opcional para interactuar con Videorama
  desde cualquier chat usando comandos `/add` y `/list`.

Ambos servicios comparten la misma imagen de Docker e instalación de
dependencias, por lo que es sencillo mantenerlos sincronizados.

## Características principales

### VHS · Video Harvester Service

- Descarga de vídeo y audio apoyada en [yt-dlp](https://github.com/yt-dlp/yt-dlp)
  con caché en disco y control de caducidad.
- Conversión directa de audio a texto usando OpenAI o un servicio compatible con
  whisper-asr.
- **Tareas rápidas de `ffmpeg`** sobre el material descargado (por ejemplo,
  extraer audio WAV/MP3 o generar copias comprimidas a 720p/480p).
- Endpoint `/api/probe` para inspeccionar cualquier URL soportada sin necesidad
  de descargarla.
- Panel web minimalista y páginas HTML (`/` y `/docs/api`) para uso manual.

### Videorama Retro Library

- API propia (`/api/library`) para guardar, consultar y eliminar elementos de la
  colección.
- Clasificación automática en base al proveedor, duración y etiquetas devueltas
  por VHS.
- Sincroniza automáticamente nuevas entradas con VHS para que el contenido quede
  precacheado en segundo plano.
- Almacena los datos en `data/videorama/library.json` (ruta configurable).
- Carpeta propia para subir archivos locales (`data/videorama/uploads`) desde el
  bot o mediante la API `/api/library/upload`.
- Panel web "VHS" en `/import` con formulario, iconografía retro, vista previa
  y confirmaciones instantáneas.
- Guarda la URL original y los metadatos completos devueltos por VHS para cada
  vídeo, manteniendo la biblioteca lista para auditorías futuras.
- Bot de Telegram opcional (`videorama/telegram_bot.py`) con comandos `/add` y
  `/list` para gestionar la biblioteca desde cualquier chat, además de menús de
  texto y soporte para subir/convertir archivos multimedia.

## Ejecución con Docker Compose

```bash
docker compose up --build
```

- Antes de levantar los servicios asegúrate de tener un fichero `.env` (puedes
  copiar `example.env`) en la raíz del repositorio. `docker compose` lo cargará
  automáticamente gracias a la directiva `env_file` y las variables estarán
  disponibles para los tres contenedores.
- El contexto de construcción excluye tanto el directorio `data/` como cualquier
  archivo `*.env`, evitando que se empaqueten datos generados por volúmenes o
  credenciales locales en la imagen final.

- VHS quedará disponible en `http://localhost:8601`.
- Videorama responderá en `http://localhost:8600`.
- VideoramaBot se conectará automáticamente a la API de Videorama usando las
  variables de entorno definidas en `.env` (necesita `TELEGRAM_BOT_TOKEN`).

Puedes seguir usando solo algunos de los servicios si lo prefieres; basta con
eliminar la entrada correspondiente del `docker-compose.yml` o ajustar el comando
que ejecuta cada contenedor.

## Variables de entorno destacadas

| Variable | Descripción | Servicio | Valor por defecto |
| --- | --- | --- | --- |
| `CACHE_TTL_SECONDS` | Tiempo de vida de los ficheros en caché | VHS | `86400` |
| `CACHE_DIR` | Carpeta de trabajo donde VHS guarda la caché | VHS | `data/cache` |
| `USAGE_LOG_PATH` | Ruta del log JSONL para estadísticas | VHS | `data/usage_log.jsonl` |
| `FFMPEG_BINARY` | Binario usado para las tareas de conversión | VHS | `ffmpeg` |
| `TRANSCRIPTION_*` | Configuración del endpoint usado para transcribir | VHS | Ver `example.env` |
| `WHISPER_ASR_*` | Endpoint alternativo compatible con whisper-asr | VHS | _(vacío)_ |
| `VHS_BASE_URL` | URL que usa Videorama para hablar con VHS | Videorama | `http://localhost:8601` |
| `VIDEORAMA_LIBRARY_PATH` | Ruta del fichero JSON de la biblioteca | Videorama | `data/videorama/library.json` |
| `VIDEORAMA_UPLOADS_DIR` | Carpeta donde se almacenan los archivos subidos | Videorama | `data/videorama/uploads` |
| `VIDEORAMA_DEFAULT_FORMAT` | Formato que Videorama pedirá a VHS al precachear | Videorama | `video_high` |
| `VIDEORAMA_API_URL` | URL que utilizará el bot de Telegram | Bot | `http://localhost:8600` |
| `TELEGRAM_BOT_TOKEN` | Token de tu bot para `videorama/telegram_bot.py` | Bot | _(vacío)_ |
| `TELEGRAM_VHS_PRESET` | Perfil de ffmpeg usado para las conversiones del bot | Bot | `ffmpeg_720p` |

Clona `example.env`, renómbralo a `.env` y ajusta los valores según tu entorno.

## Endpoints relevantes

### VHS

- `GET /api/health`: verificación del servicio.
- `GET /api/probe?url=...`: inspecciona metadatos sin descargar nada.
- `GET /api/download?url=...&format=...`: descarga/codifica contenido remoto en
  formatos `video_*`, `audio_*` o `transcripcion_*`.
- `POST /api/transcribe/upload`: sube un fichero local para obtener subtítulos en
  JSON/TXT/SRT.
- `POST /api/ffmpeg/upload`: aplica cualquiera de los perfiles `ffmpeg_*`
  (`ffmpeg_audio`, `ffmpeg_1080p`, etc.) sobre un archivo que subas desde tu
  equipo y devuelve la conversión.
- `GET /api/cache`: lista los elementos en caché (con endpoints para descargar o
  eliminar cada uno).
- `GET /api/stats/usage`: descargas, recodificaciones, formatos populares y
  métricas de transcripción.

### Videorama

- `GET /api/library`: devuelve todas las entradas guardadas junto al recuento.
- `POST /api/library`: añade una nueva URL, consulta `/api/probe` en VHS y, si
  se solicita, dispara una descarga remota para precachear el contenido.
- `POST /api/library/upload`: recibe un archivo local (audio o vídeo), lo
  almacena en `VIDEORAMA_UPLOADS_DIR` y genera una entrada lista para compartir.
- `DELETE /api/library/{id}`: elimina un elemento.
- `GET /media/{entry_id}/{filename}`: expone los archivos subidos para que
  puedas reproducirlos o descargarlos.
- `GET /api/health`: estado básico del servicio.

## Bot de Telegram

El bot es opcional y vive en `videorama/telegram_bot.py`. Para ejecutarlo:

```bash
export TELEGRAM_BOT_TOKEN="<tu token>"
export VIDEORAMA_API_URL="http://localhost:8600"
python -m videorama.telegram_bot
```

Comandos disponibles:

- `/add <url>`: añade el vídeo a la biblioteca y dispara el precacheo en VHS.
- `/list`: muestra las últimas 5 entradas disponibles.
- `/menu`: despliega los botones principales.

Además:

- Si le reenvías un archivo de audio o vídeo, el bot te ofrecerá un menú para
  subirlo directamente a Videorama (usando la API `/api/library/upload`) o
  pedirle a VHS que lo convierta con el preset definido en `TELEGRAM_VHS_PRESET`.
- Las conversiones usan el endpoint `/api/ffmpeg/upload` de VHS, y el resultado
  llega de vuelta al chat como documento adjunto.

## Ejecución local (sin Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn vhs.main:app --reload --host 0.0.0.0 --port 8601  # VHS
uvicorn videorama.main:app --reload --host 0.0.0.0 --port 8600  # Videorama
```

Lanza cada servicio en una terminal distinta o usa `tmux`/`foreman`. El bot de
Telegram también puede ejecutarse en el mismo entorno virtual.

## Licencia

MIT
