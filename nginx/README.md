# Nginx Reverse Proxy Configuration

This directory contains the Nginx configuration for Videorama's integrated reverse proxy.

## How It Works

```
Browser → http://localhost:80 (nginx)
  ├─ /api/v1/* → backend:8000 (FastAPI)
  ├─ /docs → backend:8000/docs (Swagger UI)
  ├─ /health → backend:8000/health
  └─ / → frontend:5173 (React/Vite)
```

## Configuration

**File:** `nginx.conf`

### Backend Routes (Regex Match)
```nginx
location ~ ^/(api|docs|redoc|openapi\.json|health) {
    proxy_pass http://backend;
    ...
}
```

Matches:
- `/api/v1/*` - All API endpoints
- `/docs` - Swagger UI
- `/redoc` - ReDoc UI
- `/openapi.json` - OpenAPI spec
- `/health` - Health check

### Frontend Routes (Everything Else)
```nginx
location / {
    proxy_pass http://frontend;
    ...
}
```

Matches all other routes and proxies to Vite dev server.

## Development

**Access application:**
```bash
# Through Nginx (recommended)
http://localhost

# Direct access (if ports are uncommented in docker-compose.yml)
http://localhost:5173  # Frontend
http://localhost:8000  # Backend
```

**Test endpoints:**
```bash
# Frontend
curl http://localhost

# Backend API
curl http://localhost/api/v1/settings

# Health check
curl http://localhost/health

# API Docs
curl http://localhost/docs
```

## Production

### Enable HTTPS

1. **Get SSL certificates** (Let's Encrypt example):
```bash
# On host machine
sudo certbot certonly --standalone -d videorama.example.com
sudo cp /etc/letsencrypt/live/videorama.example.com/fullchain.pem ./ssl/
sudo cp /etc/letsencrypt/live/videorama.example.com/privkey.pem ./ssl/
```

2. **Uncomment HTTPS server block** in `nginx.conf`:
```nginx
server {
    listen 443 ssl http2;
    server_name videorama.example.com;
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ...
}
```

3. **Mount SSL certificates** in `docker-compose.yml`:
```yaml
nginx:
  ports:
    - "443:443"
  volumes:
    - ./ssl:/etc/nginx/ssl:ro
```

4. **Update CORS** in `.env`:
```env
CORS_ORIGINS=https://videorama.example.com
```

5. **Restart:**
```bash
docker-compose down
docker-compose up -d
```

## Features

✅ **Automatic routing** - No complex configuration
✅ **WebSocket support** - For Vite HMR
✅ **Long upload timeouts** - 300s for video uploads
✅ **Security headers** - X-Frame-Options, X-Content-Type-Options, etc.
✅ **No health check logging** - Cleaner logs
✅ **2GB upload limit** - For large videos

## Troubleshooting

### 502 Bad Gateway

**Cause:** Backend or frontend not running

**Fix:**
```bash
docker-compose ps  # Check services are running
docker-compose logs backend  # Check for errors
docker-compose logs frontend
```

### 404 Not Found on /api/*

**Cause:** Backend not accessible from nginx

**Debug:**
```bash
# From nginx container
docker-compose exec nginx wget -O- http://backend:8000/health

# Should return {"status":"healthy",...}
```

### Frontend not loading

**Cause:** Frontend not accessible from nginx

**Debug:**
```bash
# From nginx container
docker-compose exec nginx wget -O- http://frontend:5173

# Should return HTML
```

### CORS errors in browser

**Cause:** CORS not configured for nginx origin

**Fix in `.env`:**
```env
CORS_ORIGINS=http://localhost,http://localhost:80
```

Then restart:
```bash
docker-compose restart backend
```

## Architecture

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ http://localhost:80
       ↓
┌─────────────┐
│    Nginx    │ (Port 80/443)
│  Reverse    │
│    Proxy    │
└──────┬──────┘
       │
       ├─ /api/* ──→ ┌──────────┐
       │             │ Backend  │ (Port 8000)
       │             │ FastAPI  │
       │             └──────────┘
       │
       └─ / ────────→ ┌──────────┐
                      │ Frontend │ (Port 5173)
                      │ Vite     │
                      └──────────┘
```

## Files

- `nginx.conf` - Main Nginx configuration
- `README.md` - This file
- `ssl/` - SSL certificates (create this directory for production)

## See Also

- [REVERSE_PROXY_SETUP.md](../REVERSE_PROXY_SETUP.md) - Complete reverse proxy guide
- [docker-compose.yml](../docker-compose.yml) - Service configuration
