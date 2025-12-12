// Cargar la configuración guardada al abrir la página
document.addEventListener('DOMContentLoaded', async () => {
  const result = await chrome.storage.sync.get(['serverUrl']);
  if (result.serverUrl) {
    document.getElementById('serverUrl').value = result.serverUrl;
  }
});

// Guardar la configuración
document.getElementById('save').addEventListener('click', async () => {
  const serverUrl = document.getElementById('serverUrl').value.trim();

  if (!serverUrl) {
    showStatus('Por favor, introduce una URL válida', 'error');
    return;
  }

  // Normalizar URL (remover trailing slash)
  const normalizedUrl = serverUrl.replace(/\/+$/, '');

  try {
    await chrome.storage.sync.set({ serverUrl: normalizedUrl });
    showStatus('Configuración guardada correctamente', 'success');
  } catch (error) {
    showStatus('Error al guardar la configuración: ' + error.message, 'error');
  }
});

// Probar la conexión con el servidor
document.getElementById('test').addEventListener('click', async () => {
  const serverUrl = document.getElementById('serverUrl').value.trim();

  if (!serverUrl) {
    showStatus('Por favor, introduce una URL válida primero', 'error');
    return;
  }

  // Normalizar URL
  const normalizedUrl = serverUrl.replace(/\/+$/, '');

  showStatus('Probando conexión...', 'info');

  try {
    // Intentar conectar al endpoint de salud o a la raíz
    const response = await fetch(`${normalizedUrl}/api/library`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json'
      }
    });

    if (response.ok) {
      showStatus('Conexión exitosa al servidor Videorama', 'success');
    } else {
      showStatus(`Servidor respondió con estado ${response.status}. Verifica la URL.`, 'error');
    }
  } catch (error) {
    showStatus('Error de conexión: ' + error.message + '. Verifica que el servidor esté ejecutándose.', 'error');
  }
});

// Función auxiliar para mostrar mensajes de estado
function showStatus(message, type) {
  const statusDiv = document.getElementById('status');
  statusDiv.textContent = message;
  statusDiv.className = 'status ' + type;
  statusDiv.style.display = 'block';

  // Ocultar el mensaje después de 5 segundos (excepto errores)
  if (type !== 'error') {
    setTimeout(() => {
      statusDiv.style.display = 'none';
    }, 5000);
  }
}
