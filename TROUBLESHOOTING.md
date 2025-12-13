# Videorama v2.0.0 - Troubleshooting Guide

## Issue: Frontend Unable to Connect to Backend

### Symptoms
- Settings page shows: "Failed to load settings. Please try again."
- Library creation does nothing when clicking "Create Library"
- No error toasts appear
- Browser console may show CORS or network errors

### Root Cause Analysis

This issue occurred due to misconfiguration of the frontend API URL when running in different environments (local vs. Coder cloud).

**Background:**
1. The application can be accessed two ways:
   - **Locally**: `http://localhost:5173` (frontend) + `http://localhost:8000` (backend)
   - **Coder Cloud**: `https://5173--main--javi-dev--successbyfailure.coder.mksmad.org` (frontend) + backend URL

2. **The Problem**: Coder's backend URL (`https://8000--main--javi-dev--successbyfailure.coder.mksmad.org`) requires authentication, making it inaccessible from the browser even when the frontend is accessible.

3. **The Solution**: Always use localhost URLs for both frontend and backend when running with Docker Compose.

### Fix Applied

#### 1. Updated `docker-compose.yml`
Changed the frontend environment variable to use env var with localhost fallback:

```yaml
environment:
  - VITE_API_URL=${VITE_API_URL:-http://localhost:8000}  # Uses .env or defaults to localhost
  - VITE_ALLOWED_HOSTS=${VITE_ALLOWED_HOSTS:-localhost}
```

#### 2. Updated `.env` file
Removed the Coder-specific URLs and kept only localhost:

```env
# Removed this line (was causing the issue):
# VITE_API_URL=https://8000--main--javi-dev--successbyfailure.coder.mksmad.org

# Updated CORS to localhost only:
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

#### 3. Restarted Services
```bash
docker-compose down
docker-compose up -d
```

### Verification Steps

Run these commands to verify the fix:

```bash
# 1. Check frontend environment
docker-compose exec frontend env | grep VITE
# Expected: VITE_API_URL=http://localhost:8000

# 2. Check backend CORS
docker-compose exec backend python -c "from app.config import settings; print(settings.CORS_ORIGINS)"
# Expected: ['http://localhost:3000', 'http://localhost:5173']

# 3. Test backend API
curl http://localhost:8000/health
# Expected: {"status":"healthy","app":"Videorama","version":"2.0.0"}

# 4. Test settings endpoint
curl http://localhost:8000/api/v1/settings
# Expected: JSON with app settings

# 5. Test library creation
curl -X POST http://localhost:8000/api/v1/libraries \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test-lib",
    "name": "Test Library",
    "icon": "🎬",
    "default_path": "/storage/test"
  }'
# Expected: HTTP 201 Created
```

### How to Access the Application

#### Local Development (Recommended)
1. Access frontend: **http://localhost:5173**
2. Backend API docs: **http://localhost:8000/docs**
3. All features work with this setup

#### Coder Cloud Access
- ⚠️ **Not supported** for the backend due to authentication requirements
- The frontend can be viewed but won't connect to backend
- **Solution**: Use local access instead

### Related Issues Fixed in This Session

#### Issue 1: Settings API Naming Conflict (CRITICAL)
**Error:** `AttributeError: module 'app.api.v1.settings' has no attribute 'APP_NAME'`

**Cause:** Import collision in `backend/app/main.py`:
```python
from .config import settings  # Config object
from .api.v1 import settings  # API router module - OVERWRITES ABOVE!
```

**Fix:** Renamed `backend/app/api/v1/settings.py` → `settings_api.py`

**Commit:** b9b4515

#### Issue 2: Frontend-Backend Communication
**Symptoms:** Frontend can't load settings or create libraries

**Cause:** Incorrect `VITE_API_URL` pointing to authenticated Coder URL

**Fix:** Configured to use localhost for both services

**Commit:** [This session]

---

## General Troubleshooting

### Backend Won't Start
```bash
# Check logs
docker-compose logs backend --tail 50

# Common fixes:
1. Missing .env file → Copy from .env.example
2. Database not ready → Wait for postgres healthcheck
3. Import errors → Check recent code changes
```

### Frontend Won't Load
```bash
# Check logs
docker-compose logs frontend --tail 30

# Common fixes:
1. Backend not running → docker-compose up -d backend
2. Port conflict → Stop other services on port 5173
3. Build cache → docker-compose down && docker-compose up -d --build
```

### CORS Errors in Browser
```bash
# Check CORS configuration
docker-compose exec backend python -c "from app.config import settings; print(settings.CORS_ORIGINS)"

# Fix: Update .env
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Restart backend
docker-compose restart backend
```

### Database Connection Errors
```bash
# Check database is healthy
docker-compose ps postgres
# Should show "healthy" status

# Reset database (⚠️ DELETES ALL DATA)
docker-compose down -v
docker-compose up -d
docker-compose exec backend alembic upgrade head
```

---

## Quick Commands Reference

### Services Management
```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Rebuild and restart
docker-compose down && docker-compose up -d --build

# View all logs
docker-compose logs -f

# View specific service
docker-compose logs backend -f
```

### Health Checks
```bash
# All services status
docker-compose ps

# Backend health
curl http://localhost:8000/health

# Database connection
docker-compose exec db pg_isready -U videorama

# Redis connection
docker-compose exec redis redis-cli ping
```

### Database Operations
```bash
# Run migrations
docker-compose exec backend alembic upgrade head

# Access PostgreSQL
docker-compose exec postgres psql -U videorama -d videorama

# View tables
docker-compose exec postgres psql -U videorama -d videorama -c "\dt"
```

---

## Common Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| `Failed to load settings` | Frontend can't reach backend | Check VITE_API_URL and CORS |
| `AttributeError: 'module' has no attribute` | Import collision | Check for naming conflicts |
| `CORS policy: No 'Access-Control-Allow-Origin'` | CORS misconfiguration | Update CORS_ORIGINS in .env |
| `Connection refused` | Backend not running | `docker-compose up -d backend` |
| `404 Not Found` on API | Wrong URL or route not registered | Check API docs at /docs |

---

## Support & Documentation

- **Quick Start Guide**: See [QUICK_START.md](QUICK_START.md)
- **Implementation Log**: See [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md)
- **Session Summaries**:
  - Session 1: [SESSION_SUMMARY.md](SESSION_SUMMARY.md)
  - Session 2: [SESSION_2_FINAL_SUMMARY.md](SESSION_2_FINAL_SUMMARY.md)
- **API Documentation**: http://localhost:8000/docs (when running)

---

**Last Updated:** 2025-12-13
**Issue Fixed:** Frontend-backend communication failure
**Status:** ✅ Resolved
