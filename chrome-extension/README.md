# Videorama Importer (Chrome Extension)

Carga la extensión como *Unpacked* en Chrome:
1. Abre `chrome://extensions` y activa *Developer mode*.
2. Haz clic en *Load unpacked* y selecciona la carpeta `chrome-extension`.
3. Configura la API base en Opciones y prueba el popup en una pestaña con video.

La extensión envía `POST /api/v1/import/url` al backend configurado, usando `imported_by: "chrome-extension"`.
