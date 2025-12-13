# Videorama v2.0.0 - Quick Start Guide

**Estado:** MVP Completo (~95%) - Listo para Testing ✅

---

## 🚀 Inicio Rápido

### 1. Configuración Inicial

```bash
# Clonar el repositorio (si no lo tienes ya)
cd /home/coder/projects/Videorama

# Verificar estructura
ls -la
# Deberías ver: backend/, frontend/, docker-compose.yml
```

### 2. Configurar Variables de Entorno

```bash
# Copiar archivo de ejemplo (crear si no existe)
cp backend/.env.example backend/.env

# Editar configuración
nano backend/.env
```

**Configuración mínima requerida:**
```env
# Base
APP_NAME=Videorama
DEBUG=true
SECRET_KEY=tu-secret-key-aqui-cambiar-en-produccion

# Database (para Docker)
DATABASE_URL=postgresql://videorama:videorama@db:5432/videorama

# Storage
STORAGE_BASE_PATH=/app/storage

# VHS API (para descargar videos)
VHS_BASE_URL=http://vhs:8080
VHS_TIMEOUT=300

# OpenAI/LLM (opcional pero recomendado)
OPENAI_API_KEY=sk-tu-api-key-aqui
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# External APIs (opcional)
TMDB_API_KEY=tu-tmdb-key
SPOTIFY_CLIENT_ID=tu-spotify-id
SPOTIFY_CLIENT_SECRET=tu-spotify-secret

# Telegram (opcional)
TELEGRAM_BOT_TOKEN=tu-bot-token
```

### 3. Levantar Servicios con Docker

```bash
# Build y start de todos los servicios
docker-compose up -d

# Ver logs
docker-compose logs -f

# Verificar que todo esté corriendo
docker-compose ps
```

**Servicios que deberían estar corriendo:**
- `videorama-backend` (FastAPI) - Puerto 8000
- `videorama-frontend` (React) - Puerto 5173
- `videorama-db` (PostgreSQL) - Puerto 5432
- `videorama-redis` (Redis) - Puerto 6379
- `videorama-vhs` (VHS downloader) - Puerto 8080

### 4. Inicializar Base de Datos

```bash
# Ejecutar migraciones de Alembic
docker-compose exec backend alembic upgrade head

# Verificar que se crearon las tablas
docker-compose exec db psql -U videorama -d videorama -c "\dt"
```

### 5. Acceder a la Aplicación

⚠️ **IMPORTANTE:** Debes acceder usando localhost, no la URL de Coder.

Abrir en el navegador:
- **Frontend:** http://localhost:5173 ✅
- **Backend API:** http://localhost:8000 ✅
- **API Docs:** http://localhost:8000/docs ✅

**NO usar URLs de Coder** (el backend requiere autenticación):
- ❌ https://5173--main--javi-dev--... (frontend sin backend)
- ❌ https://8000--main--javi-dev--... (requiere auth)

---

## 🧪 Testing Manual

### Test 1: Settings Page
1. Ir a **Settings** (⚙️)
2. Verificar que se cargan las configuraciones
3. Modificar el nombre de la app
4. Guardar
5. **Verificar toast verde:** "Settings updated successfully"

### Test 2: Libraries
1. Ir a **Libraries** (📚)
2. Click "New Library"
3. Crear library:
   - ID: `movies`
   - Name: `My Movies`
   - Icon: 🎬
   - Path template: `{library}/{year}/{title}`
4. Guardar
5. **Verificar toast verde:** "Library created successfully"

### Test 3: Tags
1. Ir a **Tags** (🏷️)
2. Click "New Tag"
3. Crear tags:
   - `action`
   - `comedy`
   - `2024`
4. Probar **merge**:
   - Seleccionar 2 tags
   - Click "Merge (2)"
   - Elegir target tag
   - Merge
5. **Verificar toasts** en cada operación

### Test 4: Playlists
1. Ir a **Playlists** (📋)
2. Click "New Playlist"
3. Crear **Dynamic Playlist**:
   - Activar toggle "Dynamic Playlist"
   - Filtros:
     - Tags: `action, 2024` (required)
     - Min rating: 4.0
     - Sort by: Rating (desc)
     - Limit: 50
4. Guardar
5. **Verificar toast verde**

### Test 5: Import (URL)
1. Ir a **Inbox** (📥)
2. Probar importar video de YouTube
3. Aprobar en inbox
4. Ver entry creado en **Entries**
5. **Verificar toasts**

### Test 6: Import (Filesystem)
1. Copiar archivos de video a un directorio
2. Usar API para scan:
```bash
curl -X POST http://localhost:8000/api/v1/import/filesystem \
  -H "Content-Type: application/json" \
  -d '{
    "directory_path": "/ruta/a/tus/videos",
    "library_id": "movies",
    "recursive": true,
    "mode": "copy"
  }'
```
3. Verificar entries importados

---

## 📋 Checklist de Features

### ✅ UI Components (100%)
- [x] Modal
- [x] Input, Textarea, Select
- [x] Toggle, Checkbox
- [x] Button, Card
- [x] Toast notifications

### ✅ Páginas (100%)
- [x] Dashboard
- [x] Libraries (CRUD)
- [x] Entries (List + Detail)
- [x] Inbox (Review + Approve)
- [x] Playlists (CRUD + Query Builder)
- [x] Tags (CRUD + Merge)
- [x] Settings

### ✅ Backend APIs (100%)
- [x] Libraries CRUD
- [x] Entries CRUD
- [x] Tags CRUD + Merge
- [x] Playlists CRUD + Dynamic Queries
- [x] Inbox workflow
- [x] Import (URL + Filesystem)
- [x] Settings GET/PUT
- [x] Jobs tracking

### ✅ Core Features (100%)
- [x] URL import (yt-dlp)
- [x] Filesystem import (3 modes)
- [x] LLM classification
- [x] External API enrichment
- [x] Duplicate detection
- [x] Tag hierarchy
- [x] Dynamic playlists
- [x] Toast notifications

---

## 🐛 Troubleshooting

### ⚠️ "Failed to load settings" o Library creation no funciona

**Síntomas:**
- Settings page muestra: "Failed to load settings. Please try again."
- Crear library no hace nada
- No aparecen toasts de error

**Causa:** Frontend no puede conectar con backend (probablemente accediendo desde URL de Coder)

**Solución:**
1. **IMPORTANTE:** Acceder SOLO desde **http://localhost:5173**
2. Verificar configuración:
```bash
# Frontend debe usar localhost:8000
docker-compose exec frontend env | grep VITE_API_URL
# Esperado: VITE_API_URL=http://localhost:8000

# Backend debe aceptar localhost
docker-compose exec backend python -c "from app.config import settings; print(settings.CORS_ORIGINS)"
# Esperado: ['http://localhost:3000', 'http://localhost:5173']
```

3. Si la config es incorrecta:
```bash
# Verificar .env NO tenga VITE_API_URL con URLs de Coder
# CORS_ORIGINS debe ser: http://localhost:3000,http://localhost:5173

# Reiniciar servicios
docker-compose down && docker-compose up -d
```

**Ver guía completa:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

### Backend no inicia
```bash
# Ver logs
docker-compose logs backend

# Común: falta .env
cp backend/.env.example backend/.env

# Rebuild
docker-compose down
docker-compose up -d --build
```

### Frontend no carga
```bash
# Ver logs
docker-compose logs frontend

# Verificar que backend esté corriendo
curl http://localhost:8000/api/v1/libraries

# Rebuild
docker-compose restart frontend
```

### Database errors
```bash
# Reset database (⚠️ BORRA TODOS LOS DATOS)
docker-compose down -v
docker-compose up -d
docker-compose exec backend alembic upgrade head
```

### VHS download fails
```bash
# Verificar que VHS esté corriendo
docker-compose ps vhs

# Ver logs de VHS
docker-compose logs vhs

# Test manual
curl http://localhost:8080/health
```

---

## 🔧 Comandos Útiles

### Docker
```bash
# Ver todos los contenedores
docker-compose ps

# Ver logs de un servicio
docker-compose logs -f backend

# Reiniciar un servicio
docker-compose restart frontend

# Detener todo
docker-compose down

# Limpiar todo (incluyendo volúmenes)
docker-compose down -v
```

### Base de Datos
```bash
# Acceder a PostgreSQL
docker-compose exec db psql -U videorama -d videorama

# Ver tablas
docker-compose exec db psql -U videorama -d videorama -c "\dt"

# Ejecutar query
docker-compose exec db psql -U videorama -d videorama -c "SELECT * FROM libraries;"
```

### Backend
```bash
# Shell en contenedor backend
docker-compose exec backend bash

# Correr migraciones
docker-compose exec backend alembic upgrade head

# Crear nueva migración
docker-compose exec backend alembic revision -m "descripcion"
```

### Frontend
```bash
# Shell en contenedor frontend
docker-compose exec frontend sh

# Reinstalar dependencias
docker-compose exec frontend npm install

# Build para producción
docker-compose exec frontend npm run build
```

---

## 📊 Verificación de Estado

### Health Checks
```bash
# Backend API
curl http://localhost:8000/health

# Frontend (debería cargar HTML)
curl http://localhost:5173

# PostgreSQL
docker-compose exec db pg_isready -U videorama

# Redis
docker-compose exec redis redis-cli ping
```

### Test de API Endpoints
```bash
# Listar libraries
curl http://localhost:8000/api/v1/libraries

# Crear library
curl -X POST http://localhost:8000/api/v1/libraries \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test",
    "name": "Test Library",
    "icon": "🎬"
  }'

# Listar tags
curl http://localhost:8000/api/v1/tags

# Ver settings
curl http://localhost:8000/api/v1/settings
```

---

## 🎯 Próximos Pasos

### Después del Testing
1. ✅ Verificar todas las operaciones CRUD
2. ✅ Probar import de URLs
3. ✅ Probar import de filesystem
4. ✅ Verificar toasts en todas las acciones
5. ✅ Probar dark mode

### Features Opcionales (5%)
Si quieres implementar las features restantes:
- **Celery** - Background job processing
- **Watch Folders** - Auto-import automation
- **Thumbnails** - ffmpeg video thumbnails
- **Audio Extract** - Extract audio from videos

### Deployment
Cuando estés listo para producción:
- Cambiar `DEBUG=false`
- Usar `SECRET_KEY` seguro
- Configurar dominio + SSL
- Usar PostgreSQL externo (opcional)
- Configurar backups
- Añadir monitoring

---

## 📖 Documentación Adicional

- [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) - Log técnico completo
- [SESSION_SUMMARY.md](SESSION_SUMMARY.md) - Resumen Session 1
- [SESSION_2_FINAL_SUMMARY.md](SESSION_2_FINAL_SUMMARY.md) - Resumen Session 2
- Backend API Docs: http://localhost:8000/docs (cuando esté corriendo)

---

## ✅ Estado del Proyecto

**Versión:** 2.0.0 MVP
**Completitud:** ~95%
**Estado:** ✅ Listo para Testing y Uso Básico

**Funciona:**
- ✅ Import de media (URL + filesystem)
- ✅ Organización con libraries
- ✅ Tags con jerarquía y merge
- ✅ Playlists estáticas y dinámicas
- ✅ Gestión completa de entries
- ✅ Configuración via Settings
- ✅ Toast notifications
- ✅ Dark mode
- ✅ Responsive design

**Falta (opcional):**
- ⚠️ Background jobs (Celery)
- ⚠️ Watch folders
- ⚠️ Thumbnails automáticos
- ⚠️ Audio extraction

---

**¡Listo para empezar! 🚀**

Si encuentras algún problema durante el testing, revisa la sección de Troubleshooting o consulta los logs con `docker-compose logs -f`.
