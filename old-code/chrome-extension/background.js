// Service Worker para la extensión de Chrome
// Se ejecuta en segundo plano

// Listener para cuando se instala la extensión
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('Videorama Video Sender instalado correctamente');

    // Abrir la página de opciones en la primera instalación
    chrome.runtime.openOptionsPage();
  } else if (details.reason === 'update') {
    console.log('Videorama Video Sender actualizado a la versión', chrome.runtime.getManifest().version);
  }
});

// Listener para mensajes desde el popup o content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  // Aquí se pueden manejar mensajes en segundo plano si es necesario
  return true;
});
