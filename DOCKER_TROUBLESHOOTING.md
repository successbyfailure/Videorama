# Docker Troubleshooting - Videorama v2.0

## Error: "failed to read dockerfile: open Dockerfile: no such file or directory"

### Causa Común
Este error ocurre cuando Docker no puede encontrar el Dockerfile en el contexto de build especificado.

### Soluciones

#### 1. Verificar que estás en el directorio correcto
```bash
# Debes estar en el directorio raíz del proyecto
cd /path/to/Videorama

# Verifica que estás en el lugar correcto
ls -la docker-compose.yml
# Deberías ver el archivo docker-compose.yml

# Verifica que los Dockerfiles existen
ls -la backend/Dockerfile frontend/Dockerfile
# Deberías ver ambos archivos
```

#### 2. Usar docker compose (v2) en lugar de docker-compose (v1)
```bash
# Nuevo (Docker Compose V2 - recomendado)
docker compose build
docker compose up -d

# Antiguo (Docker Compose V1)
docker-compose build
docker-compose up -d
```

#### 3. Construir servicios individualmente
```bash
# Construir solo el backend
docker compose build backend

# Construir solo el frontend
docker compose build frontend

# Construir todo
docker compose build
```

#### 4. Verificar permisos de archivos
```bash
# Los Dockerfiles deben ser legibles
chmod 644 backend/Dockerfile
chmod 644 frontend/Dockerfile
```

#### 5. Limpiar caché de Docker
```bash
# Limpiar build cache
docker builder prune

# Rebuild sin caché
docker compose build --no-cache
```

#### 6. Verificar versión de Docker
```bash
# Verificar versión
docker --version
docker compose version

# Requiere:
# - Docker Engine 20.10+
# - Docker Compose 2.0+
```

## Otros Errores Comunes

### Error: Port already in use
```bash
# Encontrar qué está usando el puerto
sudo lsof -i :8000  # Backend
sudo lsof -i :5173  # Frontend
sudo lsof -i :5432  # PostgreSQL
sudo lsof -i :6379  # Redis

# Matar el proceso
sudo kill -9 <PID>

# O cambiar el puerto en docker-compose.yml
```

### Error: Permission denied (storage)
```bash
# Dar permisos al directorio storage
chmod -R 755 storage/
```

### Error: Cannot connect to Docker daemon
```bash
# Iniciar Docker
sudo systemctl start docker

# O en macOS
open -a Docker
```

### Error: requirements.txt not found
```bash
# Verificar que existe
ls -la backend/requirements.txt

# Si no existe, hay un problema con el repositorio
git status
```

## Comandos Útiles

### Ver logs
```bash
# Todos los servicios
docker compose logs -f

# Un servicio específico
docker compose logs -f backend
docker compose logs -f frontend
```

### Reiniciar servicios
```bash
# Reiniciar todo
docker compose restart

# Reiniciar un servicio
docker compose restart backend
```

### Detener servicios
```bash
# Detener sin borrar
docker compose stop

# Detener y borrar contenedores
docker compose down

# Detener, borrar contenedores Y volúmenes (⚠️ borra la base de datos)
docker compose down -v
```

### Ejecutar comandos en contenedores
```bash
# Shell en el backend
docker compose exec backend bash

# Shell en la base de datos
docker compose exec postgres psql -U videorama -d videorama

# Ver proceso de Python
docker compose exec backend ps aux
```

### Reconstruir completamente
```bash
# Detener todo
docker compose down -v

# Limpiar todo
docker system prune -a --volumes

# Reconstruir sin caché
docker compose build --no-cache

# Iniciar
docker compose up -d
```

## Verificación de Setup Correcto

### 1. Estructura de archivos
```
Videorama/
├── docker-compose.yml          ✓ Debe existir
├── .env                        ✓ Copiado de .env.example
├── backend/
│   ├── Dockerfile              ✓ Debe existir
│   ├── requirements.txt        ✓ Debe existir
│   ├── .dockerignore          ✓ Debe existir
│   └── app/
│       └── main.py            ✓ Debe existir
├── frontend/
│   ├── Dockerfile              ✓ Debe existir
│   ├── package.json            ✓ Debe existir
│   ├── .dockerignore          ✓ Debe existir
│   └── src/
│       └── main.tsx           ✓ Debe existir
└── storage/
    └── .gitkeep               ✓ Debe existir
```

### 2. Contenido de .env
```bash
# Verificar que .env existe
cat .env

# Debe contener al menos:
# - DATABASE_URL
# - OPENAI_API_KEY (o configuración LLM)
# - VHS_BASE_URL (si usas VHS)
```

### 3. Docker funcionando
```bash
# Docker debe estar corriendo
docker ps

# Debe mostrar contenedores (o lista vacía sin error)
```

## Inicio Limpio (Fresh Start)

Si nada funciona, intenta esto:

```bash
# 1. Detener y limpiar todo
docker compose down -v
docker system prune -a --volumes -f

# 2. Verificar archivos
ls -la docker-compose.yml backend/Dockerfile frontend/Dockerfile

# 3. Verificar .env
cp .env.example .env
nano .env  # Editar y añadir claves necesarias

# 4. Verificar permisos
chmod 644 backend/Dockerfile frontend/Dockerfile
chmod -R 755 storage/

# 5. Construir
docker compose build --no-cache

# 6. Iniciar
docker compose up -d

# 7. Ver logs
docker compose logs -f
```

## Verificación de Servicios

Una vez iniciado, verifica:

```bash
# 1. Todos los contenedores corriendo
docker compose ps
# Deberías ver: postgres, redis, backend, frontend, celery-worker

# 2. Backend funcionando
curl http://localhost:8000/health
# Debe retornar: {"status":"healthy",...}

# 3. Frontend accesible
curl http://localhost:5173
# Debe retornar HTML

# 4. PostgreSQL conectado
docker compose exec backend python -c "from app.database import init_db; init_db()"
# No debe dar error

# 5. Logs sin errores
docker compose logs backend | grep -i error
docker compose logs frontend | grep -i error
```

## Soporte

Si el problema persiste:

1. **Recopila información**:
   ```bash
   docker --version > debug.txt
   docker compose version >> debug.txt
   docker compose ps >> debug.txt
   docker compose logs >> debug.txt
   ```

2. **Verifica el README**: Lee `DOCKER_SETUP.md` para instrucciones completas

3. **Revisa los issues**: Busca en GitHub si otros han tenido el mismo problema

4. **Información útil para reportar**:
   - Sistema operativo
   - Versión de Docker
   - Logs completos del error
   - Salida de `docker compose ps`
   - Contenido de `docker-compose.yml` (sin secretos)
