// Elementos del DOM
const videoUrlInput = document.getElementById('videoUrl');
const sendButton = document.getElementById('sendButton');
const optionsButton = document.getElementById('optionsButton');
const statusDiv = document.getElementById('status');
const autoDownloadCheckbox = document.getElementById('autoDownload');
const musicLibraryCheckbox = document.getElementById('musicLibrary');
const noConfigDiv = document.getElementById('noConfig');
const mainContent = document.getElementById('mainContent');
const loadingDiv = document.getElementById('loading');

let serverUrl = '';

// Inicializar al cargar el popup
document.addEventListener('DOMContentLoaded', async () => {
  // Cargar configuración
  const result = await chrome.storage.sync.get(['serverUrl']);

  if (!result.serverUrl) {
    // No hay configuración
    noConfigDiv.style.display = 'block';
    mainContent.style.display = 'none';
    sendButton.disabled = true;
    return;
  }

  serverUrl = result.serverUrl;

  // Detectar URL de video en la página actual
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (tab && tab.url) {
      // Detectar si es un sitio de video conocido
      const videoUrl = detectVideoUrl(tab.url);

      if (videoUrl) {
        videoUrlInput.value = videoUrl;
        videoUrlInput.classList.add('detected-url');
      }
    }

    // Intentar obtener URL detectada por el content script
    chrome.tabs.sendMessage(tab.id, { action: 'getVideoUrl' }, (response) => {
      if (chrome.runtime.lastError) {
        // El content script puede no estar cargado aún, no es un error crítico
        return;
      }

      if (response && response.url && !videoUrlInput.value) {
        videoUrlInput.value = response.url;
        videoUrlInput.classList.add('detected-url');
      }
    });
  } catch (error) {
    console.error('Error al detectar URL:', error);
  }
});

// Detectar URLs de sitios de video conocidos
function detectVideoUrl(url) {
  // YouTube
  if (url.includes('youtube.com/watch') || url.includes('youtu.be/')) {
    return url;
  }

  // Vimeo
  if (url.includes('vimeo.com/')) {
    return url;
  }

  // Dailymotion
  if (url.includes('dailymotion.com/video/')) {
    return url;
  }

  // Twitch
  if (url.includes('twitch.tv/videos/') || url.includes('twitch.tv/') && url.includes('/clip/')) {
    return url;
  }

  // Twitter/X
  if ((url.includes('twitter.com/') || url.includes('x.com/')) && url.includes('/status/')) {
    return url;
  }

  // Reddit
  if (url.includes('reddit.com/') && (url.includes('/comments/') || url.includes('v.redd.it'))) {
    return url;
  }

  // TikTok
  if (url.includes('tiktok.com/')) {
    return url;
  }

  // Instagram
  if (url.includes('instagram.com/p/') || url.includes('instagram.com/reel/')) {
    return url;
  }

  // Facebook
  if (url.includes('facebook.com/') && (url.includes('/videos/') || url.includes('/watch/'))) {
    return url;
  }

  return null;
}

// Botón de enviar
sendButton.addEventListener('click', async () => {
  const url = videoUrlInput.value.trim();

  if (!url) {
    showStatus('Por favor, introduce una URL de video', 'error');
    return;
  }

  if (!serverUrl) {
    showStatus('Configura la URL del servidor primero', 'error');
    return;
  }

  // Validar formato básico de URL
  try {
    new URL(url);
  } catch (error) {
    showStatus('La URL no es válida', 'error');
    return;
  }

  // Mostrar loading
  mainContent.style.display = 'none';
  loadingDiv.style.display = 'block';

  try {
    // Preparar el payload según la API de Videorama
    const payload = {
      url: url,
      auto_download: autoDownloadCheckbox.checked,
      library: musicLibraryCheckbox.checked ? 'music' : 'video'
    };

    // Enviar a Videorama
    const response = await fetch(`${serverUrl}/api/library`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    loadingDiv.style.display = 'none';
    mainContent.style.display = 'block';

    if (response.ok) {
      const data = await response.json();
      showStatus('Video enviado correctamente a Videorama', 'success');

      // Limpiar el input después de enviar
      videoUrlInput.value = '';
      videoUrlInput.classList.remove('detected-url');

      // Opcional: cerrar el popup después de unos segundos
      setTimeout(() => {
        window.close();
      }, 2000);
    } else {
      const errorText = await response.text();
      let errorMessage = 'Error al enviar el video';

      try {
        const errorData = JSON.parse(errorText);
        errorMessage = errorData.detail || errorMessage;
      } catch (e) {
        errorMessage = `Error ${response.status}: ${errorText}`;
      }

      showStatus(errorMessage, 'error');
    }
  } catch (error) {
    loadingDiv.style.display = 'none';
    mainContent.style.display = 'block';
    showStatus('Error de conexión: ' + error.message, 'error');
    console.error('Error al enviar video:', error);
  }
});

// Botón de opciones
optionsButton.addEventListener('click', () => {
  chrome.runtime.openOptionsPage();
});

// Función auxiliar para mostrar mensajes de estado
function showStatus(message, type) {
  statusDiv.textContent = message;
  statusDiv.className = 'status ' + type;
  statusDiv.style.display = 'block';

  // Ocultar el mensaje después de 5 segundos si es éxito
  if (type === 'success') {
    setTimeout(() => {
      statusDiv.style.display = 'none';
    }, 5000);
  }
}

// Permitir enviar con Enter
videoUrlInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    sendButton.click();
  }
});
