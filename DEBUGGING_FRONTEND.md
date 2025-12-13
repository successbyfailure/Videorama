# Debugging Frontend Issues - Videorama v2.0.0

**Last Updated:** 2025-12-13 20:45

---

## 🔍 Current Status

### Backend Status: ✅ WORKING CORRECTLY

```bash
# Test realizado:
$ curl http://localhost:8000/api/v1/settings
✅ Response 200 OK con datos correctos

$ curl -H "Origin: http://localhost:5173" http://localhost:8000/api/v1/settings
✅ CORS headers correctos: access-control-allow-origin: http://localhost:5173

# Logs del backend (19:31:51):
INFO: 172.21.0.1:41748 - "GET /api/v1/settings HTTP/1.1" 200 OK
INFO: 172.21.0.1:56222 - "GET /api/v1/libraries HTTP/1.1" 200 OK
```

**Conclusión:** El backend está recibiendo requests del navegador y respondiendo correctamente.

### Frontend Status: ⚠️ POSIBLE CACHE ISSUE

El frontend está sirviendo en http://localhost:5173 pero puede tener:
- Cache de React Query con errores antiguos
- Cache del navegador
- Service Workers activos

---

## 🔧 Solución: Hard Refresh del Navegador

### Paso 1: Hard Refresh (Limpia el Cache)

**En Chrome/Edge:**
1. Abre http://localhost:5173
2. Presiona: **Ctrl + Shift + R** (Windows/Linux) o **Cmd + Shift + R** (Mac)
3. O también: **Ctrl + F5**

**En Firefox:**
1. Abre http://localhost:5173
2. Presiona: **Ctrl + Shift + R** o **Ctrl + F5**

**En Safari:**
1. Abre http://localhost:5173
2. Presiona: **Cmd + Option + R**

### Paso 2: Verificar Consola del Navegador

1. Presiona **F12** para abrir DevTools
2. Ve a la pestaña **Console**
3. Busca errores en rojo (especialmente relacionados con:
   - `net::ERR_CONNECTION_REFUSED`
   - `CORS`
   - `Failed to fetch`
   - `Network Error`

### Paso 3: Verificar Network Tab

1. En DevTools, ve a la pestaña **Network**
2. Refresh la página (**Ctrl + R**)
3. Busca la request a `/api/v1/settings`
4. Verifica:
   - ✅ Status: 200 OK
   - ✅ Request URL: `http://localhost:8000/api/v1/settings`
   - ✅ Response Headers: debe incluir `access-control-allow-origin`

---

## 🐛 Debugging Común

### Problema 1: "Failed to load settings"

**Síntoma:** Settings page muestra error

**Causas posibles:**
1. React Query tiene cached error del problema anterior
2. Frontend está usando API URL incorrecta
3. CORS bloqueando requests

**Debug:**

```bash
# 1. Verificar configuración del frontend
docker-compose exec frontend env | grep VITE_API_URL
# Debe mostrar: VITE_API_URL=http://localhost:8000

# 2. Verificar CORS del backend
docker-compose exec backend python -c "from app.config import settings; print(settings.CORS_ORIGINS)"
# Debe mostrar: ['http://localhost:3000', 'http://localhost:5173']

# 3. Test directo del API
curl -H "Origin: http://localhost:5173" http://localhost:8000/api/v1/settings
# Debe devolver JSON con settings
```

**Fix:**
1. Hard refresh del navegador (Ctrl + Shift + R)
2. Borrar cookies y cache del navegador
3. Probar en modo incógnito/privado

### Problema 2: Library creation "no hace nada"

**Síntoma:** Click en "Create Library" button, modal no se abre

**Causas posibles:**
1. JavaScript error en consola
2. Event handler no registrado
3. Modal component con error

**Debug:**

1. Abre DevTools → Console (F12)
2. Click en "New Library" button
3. Busca errores en rojo en la consola

**Verificar en Network tab:**
- ¿Se hace alguna request al backend al hacer click?
- Si NO → problema en el frontend (JavaScript)
- Si SÍ → verificar response

### Problema 3: No aparecen toasts

**Síntoma:** Operaciones se completan pero no hay feedback visual

**Causa:** ToastProvider no está correctamente montado

**Verificar:**

```bash
# Verificar que ToastContainer está en main.tsx
grep -A 5 "ToastProvider" frontend/src/main.tsx
```

---

## 📊 Verificación Completa del Sistema

### Script de Verificación

Ejecuta estos comandos para verificar todo:

```bash
cd /home/coder/projects/Videorama

echo "=== VERIFICACIÓN COMPLETA ==="
echo ""
echo "1. Servicios Docker:"
docker-compose ps | grep -E "backend|frontend|postgres|redis"
echo ""

echo "2. Backend Health:"
curl -s http://localhost:8000/health | jq .
echo ""

echo "3. Settings API:"
curl -s http://localhost:8000/api/v1/settings | jq '{app_name, version}'
echo ""

echo "4. CORS Test:"
curl -s -H "Origin: http://localhost:5173" -I http://localhost:8000/api/v1/settings | grep -i access-control
echo ""

echo "5. Frontend Environment:"
docker-compose exec frontend env | grep VITE_API_URL
echo ""

echo "6. Backend CORS Config:"
docker-compose exec backend python -c "from app.config import settings; print('CORS:', settings.CORS_ORIGINS)"
echo ""

echo "=== FIN VERIFICACIÓN ==="
```

**Expected Output:**

```
1. Servicios Docker:
✅ videorama-backend    Up
✅ videorama-frontend   Up
✅ videorama-postgres   Healthy
✅ videorama-redis      Healthy

2. Backend Health:
✅ {"status":"healthy","app":"Videorama","version":"2.0.0"}

3. Settings API:
✅ {"app_name":"Videorama","version":"2.0.0"}

4. CORS Test:
✅ access-control-allow-origin: http://localhost:5173

5. Frontend Environment:
✅ VITE_API_URL=http://localhost:8000

6. Backend CORS Config:
✅ CORS: ['http://localhost:3000', 'http://localhost:5173']
```

Si todo muestra ✅ pero el navegador aún no funciona → **HARD REFRESH REQUIRED**

---

## 🔄 Reset Completo (Last Resort)

Si nada funciona, reset completo:

```bash
cd /home/coder/projects/Videorama

# 1. Parar todos los servicios
docker-compose down

# 2. Limpiar cache de Docker (opcional)
docker system prune -f

# 3. Rebuild y restart
docker-compose up -d --build

# 4. Esperar a que estén healthy
sleep 10

# 5. Verificar estado
docker-compose ps
curl http://localhost:8000/health
```

Luego en el navegador:
1. Cerrar TODAS las pestañas de http://localhost:5173
2. Borrar cookies y cache del sitio
3. Abrir nueva pestaña en modo incógnito
4. Ir a http://localhost:5173
5. Verificar que funcione

---

## 📝 Información para Debugging

### Backend Logs (Live)

```bash
docker-compose logs -f backend | grep -E "GET|POST|ERROR"
```

Esto mostrará en tiempo real las requests que llegan al backend.

**Qué buscar:**
- ✅ `GET /api/v1/settings HTTP/1.1" 200` → Settings funciona
- ✅ `GET /api/v1/libraries HTTP/1.1" 200` → Libraries funciona
- ❌ `401 Unauthorized` → Problema de auth (no debería pasar)
- ❌ `CORS` errors → Problema de configuración

### Frontend Logs

```bash
docker-compose logs -f frontend
```

**Qué buscar:**
- ✅ `ready in X ms` → Vite compiló correctamente
- ❌ Errores de compilación → Problema en el código

### Browser DevTools Checklist

**Console Tab:**
- [ ] No hay errores en rojo
- [ ] No hay warnings de CORS
- [ ] No hay "Failed to fetch" errors

**Network Tab:**
- [ ] Request a `/api/v1/settings` existe
- [ ] Status: 200 OK
- [ ] Response contiene JSON válido
- [ ] Headers incluyen `access-control-allow-origin`

**Application Tab:**
- [ ] No hay Service Workers activos (pueden cachear)
- [ ] Cookies de localhost:5173 (si las hay)

---

## 💡 Casos Especiales

### Caso 1: Funciona en Incógnito pero no en Normal

**Causa:** Cache del navegador o Service Worker

**Fix:**
1. En modo normal: F12 → Application → Clear storage
2. Check "Unregister service workers"
3. Click "Clear site data"
4. Refresh

### Caso 2: Settings funciona pero Libraries no

**Causa:** Error específico en LibraryForm component

**Debug:**
1. F12 → Console
2. Click "New Library"
3. Ver error en consola
4. Reportar error específico

### Caso 3: Todo funciona en curl pero no en navegador

**Causa:** React Query en estado de error

**Fix:**
1. Hard refresh (Ctrl + Shift + R)
2. Si no funciona: Clear all browser data
3. Si aún no: Probar otro navegador

---

## 📞 Reportar Problema

Si después de todos estos pasos aún no funciona, reporta:

1. **Navegador y versión:**
   - Chrome 120
   - Firefox 121
   - Safari 17
   - Etc.

2. **Output del script de verificación completa** (arriba)

3. **Screenshot de DevTools Console** (F12 → Console)

4. **Screenshot de DevTools Network** (F12 → Network → refresh página)

5. **Backend logs durante el problema:**
   ```bash
   docker-compose logs backend --tail 50
   ```

---

## ✅ Checklist de Resolución

- [ ] Backend está corriendo (docker-compose ps)
- [ ] Frontend está corriendo (docker-compose ps)
- [ ] Backend responde a curl (curl http://localhost:8000/health)
- [ ] CORS está configurado correctamente
- [ ] Frontend usa API_URL correcto (VITE_API_URL=http://localhost:8000)
- [ ] Hard refresh en navegador (Ctrl + Shift + R)
- [ ] No hay errores en Console (F12)
- [ ] Network tab muestra requests a /api/v1/settings con 200 OK
- [ ] Probado en modo incógnito
- [ ] Probado en otro navegador

---

**Si todos los ✅ están marcados y aún no funciona, hay un bug en el código que necesita investigación más profunda.**

---

**Created:** 2025-12-13 20:45
**Purpose:** Debugging frontend-backend communication issues
**Status:** Active troubleshooting guide
