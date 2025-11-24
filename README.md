# Videorama · VHS Monorepo

Este repositorio agrupa dos proyectos listos para separarse en repos independientes:

- `Videorama/`: biblioteca retro, bot de Telegram y servidor MCP. Incluye el `docker-compose.yml` por defecto, que construye la API junto a un contenedor de VHS como dependencia local.
- `VHS/`: servicio de ingesta y transformación de vídeo/audio. Puede desplegarse solo o como parte del compose incluido en `Videorama/`.

Cada carpeta contiene su propio `Dockerfile`, variables de entorno de ejemplo y documentación específica. Para configurar los servicios, consulta primero `Videorama/README.md` (compose conjunto) o `VHS/README.md` (servicio aislado).
