// Content script para detectar videos en la página
// Se ejecuta en el contexto de cada página web

// Función para obtener la URL del video actual
function getVideoUrl() {
  const url = window.location.href;

  // YouTube
  if (url.includes('youtube.com/watch')) {
    return url.split('&')[0]; // Remover parámetros adicionales
  }

  if (url.includes('youtu.be/')) {
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
  if (url.includes('twitch.tv/videos/') || (url.includes('twitch.tv/') && url.includes('/clip/'))) {
    return url;
  }

  // Twitter/X
  if ((url.includes('twitter.com/') || url.includes('x.com/')) && url.includes('/status/')) {
    return url;
  }

  // Reddit
  if (url.includes('reddit.com/') && url.includes('/comments/')) {
    return url;
  }

  if (url.includes('v.redd.it')) {
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

  // Buscar elementos de video HTML5 en la página
  const videoElements = document.querySelectorAll('video');
  if (videoElements.length > 0) {
    // Si hay videos, devolver la URL actual
    return url;
  }

  return null;
}

// Escuchar mensajes desde el popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getVideoUrl') {
    const videoUrl = getVideoUrl();
    sendResponse({ url: videoUrl });
  }
  return true; // Mantener el canal de mensajes abierto para respuestas asíncronas
});

// Opcional: Detectar cuando la URL cambia (para SPAs como YouTube)
let lastUrl = location.href;
new MutationObserver(() => {
  const currentUrl = location.href;
  if (currentUrl !== lastUrl) {
    lastUrl = currentUrl;
    // URL ha cambiado, podríamos hacer algo aquí si es necesario
  }
}).observe(document, { subtree: true, childList: true });
