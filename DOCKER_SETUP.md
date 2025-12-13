# Videorama v2.0.0 - Docker Setup Guide

Quick start guide for running Videorama with Docker Compose.

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- At least 2GB free disk space

## Quick Start

1. **Copy environment file**
   ```bash
   cp .env.example .env
   ```

2. **Edit .env file**

   Required configurations:
   - `OPENAI_API_KEY` - Your OpenAI API key or compatible endpoint
   - `OPENAI_BASE_URL` - API base URL (default: OpenAI)

   Optional configurations:
   - `TMDB_API_KEY` - For movie metadata enrichment
   - `SPOTIFY_CLIENT_ID/SECRET` - For music metadata enrichment
   - `TELEGRAM_BOT_TOKEN` - If using Telegram bot integration

3. **Start all services**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## Services

The stack includes:

- **postgres** - PostgreSQL 16 database (port 5432)
- **redis** - Redis for background tasks (port 6379)
- **backend** - FastAPI application (port 8000)
- **celery-worker** - Background task processor
- **frontend** - React application (port 5173)

## Common Commands

### View logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Restart a service
```bash
docker-compose restart backend
```

### Stop all services
```bash
docker-compose down
```

### Stop and remove volumes (⚠️ deletes database)
```bash
docker-compose down -v
```

### Rebuild after code changes
```bash
docker-compose up -d --build
```

## Database Management

### Access PostgreSQL
```bash
docker exec -it videorama-postgres psql -U videorama -d videorama
```

### Run migrations (if needed)
```bash
docker exec -it videorama-backend alembic upgrade head
```

### Create new migration
```bash
docker exec -it videorama-backend alembic revision --autogenerate -m "description"
```

## Development Tips

### Live reload
Both backend and frontend are configured for hot reload:
- Backend: Edit files in `backend/` - uvicorn will auto-reload
- Frontend: Edit files in `frontend/` - Vite will auto-reload

### Check service health
```bash
# Backend health check
curl http://localhost:8000/health

# PostgreSQL
docker exec videorama-postgres pg_isready -U videorama

# Redis
docker exec videorama-redis redis-cli ping
```

### Storage directories
Media files are stored in `./storage/`:
- `libraries/` - Organized media files
- `temp/` - Temporary downloads
- `thumbnails/` - Generated thumbnails
- `backups/` - Database backups

## Troubleshooting

### Port already in use
If ports 5432, 6379, 8000, or 5173 are in use:
1. Stop conflicting services
2. Or edit `docker-compose.yml` to use different ports

### Database connection errors
```bash
# Check if postgres is ready
docker-compose ps postgres

# View postgres logs
docker-compose logs postgres
```

### Backend won't start
```bash
# Check backend logs
docker-compose logs backend

# Rebuild backend
docker-compose up -d --build backend
```

### Celery tasks not running
```bash
# Check celery worker logs
docker-compose logs celery-worker

# Restart celery worker
docker-compose restart celery-worker
```

## Production Deployment

For production:

1. **Change credentials in .env**
   - Generate secure `SECRET_KEY`
   - Use strong database password
   - Set `DEBUG=False`

2. **Use production database**
   - Point to external PostgreSQL
   - Regular backups

3. **Configure reverse proxy**
   - Use nginx/traefik in front
   - Enable HTTPS
   - Configure proper CORS origins

4. **Resource limits**
   - Add resource limits to docker-compose.yml
   - Monitor with Prometheus/Grafana

5. **Persistent storage**
   - Mount `./storage` to persistent volume
   - Regular backups of PostgreSQL data

## Integration with VHS

If using VHS (Video Hosting Service) for video downloads:

1. Uncomment VHS service in `docker-compose.yml`
2. Set `VHS_BASE_URL=http://vhs:8000` in `.env`
3. Restart services

## Next Steps

- Read [API Documentation](http://localhost:8000/docs)
- Configure your first library via API or frontend
- Set up watch folders for automatic imports
- Configure Telegram bot for remote imports
