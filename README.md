# Videorama · VHS Suite

**Versiones**: Videorama 0.1.7 · Bot de Telegram 0.1.4 · Servidor MCP 0.1.3

Las versiones se cargan desde `versions.json`, aparecen en el _footer_ de las páginas y pueden consultarse desde todos los canales (MCP, bot de Telegram y web).

Videorama reúne tres servicios pensados para gestionar vídeos de manera ágil: un **API de captura y transformación (VHS)**, una **biblioteca web retro** y un **bot opcional de Telegram**. VHS vive ahora en un repositorio independiente y se despliega por separado; esta carpeta contiene únicamente Videorama, el bot y el MCP, que se conectan a la URL de VHS que definas en tu entorno.

## Tabla de contenido

- [Componentes](#componentes)
- [Arquitectura y flujo](#arquitectura-y-flujo)
- [Requisitos previos](#requisitos-previos)
- [Configuración](#configuración)
- [Puesta en marcha con Docker Compose](#puesta-en-marcha-con-docker-compose)
- [Ejecución local](#ejecución-local)
- [Endpoints y funcionalidades clave](#endpoints-y-funcionalidades-clave)
- [Flujos de trabajo habituales](#flujos-de-trabajo-habituales)
- [Mantenimiento y despliegues continuos](#mantenimiento-y-despliegues-continuos)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Resolución de problemas](#resolución-de-problemas)
- [Licencia](#licencia)
- [Servidor MCP](#servidor-mcp)

## Componentes

### VHS · Video Harvester Service (FastAPI)

- Descarga vídeo/audio con [yt-dlp](https://github.com/yt-dlp/yt-dlp), guardando caché en disco con control de caducidad.
- Transcribe audio a texto mediante OpenAI o servicios compatibles con `whisper-asr`.
- Ejecuta **perfiles rápidos de `ffmpeg`** (audio, 1080p/720p/480p, etc.) sobre material descargado o subido.
- Endpoint `/api/probe` para inspeccionar URLs soportadas sin necesidad de bajarlas.
- Panel web minimalista (`/` y `/docs/api`) para pruebas manuales.

### Videorama Library (FastAPI)

- API `/api/library` para guardar, consultar o eliminar elementos de la colección.
- Clasificación automática por proveedor, duración y etiquetas devueltas por VHS.
- Sincroniza nuevas entradas con VHS para precachear en segundo plano.
- Guarda datos en SQLite (`data/videorama/library.db`).
- Panel web retro en `/import` con formulario, vista previa y confirmaciones instantáneas.
- Gestor de listas estáticas/dinámicas y categorías directamente desde la biblioteca.

### VideoramaBot (Telegram)

- Comandos `/add` y `/list` para operar la biblioteca desde cualquier chat.
- Menús rápidos de texto y soporte para subir/convertir archivos multimedia.
- Reutiliza los presets de `ffmpeg` definidos en VHS (`TELEGRAM_VHS_PRESET`).

## Arquitectura y flujo

- **Puertos**: VHS expone `:8601`, Videorama `:8600` y el servidor MCP HTTP `:8765/mcp`. El bot consume la API de Videorama.
- **Datos**: todo lo que se descarga o sube vive bajo `data/` (montado como volumen en Docker). Las rutas clave se configuran con variables de entorno.
- **Cacheo y precarga**: Videorama solicita a VHS que precargue contenido con el formato por defecto definido en `VIDEORAMA_DEFAULT_FORMAT`.
- **Imágenes**: Videorama, el bot y el MCP usan `Dockerfile` en esta carpeta. VHS tiene su propia imagen en su repositorio y debe desplegarse aparte; apunta `VHS_BASE_URL` a la instancia que quieras usar.

## Requisitos previos

- Docker y Docker Compose (para el flujo recomendado).
- Python 3.11+ y `ffmpeg` instalados en el PATH si optas por ejecución local.
- Token de bot de Telegram (opcional) para `videorama/telegram_bot.py`.

## Configuración

1. Copia el archivo de ejemplo y ajústalo a tu entorno:

   ```bash
   cp example.env .env
   # Edita los valores según tus claves y rutas locales
   ```

2. Variables destacadas:

   | Variable | Descripción | Servicio | Valor por defecto |
   | --- | --- | --- | --- |
   | `CACHE_TTL_SECONDS` | Tiempo de vida de los ficheros en caché | VHS | `86400` |
   | `CACHE_DIR` | Carpeta donde VHS guarda caché | VHS | `data/cache` |
   | `USAGE_LOG_PATH` | Log JSONL para estadísticas | VHS | `data/usage_log.jsonl` |
   | `FFMPEG_BINARY` | Binario usado para conversiones | VHS | `ffmpeg` |
   | `TRANSCRIPTION_*` / `WHISPER_ASR_*` | Configuración del endpoint de transcripción | VHS | Ver `example.env` |
   | `VHS_BASE_URL` | URL que Videorama y el bot usan para hablar con VHS | Videorama/Bot | `http://localhost:8601` |
   | `VIDEORAMA_UPLOADS_DIR` | Carpeta para archivos subidos | Videorama | `data/videorama/uploads` |
   | `VIDEORAMA_DB_PATH` | Ruta del fichero SQLite de la biblioteca | Videorama | `data/videorama/library.db` |
   | `VIDEORAMA_DEFAULT_FORMAT` | Formato que Videorama pedirá a VHS al precachear | Videorama | `video_high` |
   | `VIDEORAMA_API_URL` | URL que usará el bot para hablar con Videorama | Bot | `http://localhost:8600` |
   | `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram | Bot | _(vacío)_ |
   | `TELEGRAM_VHS_PRESET` | Perfil de `ffmpeg` para conversiones vía bot | Bot | `ffmpeg_720p` |
| `VIDEORAMA_HOST_CONFIG_DIR` | Carpeta del host donde vive `.env` | Despliegue | `.` |
   | `VIDEORAMA_HOST_DATA_DIR` | Ruta del host para montar `data/` en los contenedores | Despliegue | `./data` |
   | `VIDEORAMA_HOST_VIDEOS_DIR` | Ruta del host para el volumen de `storage/videos` | Despliegue | `./storage/videos` |
   | `VIDEORAMA_HOST_VIDEOCLIPS_DIR` | Ruta del host para el volumen de `storage/videoclips` | Despliegue | `./storage/videoclips` |
   | `VIDEORAMA_HOST_MUSICA_DIR` | Ruta del host para el volumen de `storage/musica` | Despliegue | `./storage/musica` |
   | `VIDEORAMA_UID` / `VIDEORAMA_GID` | Usuario y grupo con los que se ejecutan los contenedores | Todos | `1000` / `1000` |
   | `VIDEORAMA_IMAGE` | Nombre de la imagen usada por Videorama/Bot/MCP | Despliegue | `ghcr.io/successbyfailure/videorama:latest` |

## Puesta en marcha con Docker Compose

1. Arranca o apunta a una instancia de VHS desplegada aparte (por ejemplo, desde su repositorio oficial o imagen publicada) y define `VHS_BASE_URL` en `.env` hacia esa URL.

2. Desde `Videorama/`, levanta la biblioteca, el bot y el MCP (solo se construye la imagen de Videorama):

   ```bash
   docker compose up --build
   ```

3. Una vez arriba:
   - VHS: la URL configurada en `VHS_BASE_URL`.
   - Videorama: <http://localhost:8600>
   - Servidor MCP (HTTP): <http://localhost:8765/mcp>
   - El bot se conectará automáticamente si `TELEGRAM_BOT_TOKEN` está definido.

4. Los contextos de construcción excluyen `data/` y cualquier `*.env`, evitando subir datos o credenciales a las imágenes finales.

> Usa `docker compose logs -f <servicio>` para inspeccionar los procesos y `docker compose down` para detenerlos conservando los volúmenes.

## Ejecución local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Terminal 1: VHS (repositorio independiente)
# Sigue las instrucciones del proyecto de VHS y arráncalo en otro terminal
# apuntando al puerto configurado (ej.: 8601).

# Terminal 2: Videorama
uvicorn videorama.main:app --reload --host 0.0.0.0 --port 8600

# (Opcional) Bot de Telegram en el mismo entorno
export TELEGRAM_BOT_TOKEN="<tu token>"
export VIDEORAMA_API_URL="http://localhost:8600"
python -m videorama.telegram_bot
```

Si ya tienes VHS desplegado en otro servidor, omite la Terminal 1 y configura `VHS_BASE_URL` para apuntar a esa instancia remota.

## Servidor MCP

Videorama incluye un servidor [Model Context Protocol](https://github.com/modelcontextprotocol/specification) para exponer
herramientas con las que consultar o poblar la biblioteca desde clientes compatibles (por ejemplo, asistentes locales). Es
un servicio opcional y separado del API principal.

1. Instala las dependencias en un entorno virtual limpio (evita mezclarlo con el bot de Telegram debido a diferencias en
   versiones de `httpx`):

   ```bash
   python -m venv .venv-mcp
   source .venv-mcp/bin/activate
   pip install -r requirements-mcp.txt
   ```

2. Lanza el servidor conectado al API de Videorama (usa `VIDEORAMA_API_URL` o `--api-url` para apuntar a otro host). Puedes elegir
   transporte `stdio` (modo local) o `http` (expuesto en `/mcp`):

   ```bash
   # Stdio (por defecto)
   python -m videorama.mcp_server --api-url http://localhost:8600

   # HTTP accesible en http://localhost:8765/mcp
   python -m videorama.mcp_server --api-url http://localhost:8600 --transport http --host 0.0.0.0 --port 8765
   ```

3. Herramientas disponibles:

   - `health`: comprueba el estado del API.
   - `list_recent_entries`: devuelve las últimas entradas (parámetro opcional `limit`).
   - `get_entry`: obtiene los detalles completos de una entrada por `entry_id`.
   - `add_entry_from_url`: agrega una nueva URL a la biblioteca y puede disparar la descarga en VHS con `auto_download`.

## Endpoints y funcionalidades clave

### VHS

- `GET /api/health`: estado del servicio.
- `GET /api/probe?url=...`: inspecciona metadatos sin descargar.
- `GET /api/download?url=...&format=...`: descarga/convierte en formatos `video_*`, `audio_*`, `ffmpeg_*` o `transcript_*`.
- `POST /api/transcribe/upload`: sube un fichero y devuelve subtítulos en JSON/TXT/SRT.
- `POST /api/ffmpeg/upload`: aplica un perfil `ffmpeg_*` sobre un archivo subido y devuelve la conversión.
- `GET /api/cache`: lista la caché (incluye endpoints para descargar o eliminar).
- `GET /api/stats/usage`: métricas de descargas, recodificaciones y transcripciones.

### Videorama

- `GET /api/library`: listado completo con recuento.
- `POST /api/library`: añade una URL, consulta `/api/probe` y dispara descargas opcionales en VHS.
- `POST /api/library/upload`: sube un archivo local (audio/vídeo) y genera entrada lista para compartir.
- `DELETE /api/library/{id}`: elimina un elemento.
- `GET /media/{entry_id}/{filename}`: expone archivos subidos para reproducir o descargar.
- `GET /api/playlists` · `POST /api/playlists` · `DELETE /api/playlists/{id}`: CRUD de listas personalizadas.
- `GET /api/category-settings` · `PUT /api/category-settings`: alias/visibilidad de categorías.
- `GET /api/health`: estado del servicio.

### Bot de Telegram

- `/add <url>`: agrega un vídeo y lanza precacheo en VHS.
- `/list`: muestra las últimas 5 entradas.
- `/menu`: despliega los botones principales.
- Reenvía un archivo y el bot ofrecerá subirlo a la biblioteca o convertirlo con el preset `TELEGRAM_VHS_PRESET` usando `/api/ffmpeg/upload`.

## Flujos de trabajo habituales

1. **Agregar un vídeo remoto**: envía la URL a `/api/library` (o usa `/add` en el bot). Videorama consultará VHS, clasificará la entrada y puede lanzar la descarga.
2. **Subir un archivo local**: usa `/api/library/upload` para alojarlo en `VIDEORAMA_UPLOADS_DIR` y obtener un enlace reproducible vía `/media/...`.
3. **Convertir un archivo puntual**: manda el fichero a `/api/ffmpeg/upload` indicando el perfil `ffmpeg_*` deseado; útil para obtener audio/MP3 o copias comprimidas.
4. **Gestionar la colección**: consulta `/api/playlists` y `/api/category-settings` para crear vistas dinámicas o categorizar por duración/proveedor.

## Mantenimiento y despliegues continuos

El script `scripts/auto_update.sh` comprueba periódicamente el repositorio remoto, sincroniza nuevas variables de `example.env` hacia `.env` y reinicia los servicios si detecta cambios.

Uso básico:

```bash
INTERVAL_SECONDS=300 ./scripts/auto_update.sh
```

Ejemplo en contenedor (requiere socket de Docker y el repo montado):

```bash
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd)":/workspace/Videorama \
  -w /workspace/Videorama \
  -e INTERVAL_SECONDS=180 \
  docker:27-cli \
  sh -c "apk add --no-cache git && ./scripts/auto_update.sh"
```

## Estructura del proyecto

```
assets/                 Recursos estáticos de Videorama.
data/                   Caché, base de datos y ficheros subidos (montados como volumen en Docker).
scripts/                Utilidades de mantenimiento (incluye auto_update.sh).
storage/                Volúmenes locales para vídeos, música y clips.
templates/              Plantillas HTML de la biblioteca retro.
videorama/              Código del servicio Videorama y bot de Telegram.
docker-compose.yml      Orquestación de Videorama/Bot/MCP apuntando a un VHS externo.
Dockerfile              Imagen de Videorama, el bot y el MCP.
requirements.txt        Dependencias Python de Videorama/Bot/MCP.
requirements-mcp.txt    Dependencias mínimas para el servidor MCP.
versions.json           Versiones cargadas por la interfaz y los servicios.
```

## Resolución de problemas

- **No se descargan vídeos**: revisa permisos de red y que `yt-dlp` soporte la URL; consulta `/api/probe` para ver si el proveedor es compatible.
- **Errores de `ffmpeg`**: asegúrate de que `FFMPEG_BINARY` apunta a un ejecutable válido y que el preset solicitado existe en la configuración.
- **El bot no responde**: verifica `TELEGRAM_BOT_TOKEN` y que `VIDEORAMA_API_URL` sea accesible desde la red de Telegram.
- **Caché crece demasiado**: ajusta `CACHE_TTL_SECONDS` o limpia con los endpoints de `/api/cache`.

## Licencia

Consulta el archivo de licencia asociado al proyecto o las condiciones proporcionadas por el equipo mantenedor.

