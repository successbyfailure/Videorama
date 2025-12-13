# Videorama v2.0.0 - Reverse Proxy Setup

**Last Updated:** 2025-12-13 20:50

---

## 🎯 Objetivo

Configurar Videorama detrás de un reverse proxy para que funcione así:

```
Browser → https://videorama.example.com/ → Frontend (React)
Browser → https://videorama.example.com/api/v1/* → Backend (FastAPI)
Browser → https://videorama.example.com/docs → API Documentation
```

**Clave:** El frontend usa **URLs relativas** en producción, por lo que funciona con **cualquier proxy reverso** sin configuración especial.

---

## 💡 ¿Por Qué Es Tan Simple?

### Solución: URLs Relativas

En lugar de configurar el frontend para apuntar a un dominio específico, usamos **URLs relativas**:

**Desarrollo (docker-compose):**
```javascript
VITE_API_URL = 'http://localhost:8000'
Request → http://localhost:8000/api/v1/settings
```

**Producción (sin VITE_API_URL configurado):**
```javascript
VITE_API_URL = ''  // Empty!
baseURL = '/api/v1'  // Relative URL

// Browser en: https://videorama.example.com
Request → https://videorama.example.com/api/v1/settings
```

### Ventajas

✅ **No requiere build específico por entorno** - El mismo build funciona en dev y prod
✅ **Funciona con cualquier dominio** - No hardcodeas URLs
✅ **No requiere configuración compleja en Nginx** - Solo proxear `/api` → backend
✅ **Automático SSL/HTTPS** - Usa el protocolo de la página
✅ **No hay CORS issues** - Same-origin requests

### Configuración Nginx Mínima

Solo necesitas **2 location blocks**:

```nginx
# 1. Backend (empieza con /api, /docs, /health, etc.)
location ~ ^/(api|docs|redoc|openapi\.json|health) {
    proxy_pass http://localhost:8000;
    proxy_set_header Host $host;
}

# 2. Frontend (todo lo demás)
location / {
    proxy_pass http://localhost:5173;
    proxy_set_header Host $host;
}
```

**¡Eso es todo!** No necesitas configurar múltiples `location` blocks ni URLs específicas.

---

## 🔧 Configuración del Frontend

**Desarrollo (localhost con docker-compose):**
```typescript
// docker-compose.yml configura:
VITE_API_URL=http://localhost:8000

// Resultado:
baseURL = 'http://localhost:8000/api/v1'
```

**Producción (detrás de proxy reverso):**
```typescript
// NO configurar VITE_API_URL

// Resultado:
baseURL = '/api/v1'  // Relative URL!

// Browser convierte a:
// https://videorama.example.com/api/v1/settings
```

### Variables de Entorno

**Para desarrollo local:**
```env
# docker-compose.yml (ya configurado)
VITE_API_URL=http://localhost:8000
```

**Para producción detrás de proxy:**
```env
# NO configurar VITE_API_URL
# Las URLs relativas funcionan automáticamente
```

---

## 🌐 Opción 1: Nginx (RECOMENDADA)

### Configuración Nginx

Crea `/etc/nginx/sites-available/videorama.conf`:

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name videorama.example.com;

    return 301 https://$server_name$request_uri;
}

# Main HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name videorama.example.com;

    # SSL Configuration (adjust paths to your certificates)
    ssl_certificate /etc/letsencrypt/live/videorama.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/videorama.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;

    # Logging
    access_log /var/log/nginx/videorama-access.log;
    error_log /var/log/nginx/videorama-error.log;

    # Max upload size (for video uploads)
    client_max_body_size 2G;

    # Backend API - Proxy ALL backend paths to port 8000
    # This includes: /api/v1/*, /docs, /redoc, /openapi.json, /health
    location ~ ^/(api|docs|redoc|openapi\.json|health) {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;

        # Proxy headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;

        # Timeouts for long uploads
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;

        # Don't log health checks
        access_log off;
    }

    # Frontend - React/Vite
    location / {
        proxy_pass http://localhost:5173;
        proxy_http_version 1.1;

        # WebSocket support for Vite HMR (development)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files (if serving directly from Nginx in production)
    # Uncomment if you build frontend and serve static files
    # location /assets {
    #     alias /var/www/videorama/frontend/dist/assets;
    #     expires 1y;
    #     add_header Cache-Control "public, immutable";
    # }
}
```

### Activar Configuración

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/videorama.conf /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

---

## 🐳 Opción 2: Nginx en Docker Compose

Añade a tu `docker-compose.yml`:

```yaml
services:
  # ... existing services ...

  nginx:
    image: nginx:alpine
    container_name: videorama-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro  # Your SSL certificates
    depends_on:
      - backend
      - frontend
    restart: unless-stopped
```

Y crea `nginx.conf` en la raíz del proyecto:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream backend {
        server backend:8000;
    }

    upstream frontend {
        server frontend:5173;
    }

    server {
        listen 80;
        server_name videorama.example.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name videorama.example.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        client_max_body_size 2G;

        # Backend - Simple regex for all backend paths
        location ~ ^/(api|docs|redoc|openapi\.json|health) {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            access_log off;
        }

        # Frontend - Everything else
        location / {
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # WebSocket for Vite HMR (development only)
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}
```

---

## 🔷 Opción 3: Traefik

Añade a tu `docker-compose.yml`:

```yaml
services:
  traefik:
    image: traefik:v2.10
    container_name: videorama-traefik
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.myresolver.acme.tlschallenge=true"
      - "--certificatesresolvers.myresolver.acme.email=your@email.com"
      - "--certificatesresolvers.myresolver.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"  # Traefik dashboard
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./letsencrypt:/letsencrypt
    restart: unless-stopped

  backend:
    # ... existing backend config ...
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.backend.rule=Host(`videorama.example.com`) && PathPrefix(`/api`)"
      - "traefik.http.routers.backend.entrypoints=websecure"
      - "traefik.http.routers.backend.tls.certresolver=myresolver"
      - "traefik.http.services.backend.loadbalancer.server.port=8000"

  frontend:
    # ... existing frontend config ...
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=Host(`videorama.example.com`)"
      - "traefik.http.routers.frontend.entrypoints=websecure"
      - "traefik.http.routers.frontend.tls.certresolver=myresolver"
      - "traefik.http.services.frontend.loadbalancer.server.port=5173"
```

---

## 🔐 SSL/TLS Certificates

### Opción A: Let's Encrypt (Certbot)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d videorama.example.com

# Auto-renewal (crontab)
sudo crontab -e
# Add:
0 0 * * * certbot renew --quiet
```

### Opción B: Cloudflare (con Proxy)

1. Apunta tu dominio a Cloudflare
2. Activa el proxy (nube naranja)
3. SSL/TLS mode: Full (strict)
4. Cloudflare maneja SSL automáticamente

### Opción C: Self-Signed (Solo desarrollo)

```bash
# Generate self-signed cert
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ./ssl/privkey.pem \
  -out ./ssl/fullchain.pem \
  -subj "/CN=videorama.local"
```

---

## ⚙️ Configuración del Backend

Actualiza `.env` para producción:

```env
# Application
APP_NAME=Videorama
DEBUG=false  # IMPORTANTE: false en producción
SECRET_KEY=your-super-secret-key-change-this-in-production

# Database (use external/managed PostgreSQL in production)
DATABASE_URL=postgresql://user:pass@postgres-host:5432/videorama

# CORS - Añadir dominio de producción
CORS_ORIGINS=https://videorama.example.com

# Storage
STORAGE_BASE_PATH=/storage

# ... rest of config ...
```

---

## 📊 Verificación

### Test Local (Desarrollo)

```bash
# Frontend
curl http://localhost:5173
# Backend
curl http://localhost:8000/health
```

### Test con Proxy Reverso

```bash
# Frontend
curl https://videorama.example.com
# Should return HTML

# Backend API
curl https://videorama.example.com/api/v1/settings
# Should return JSON

# API Docs
curl https://videorama.example.com/docs
# Should return Swagger UI HTML

# Health check
curl https://videorama.example.com/health
# Should return {"status":"healthy",...}
```

### Test desde Navegador

1. Abre: `https://videorama.example.com`
2. F12 → Console (no debe haber errores)
3. F12 → Network → Refresh
4. Verifica que requests a `/api/v1/settings` van a:
   - ✅ `https://videorama.example.com/api/v1/settings`
   - ❌ NO `http://localhost:8000/api/v1/settings`

---

## 🔍 Troubleshooting

### Error: "Mixed Content" (HTTP/HTTPS)

**Causa:** Frontend en HTTPS intenta llamar backend en HTTP

**Fix:** Asegúrate que todas las requests usen HTTPS (el proxy debe manejar esto)

### Error: 502 Bad Gateway

**Causa:** Nginx no puede conectar con backend/frontend

**Debug:**
```bash
# Verificar que servicios estén corriendo
docker-compose ps

# Verificar que puertos estén listening
netstat -tlnp | grep -E "8000|5173"

# Logs de Nginx
sudo tail -f /var/log/nginx/videorama-error.log
```

### Error: CORS en producción

**Causa:** CORS_ORIGINS no incluye el dominio de producción

**Fix en `.env`:**
```env
CORS_ORIGINS=https://videorama.example.com
```

Restart backend:
```bash
docker-compose restart backend
```

### Frontend hace requests a localhost en producción

**Causa:** VITE_API_URL está hardcodeado

**Fix:** NO configurar VITE_API_URL en producción (dejar que use auto-detection)

```bash
# Verificar
docker-compose exec frontend env | grep VITE_API_URL
# Si muestra localhost, remover del docker-compose.yml environment

# O configurar explícitamente:
VITE_API_URL=https://videorama.example.com
```

---

## 🚀 Producción: Build Optimizado (Opcional)

Para mejor performance, puedes hacer build del frontend y servir archivos estáticos:

### Build Frontend

```bash
# Build production
cd frontend
npm run build

# Output en frontend/dist/
```

### Servir con Nginx (Sin Vite Dev Server)

```nginx
server {
    # ... SSL config ...

    # Serve built frontend files directly
    location / {
        root /var/www/videorama/frontend/dist;
        try_files $uri $uri/ /index.html;

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # Backend API still proxied
    location /api {
        proxy_pass http://localhost:8000;
        # ... proxy headers ...
    }
}
```

### Docker para Producción

```dockerfile
# frontend/Dockerfile.prod
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

---

## 📝 Checklist de Deployment

- [ ] DNS apunta al servidor
- [ ] SSL/TLS certificates configurados
- [ ] Nginx/Traefik instalado y configurado
- [ ] Backend `.env` con DEBUG=false
- [ ] CORS_ORIGINS incluye dominio de producción
- [ ] SECRET_KEY cambiado de default
- [ ] Database en servidor externo/managed (no Docker local)
- [ ] Backups configurados
- [ ] Monitoring configurado (Prometheus/Grafana)
- [ ] Logs rotando correctamente
- [ ] Frontend detecta automáticamente API URL
- [ ] Test completo desde navegador
- [ ] SSL rating A+ en SSLLabs

---

## 🎯 Resumen

**Desarrollo:**
```
Frontend: http://localhost:5173
Backend:  http://localhost:8000
API URL:  Hardcoded a localhost:8000
```

**Producción:**
```
Frontend: https://videorama.example.com
Backend:  https://videorama.example.com/api (proxy)
API URL:  Auto-detected (window.location.origin)
```

**Clave:** El frontend detecta automáticamente si está en desarrollo o producción y ajusta el API URL accordingly.

---

**Created:** 2025-12-13 20:50
**Purpose:** Production deployment with reverse proxy
**Status:** Production-ready configuration
