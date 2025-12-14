# Videorama v2.0 - Próximos Pasos

**Para el siguiente agente IA**
**Fecha:** 2025-12-14

---

## 📖 Lee Primero

**DOCUMENTACIÓN CLAVE:**
1. 📄 [CURRENT_STATUS.md](CURRENT_STATUS.md) - Estado completo del sistema (LÉELO PRIMERO)
2. 📋 [IMPLEMENTATION_PLAN_V2.0.md](IMPLEMENTATION_PLAN_V2.0.md) - Plan completo de desarrollo
3. 🐳 [DOCKER_SETUP.md](DOCKER_SETUP.md) - Setup de Docker
4. 🔧 [DOCKER_TROUBLESHOOTING.md](DOCKER_TROUBLESHOOTING.md) - Troubleshooting

---

## ✅ Estado Actual (Resumen)

### LO QUE FUNCIONA
- ✅ Import Manager (URL + Search) - 100% funcional
- ✅ LLM Classification - confidence scoring 0.8+ (FIXED!)
- ✅ Jobs Queue con cancel/delete
- ✅ Inbox Management con approve/reject/reprobe/redownload
- ✅ Celery Worker + Beat (cleanup automático)
- ✅ Auto-refresh en UI (Jobs: 2s, Inbox: 3s)
- ✅ VHS Service integration (download + search)
- ✅ File downloads a /storage/temp

### LO QUE NECESITA ARREGLO
- ⚠️ Inbox approve tested pero puede mejorar UX
- ⚠️ Algunos URLs de YouTube fallan en VHS probe (issue del servicio VHS externo)

---

## 🎯 ~~PRIORIDAD 1: Arreglar LLM Service~~ ✅ COMPLETADO

### ✅ Resuelto en Sesión 4 (2025-12-14)

**Problema:** Modelo `qwen3:14b` (reasoning model) necesitaba más tokens

**Solución:**
- Aumentado max_tokens: 100→300, 800→2000, 1000→1500
- Fallback a `reasoning_content` para modelos de razonamiento
- Logging detallado agregado

**Resultado:**
- Confidence 0.85 en tests
- Auto-import funcionando correctamente
- Título extraído correctamente

**Ver detalles:** [CURRENT_STATUS.md](CURRENT_STATUS.md) - Sesión 4

---

## 🎯 NUEVA PRIORIDAD 1: Streaming Endpoint

### Objetivo
Permitir seek/scrubbing en video player

### Nuevo Endpoint
`GET /api/v1/entries/{uuid}/stream`

### Implementación Sugerida
```python
from fastapi.responses import StreamingResponse
from fastapi import Header
from pathlib import Path

@router.get("/entries/{uuid}/stream")
async def stream_entry(
    uuid: str,
    range: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    # 1. Get entry and file
    # 2. Parse Range header
    # 3. Return 206 Partial Content with proper headers
```

**Frontend Update:**
```typescript
<video src={`/api/v1/entries/${entry.uuid}/stream`} controls />
```

---

## 🎯 PRIORIDAD 2 (LEGACY - Puede mejorarse): Inbox Approve

### Problema
El endpoint `/api/v1/inbox/{id}/approve` existe pero:
- No está tested end-to-end
- Puede fallar si entry_data no tiene `file_path`
- Algunos items en inbox son de imports fallidos (no tienen archivo)

### Archivo Principal
`backend/app/api/v1/inbox.py` líneas 56-150

### Análisis Actual
```python
@router.post("/inbox/{inbox_id}/approve")
def approve_inbox_item(inbox_id: str, db: Session = Depends(get_db)):
    # 1. Lee inbox item
    # 2. Parse entry_data
    # 3. Extrae file_path y content_hash
    # 4. Llama _create_entry_from_import()

    # PROBLEMA: ¿Qué pasa si NO hay file_path?
```

### Casos a Manejar

**Caso 1: Item de "low_confidence" (tiene archivo)**
- entry_data tiene: title, original_url, metadata, enriched
- Archivo ya descargado en /storage/temp/
- ✅ Crear entry directamente

**Caso 2: Item de "failed" (NO tiene archivo)**
- entry_data solo tiene: original_url
- Archivo no se descargó (por error)
- ❌ Necesita re-trigger download

**Caso 3: Item de "duplicate" (no hay archivo nuevo)**
- entry_data tiene: title, original_url, duplicate_of
- Archivo ya existe en otra entry
- ❌ No crear entry, solo notificar

### Solución Sugerida

```python
@router.post("/inbox/{inbox_id}/approve")
def approve_inbox_item(
    inbox_id: str,
    override_library: Optional[str] = None,  # Permitir cambiar library
    db: Session = Depends(get_db)
):
    item = db.query(InboxItem).filter(InboxItem.id == inbox_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")

    entry_data = item.entry_data  # Ya es dict gracias a validator

    # Check inbox type
    if item.type == "duplicate":
        # No crear entry, marcar como reviewed
        item.reviewed = True
        db.commit()
        return {"message": "Duplicate acknowledged", "inbox_id": inbox_id}

    if item.type == "failed":
        # Re-trigger import with original URL
        url = entry_data.get("original_url")
        if not url:
            raise HTTPException(400, "No URL to retry")

        # Create new import job
        from ..services.import_service import ImportService
        import_service = ImportService(db)
        result = await import_service.import_from_url(
            url=url,
            library_id=override_library or item.suggested_library
        )

        # Mark old inbox item as reviewed
        item.reviewed = True
        db.commit()

        return {
            "message": "Import re-triggered",
            "inbox_id": inbox_id,
            "new_job_id": result["job_id"]
        }

    # For "low_confidence" type
    # Check if we have file info
    if "file_path" not in entry_data or "content_hash" not in entry_data:
        # File was never downloaded, need to re-download
        # Similar to failed case
        pass

    # Normal approve flow...
```

### Testing Steps
1. Aprobar item tipo "low_confidence"
2. Verificar entry creado en library
3. Verificar archivo movido de /storage/temp a /storage/{library}/
4. Verificar inbox item marcado reviewed=true
5. Verificar en frontend que item desaparece de inbox

---

## 🎯 PRIORIDAD 3: Streaming Endpoint

### Objetivo
Permitir seek/scrubbing en video player

### Nuevo Endpoint
`GET /api/v1/entries/{uuid}/stream`

### Implementación
```python
from fastapi.responses import StreamingResponse
from fastapi import Header
from pathlib import Path
import os

@router.get("/entries/{uuid}/stream")
async def stream_entry(
    uuid: str,
    range: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    # 1. Get entry and file
    entry = db.query(Entry).filter(Entry.uuid == uuid).first()
    if not entry:
        raise HTTPException(404, "Entry not found")

    entry_file = db.query(EntryFile).filter(EntryFile.entry_uuid == uuid).first()
    if not entry_file:
        raise HTTPException(404, "File not found")

    file_path = Path(entry_file.file_path)
    if not file_path.exists():
        raise HTTPException(404, "Physical file not found")

    file_size = file_path.stat().st_size

    # 2. Handle Range request
    if range:
        # Parse: "bytes=0-1023" or "bytes=1024-"
        range_str = range.replace("bytes=", "")
        start, end = range_str.split("-")
        start = int(start) if start else 0
        end = int(end) if end else file_size - 1

        # Validate range
        if start >= file_size or end >= file_size:
            raise HTTPException(416, "Range not satisfiable")

        chunk_size = end - start + 1

        def file_iterator():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    chunk = f.read(min(8192, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            file_iterator(),
            status_code=206,  # Partial Content
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
                "Content-Type": entry_file.file_type or "video/mp4"
            }
        )

    # 3. Full file (no Range)
    return FileResponse(
        file_path,
        media_type=entry_file.file_type or "video/mp4",
        headers={"Accept-Ranges": "bytes"}
    )
```

### Frontend Update
```typescript
// En Entry detail page, cambiar src del video:

<video
  src={`/api/v1/entries/${entry.uuid}/stream`}
  controls
  className="w-full"
/>

// El browser automáticamente usará Range requests
```

---

## 📝 Comandos Útiles

### Ver Estado del Sistema
```bash
cd /home/coder/projects/Videorama
docker-compose ps
```

### Ver Logs en Tiempo Real
```bash
# Backend
docker-compose logs -f backend

# Celery Worker (aquí se ven los imports)
docker-compose logs -f celery-worker

# Frontend
docker-compose logs -f frontend

# Todos
docker-compose logs -f
```

### Reiniciar Servicios
```bash
docker-compose restart backend
docker-compose restart celery-worker
docker-compose restart frontend
```

### Rebuild con Cambios
```bash
# Sin cache (si cambios importantes)
docker-compose build --no-cache backend
docker-compose build --no-cache frontend

# Con cache (más rápido)
docker-compose build backend
docker-compose up -d
```

### Ejecutar Scripts en Backend
```bash
docker-compose exec -T backend python3 -c "
from app.database import SessionLocal
from app.models import Job, InboxItem

db = SessionLocal()
jobs = db.query(Job).count()
inbox = db.query(InboxItem).count()
print(f'Jobs: {jobs}, Inbox items: {inbox}')
db.close()
"
```

### Acceder a PostgreSQL
```bash
docker-compose exec postgres psql -U videorama -d videorama

# Queries útiles:
SELECT id, status, progress, current_step FROM jobs ORDER BY created_at DESC LIMIT 5;
SELECT id, type, reviewed FROM inbox ORDER BY created_at DESC LIMIT 5;
```

---

## 🚦 Flujo de Desarrollo Recomendado

### 1. Primera Sesión: Familiarización
- [ ] Lee CURRENT_STATUS.md completo
- [ ] Verifica que servicios corran: `docker-compose ps`
- [ ] Accede a UI: http://localhost/
- [ ] Prueba importar una URL
- [ ] Revisa logs: `docker-compose logs -f celery-worker`

### 2. Segunda Sesión: Debug LLM
- [ ] Ejecuta test manual del LLM endpoint (ver arriba)
- [ ] Agrega logging a llm_service.py
- [ ] Reinicia celery-worker
- [ ] Trigger nuevo import
- [ ] Analiza logs para ver qué falla

### 3. Tercera Sesión: Fix + Testing
- [ ] Aplica fix basado en logs
- [ ] Test con varios imports
- [ ] Verifica confidence scores
- [ ] Verifica auto-import funciona

### 4. Cuarta Sesión: Inbox Approve
- [ ] Lee código actual de approve endpoint
- [ ] Implementa mejoras sugeridas
- [ ] Test con item tipo "low_confidence"
- [ ] Test con item tipo "failed"
- [ ] Verifica entry se crea correctamente

---

## ⚠️ Precauciones

### NO Hacer
- ❌ NO cambiar estructura de base de datos sin migración
- ❌ NO modificar docker-compose.yml sin backup
- ❌ NO borrar archivos de /storage sin verificar
- ❌ NO hacer cambios grandes sin commit intermedio

### SÍ Hacer
- ✅ Hacer commits frecuentes
- ✅ Leer logs antes de hacer cambios
- ✅ Test en local antes de hacer cambios grandes
- ✅ Documentar cambios importantes
- ✅ Agregar logging para debugging

---

## 📚 Recursos

- **OpenAI API Docs:** https://platform.openai.com/docs/api-reference
- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **Celery Docs:** https://docs.celeryq.dev/
- **React Query Docs:** https://tanstack.com/query/latest/docs/react/overview
- **VHS API:** https://vhs.mksmad.org/docs/api

---

## 💡 Tips

1. **Debugging LLM:** El problema suele ser formato de respuesta, no conectividad
2. **Celery Logs:** Son tu mejor amigo para ver qué pasa en imports
3. **Auto-refresh:** Si cambias código backend, reinicia celery-worker también
4. **PostgreSQL:** Usa `\dt` para ver tablas, `\d table_name` para schema
5. **React DevTools:** Útil para ver queries de TanStack Query

---

**¡Buena suerte con el desarrollo! 🚀**

Lee CURRENT_STATUS.md primero y empieza con PRIORIDAD 1 (LLM) o PRIORIDAD 2 (Inbox Approve)
