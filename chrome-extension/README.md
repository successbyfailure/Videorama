# Videorama Video Sender - Extensión de Chrome

Extensión de Chrome para enviar videos directamente a tu servidor Videorama desde cualquier página web.

## Características

- 🎥 Detección automática de URLs de video en páginas populares
- 🔄 Envío rápido de videos a Videorama con un solo clic
- ⚙️ Configuración simple de la URL del servidor
- 📚 Soporte para bibliotecas de video y música
- ✅ Descarga automática opcional
- 🌐 Compatibilidad con múltiples plataformas de video

## Plataformas de Video Compatibles

La extensión detecta automáticamente videos de:

- YouTube
- Vimeo
- Dailymotion
- Twitch
- Twitter/X
- Reddit
- TikTok
- Instagram
- Facebook
- Cualquier página con elementos HTML5 `<video>`

## Instalación

### Método 1: Instalación desde el código fuente (Desarrollo)

1. Clona o descarga este repositorio
2. Abre Chrome y ve a `chrome://extensions/`
3. Activa el "Modo de desarrollador" (esquina superior derecha)
4. Haz clic en "Cargar extensión sin empaquetar"
5. Selecciona la carpeta `chrome-extension` de este proyecto
6. ¡Listo! El icono de Videorama aparecerá en tu barra de herramientas

### Método 2: Generar iconos (opcional)

Si necesitas regenerar los iconos:

```bash
cd chrome-extension/icons
pip install Pillow
python3 generate_icons.py
```

## Configuración

1. Haz clic en el icono de la extensión Videorama
2. Haz clic en el botón "Opciones"
3. Introduce la URL de tu servidor Videorama (ejemplo: `http://localhost:8600`)
4. Haz clic en "Probar conexión" para verificar que funciona
5. Haz clic en "Guardar"

### URL del Servidor

La URL del servidor debe apuntar a tu instancia de Videorama en ejecución. Ejemplos:

- **Local:** `http://localhost:8600`
- **Red local:** `http://192.168.1.100:8600`
- **Dominio público:** `https://videorama.example.com`

**Nota:** Si tu servidor usa HTTPS, asegúrate de usar `https://` en la URL. Si usas HTTP, la URL debe ser `http://`.

## Uso

### Enviar un video desde una página web

1. Navega a cualquier página con un video (YouTube, Vimeo, etc.)
2. Haz clic en el icono de Videorama en la barra de herramientas
3. La URL del video se detectará automáticamente
4. (Opcional) Marca "Añadir a biblioteca de música" si es un video musical
5. (Opcional) Desmarca "Descargar automáticamente" si solo quieres guardar la referencia
6. Haz clic en "Enviar"
7. ¡Listo! El video se ha enviado a Videorama

### Enviar una URL manualmente

1. Copia la URL del video
2. Haz clic en el icono de Videorama
3. Pega la URL en el campo de texto
4. Configura las opciones según necesites
5. Haz clic en "Enviar"

## Opciones Disponibles

- **Descargar automáticamente:** Si está marcado, Videorama descargará el video inmediatamente. Si no, solo guardará la referencia.
- **Añadir a biblioteca de música:** Si está marcado, el video se añadirá a la biblioteca de música en lugar de la de videos.

## API de Videorama

La extensión utiliza el endpoint `/api/library` de Videorama con el siguiente formato:

```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "auto_download": true,
  "library": "video"
}
```

Para más información sobre la API de Videorama, consulta la documentación del servidor.

## Desarrollo

### Estructura de archivos

```
chrome-extension/
├── manifest.json          # Configuración de la extensión
├── popup.html            # Interfaz del popup principal
├── popup.js              # Lógica del popup
├── options.html          # Página de configuración
├── options.js            # Lógica de configuración
├── content.js            # Script que se ejecuta en páginas web
├── background.js         # Service worker en segundo plano
├── icons/                # Iconos de la extensión
│   ├── icon16.png
│   ├── icon48.png
│   ├── icon128.png
│   ├── icon.svg
│   └── generate_icons.py
└── README.md             # Este archivo
```

### Permisos

La extensión requiere los siguientes permisos:

- `activeTab`: Para acceder a la URL de la pestaña activa
- `storage`: Para guardar la configuración del usuario
- `scripting`: Para inyectar scripts en páginas web
- `host_permissions`: Para hacer peticiones HTTP/HTTPS al servidor Videorama

### Modificar la extensión

1. Realiza los cambios en los archivos correspondientes
2. Ve a `chrome://extensions/`
3. Haz clic en el botón de recarga (🔄) en la tarjeta de Videorama Video Sender
4. Prueba los cambios

## Solución de Problemas

### La extensión no detecta el video

- Asegúrate de estar en una página compatible
- Intenta pegar la URL manualmente en el campo de texto
- Verifica que la URL sea válida

### Error al enviar el video

- Verifica que el servidor Videorama esté en ejecución
- Comprueba que la URL del servidor sea correcta en Opciones
- Usa el botón "Probar conexión" en Opciones
- Revisa la consola del navegador para más detalles (F12)

### Error de CORS

Si ves errores de CORS en la consola:

- Asegúrate de que tu servidor Videorama permita peticiones desde `chrome-extension://`
- Si usas HTTPS, asegúrate de que el certificado sea válido

### El servidor responde con error 404 o 500

- Verifica que tu servidor Videorama esté actualizado
- Revisa los logs del servidor Videorama para más detalles

## Licencia

Este proyecto es parte de Videorama y está bajo la misma licencia que el proyecto principal.

## Contribuir

Si encuentras algún error o tienes sugerencias de mejora:

1. Abre un issue en el repositorio de Videorama
2. Describe el problema o la mejora sugerida
3. Incluye capturas de pantalla si es relevante

## Changelog

### Versión 1.0.0 (2025-12-12)

- Versión inicial
- Detección automática de videos en páginas populares
- Configuración de URL del servidor
- Envío de videos a bibliotecas de video y música
- Opción de descarga automática
